import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path

from pcbai.core.contract import PcbAiError
from pcbai.external import find_kicad_cli
from pcbai.tools.engine import Engine
from pcbai.view_3d import component_nodes, glb_json, model_substitutions


def glb(document, payload=b""):
    body = json.dumps(document).encode()
    body += b" " * (-len(body) % 4)
    data = struct.pack("<I4s", len(body), b"JSON") + body
    if payload:
        data += struct.pack("<I4s", len(payload), b"BIN\0") + payload
    return struct.pack("<4sII", b"glTF", 2, 12 + len(data)) + data


class GlbTests(unittest.TestCase):
    def test_valid_container_and_component_names(self):
        document = {"asset": {"version": "2.0"}, "nodes": [{"name": "R1"}, {"name": "R1 (Face)"}, {"name": "U3"}]}
        parsed = glb_json(glb(document))
        matched, missing = component_nodes(parsed, ["R1", "U3", "J9"])
        self.assertEqual(matched, {"R1": [0], "U3": [2]})
        self.assertEqual(missing, ["J9"])

    def test_external_uris_extensions_and_bad_headers_refused(self):
        for document in ({"buffers": [{"uri": "https://example.org/x.bin"}]},
                         {"images": [{"uri": "data:image/png;base64,AAAA"}]},
                         {"extensionsRequired": ["KHR_draco_mesh_compression"]}):
            with self.assertRaises(PcbAiError):
                glb_json(glb(document))
        good = glb({"asset": {}})
        for bad in (b"", b"glTF" + good[4:8] + struct.pack("<I", 999) + good[12:], good.replace(b"JSON", b"JSOX", 1)):
            with self.assertRaises(PcbAiError):
                glb_json(bad)

    def test_display_only_model_path_fixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            (library / "R.3dshapes").mkdir()
            (library / "R.3dshapes/R1.step").write_bytes(b"x")
            data = (b'(footprint (model "${KICAD6_3DMODEL_DIR}/R.3dshapes/R1.wrl")) '
                    b'(footprint (model "${KICAD10_3DMODEL_DIR}/X.3dshapes/missing.wrl")) '
                    b'(footprint (model "${KIPRJMOD}/local.wrl"))')
            fixed, count = model_substitutions(data, library)
            self.assertIn(b'"${KICAD10_3DMODEL_DIR}/R.3dshapes/R1.step"', fixed)
            self.assertIn(b'"${KICAD10_3DMODEL_DIR}/X.3dshapes/missing.wrl"', fixed)  # no .step: unchanged
            self.assertIn(b'"${KIPRJMOD}/local.wrl"', fixed)
            self.assertEqual(count, 1)


def demo(name):
    try:
        path = Path(find_kicad_cli()).parent.parent / "share/kicad/demos" / name
    except PcbAiError:
        return None
    return path if path.is_dir() else None


@unittest.skipUnless(demo("ecc83"), "KiCad demos required")
class Render3dIntegrationTests(unittest.TestCase):
    def test_ecc83_glb_with_selectable_references_and_untouched_source(self):
        with tempfile.TemporaryDirectory(prefix="pcbai-3d-") as tmp:
            root = Path(tmp) / "ecc83"
            shutil.copytree(demo("ecc83"), root)
            state = Path(tmp) / "state"
            state.mkdir()
            engine = Engine([root / "ecc83-pp.kicad_pro"], state)
            session = next(iter(engine.sessions.entries.values()))
            original = (root / "ecc83-pp.kicad_pcb").read_bytes()
            response = engine.call("render_3d", session.target("ecc83-pp.kicad_pcb"))
            self.assertTrue(response["ok"], response)
            render = response["render"]
            self.assertIn("U1", render["components"])
            self.assertGreaterEqual(len(render["components"]), 10)
            self.assertGreater(render["display_model_substitutions"], 0)
            self.assertEqual((root / "ecc83-pp.kicad_pcb").read_bytes(), original)
            again = engine.call("render_3d", session.target("ecc83-pp.kicad_pcb"))
            self.assertEqual(again["render"]["sha256"], render["sha256"])  # revision cache
