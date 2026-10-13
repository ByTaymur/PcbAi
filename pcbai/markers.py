"""Project annotations with user-state HMAC, revision-bound preview/apply and checkpoints."""

import hmac
import json
import secrets
import time
import threading
from datetime import datetime, timezone

from pcbai.core.contract import PcbAiError
from pcbai.core.registry import STRING, schema, validate
from pcbai.kicad.files import atomic_write, digest, within, write_lock
from pcbai.sch.scene import scene_sch
from pcbai.views import scene_pcb, transform, rotate

POINTS = dict(
    type="array",
    minItems=1,
    maxItems=256,
    items=dict(type="array", minItems=2, maxItems=2, items=dict(type="number", minimum=-1e6, maximum=1e6)),
)
MARKER = schema(
    dict(
        kind=dict(type="string", enum=["point", "line", "area", "item"]),
        space=dict(type="string", enum=["pcb", "sch"]),
        points_mm=POINTS,
        layer=STRING,
        sheet=dict(type="string", maxLength=4096),
        anchor=schema(dict(type=STRING, uuid=STRING), ["type", "uuid"]),
        note=dict(type="string", maxLength=4096),
    ),
    ["kind", "space", "points_mm", "note"],
)
FILE = "pcbai/markers.json"


def anchor_items(root, document, space, sheet):
    """Scene items keyed by UUID. Schematic items are per sheet instance (shared files have several)."""
    data = within(root, document).read_bytes()
    items = scene_pcb(data)["items"] if space == "pcb" else scene_sch(data, sheet)["items"]
    return {i["uuid"]: i for i in items if i.get("uuid")}


def describe(item):
    keys = ("type", "reference", "value", "number", "name", "net", "text", "lib_id")
    return {k: item[k] for k in keys if item.get(k) not in (None, "")}


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


class Markers:
    def __init__(self, state, history):
        self.state, self.history = state, history
        self.previews = {}
        self.lock = threading.RLock()
        key_path = state / "marker-key.bin"
        # State is private (DACL/mode), and exclusive creation avoids two different keys.
        try:
            with key_path.open("xb") as stream:
                stream.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
        self.key = key_path.read_bytes()
        if len(self.key) != 32:
            raise PcbAiError("unsafe_state", "Invalid marker signing key")

    def signature(self, session, marker):
        return hmac.new(
            self.key, str(session.root).encode() + b"\0" + canonical(marker), "sha256"
        ).hexdigest()

    def read(self, session):
        path = within(session.root, FILE, must_exist=False)
        raw = path.read_bytes() if path.exists() else b""
        try:
            if len(raw) > 1024 * 1024:
                raise ValueError()
            payload = json.loads(raw) if raw else {"version": 1, "next_n": 1, "markers": []}
            records = payload["markers"]
            if payload["version"] != 1 or not isinstance(records, list) or len(records) > 1000:
                raise ValueError()
            numbers = []
            markers = []
            for stored in records:
                marker = dict(stored)
                signature = marker.pop("signature", "")
                if type(marker["n"]) is not int or marker["n"] < 1 or not isinstance(signature, str):
                    raise ValueError()
                fields = {k: marker[k] for k in MARKER["properties"] if k in marker}
                validate(MARKER, fields)
                document_path = within(session.root, marker["document"], must_exist=False)
                if document_path.suffix not in {".kicad_pcb", ".kicad_sch"}:
                    raise ValueError()
                if "anchor_frame" in marker:
                    validate(POINTS, marker["anchor_frame"])
                if marker["status"] not in {"open", "done", "blocked"}:
                    raise ValueError()
                trusted = hmac.compare_digest(self.signature(session, marker), signature)
                markers.append(dict(marker, trusted=trusted))
                numbers.append(marker["n"])
            if len(numbers) != len(set(numbers)) or type(payload["next_n"]) is not int:
                raise ValueError()
            return (
                dict(
                    markers=markers,
                    markers_revision=digest(raw),
                    next_n=max(payload["next_n"], max(numbers, default=0) + 1),
                ),
                payload,
                raw,
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise PcbAiError("invalid_markers", "Marker file is corrupt; it will not be overwritten") from exc

    def get(self, session):
        output, _, _ = self.read(session)
        scenes = {}
        for marker in output["markers"]:
            marker["binding"] = "coordinate"
            if not marker.get("anchor"):
                continue
            document = marker["document"]
            if not within(session.root, document, must_exist=False).is_file():
                marker["binding"] = "orphaned"
                continue
            if marker["space"] == "sch" and not marker.get("sheet"):
                marker["binding"] = "unresolved"
                continue
            key = (document, marker.get("sheet") if marker["space"] == "sch" else None)
            if key not in scenes:
                scenes[key] = anchor_items(session.root, document, marker["space"], key[1])
            item = scenes[key].get(marker["anchor"]["uuid"])
            if item is None or item["type"] != marker["anchor"]["type"] or not marker.get("anchor_frame"):
                marker["binding"] = "orphaned"
            else:
                marker["binding"] = "bound"
                marker["target_item"] = describe(item)
                frame = marker["anchor_frame"]
                marker["points_mm"] = [transform(p, item["at"], item.get("rotation", 0)) for p in frame]
        return output

    def preview(self, session, target, args, delete=False):
        current, payload, raw = self.read(session)
        if current["markers_revision"] != args["markers_revision"]:
            raise PcbAiError("stale_markers", "Markers changed; refresh and preview again")
        records = payload["markers"]
        n = args.get("n")
        matches = [m for m in records if m["n"] == n]
        if n is not None and len(matches) != 1:
            raise PcbAiError("unknown_marker", "Marker number is absent")
        if matches and matches[0]["document"] != target["document"]:
            raise PcbAiError("wrong_target", "Marker belongs to another document")
        if delete:
            if n is None:
                raise PcbAiError("invalid_arguments", "Delete requires marker number")
            records = [m for m in records if m["n"] != n]
            saved = None
        else:
            if "marker" not in args:
                raise PcbAiError("invalid_arguments", "Preview requires marker")
            marker = args["marker"]
            count = len(marker["points_mm"])
            minimum = {"point": 1, "item": 1, "line": 2, "area": 3}[marker["kind"]]
            if count < minimum or (marker["kind"] in {"point", "item", "line"} and count != minimum):
                raise PcbAiError("invalid_arguments", "Marker geometry does not match its kind")
            suffix = ".kicad_pcb" if marker["space"] == "pcb" else ".kicad_sch"
            if not target["document"].endswith(suffix):
                raise PcbAiError("invalid_document", "Marker coordinate space and document disagree")
            existing = next((m for m in current["markers"] if m["n"] == n), None)
            if existing and not existing["trusted"] and not args.get("approve_untrusted", False):
                raise PcbAiError(
                    "untrusted_marker", "Explicit UI approval is required to sign an imported marker"
                )
            counter = self.state / ("marker-counter-" + session.id + ".json")
            high = json.loads(counter.read_text())["next_n"] if counter.exists() else 1
            n = n or max(current["next_n"], high)
            saved = dict(
                marker,
                n=n,
                document=target["document"],
                revision=target["revision"],
                status="open",
                created=matches[0]["created"] if matches else datetime.now(timezone.utc).isoformat(),
            )
            if marker["space"] == "sch" and "sheet" in marker and not marker["sheet"].startswith("/"):
                raise PcbAiError("invalid_arguments", "Schematic sheet must be a KiCad UUID instance path")
            if marker.get("anchor"):
                if marker["space"] == "sch" and not marker.get("sheet"):
                    raise PcbAiError("invalid_anchor", "Schematic anchors require the sheet instance path")
                items = anchor_items(session.root, target["document"], marker["space"], marker.get("sheet"))
                item = items.get(marker["anchor"]["uuid"])
                if item is not None and item["type"] != marker["anchor"]["type"]:
                    item = None
                if item is None and matches and matches[0].get("anchor") == marker["anchor"]:
                    saved["anchor_frame"] = matches[0].get("anchor_frame", marker["points_mm"])
                    saved["points_mm"] = matches[0]["points_mm"]
                elif item is None or item["uuid"].startswith("anonymous-"):
                    raise PcbAiError("invalid_anchor", "Anchor requires an existing stable UUID")
                else:
                    saved["anchor_frame"] = [
                        rotate([p[0] - item["at"][0], p[1] - item["at"][1]], -item.get("rotation", 0))
                        for p in marker["points_mm"]
                    ]
            saved["signature"] = self.signature(session, saved)
            records = [m for m in records if m["n"] != n] + [saved]
        if len(records) > 1000:
            raise PcbAiError("too_many_markers", "Project marker limit reached")
        after = canonical(dict(version=1, next_n=max(current["next_n"], (n or 0) + 1), markers=records))
        self.previews = {k: v for k, v in self.previews.items() if v["expires"] > time.monotonic()}
        if len(self.previews) >= 100:
            raise PcbAiError("too_many_candidates", "Too many marker previews")
        candidate = "marker-" + secrets.token_hex(16)
        self.previews[candidate] = dict(
            target=target,
            before=digest(raw),
            after=after,
            action="delete" if delete else "set",
            marker=saved,
            expires=time.monotonic() + 900,
        )
        return dict(
            candidate_id=candidate,
            mode="preview",
            marker=saved,
            markers_revision=digest(raw),
            after_sha256=digest(after),
            would_change=raw != after,
        )

    def preview_status(self, session, target, args):
        current, payload, raw = self.read(session)
        if current["markers_revision"] != args["markers_revision"]:
            raise PcbAiError("stale_markers", "Markers changed; preview again")
        marker = next((m for m in current["markers"] if m["n"] == args["n"]), None)
        if not marker or marker["document"] != target["document"]:
            raise PcbAiError("wrong_target", "Select the marker's explicit document")
        if not marker["trusted"]:
            raise PcbAiError("untrusted_marker", "Approve this marker in the UI before updating its status")
        if "status" not in args or not args.get("reason", "").strip():
            raise PcbAiError("invalid_arguments", "Status preview requires status and a reason")
        saved = next(dict(m) for m in payload["markers"] if m["n"] == args["n"])
        saved.pop("signature", None)
        saved.update(
            status=args["status"], reason=args["reason"], updated=datetime.now(timezone.utc).isoformat()
        )
        saved.pop("evidence_id", None)
        if args["status"] == "done":
            evidence_id = args.get("evidence_id", "")
            if (
                len(evidence_id) != 35
                or not evidence_id.startswith("ev-")
                or any(c not in "0123456789abcdef" for c in evidence_id[3:])
            ):
                raise PcbAiError("invalid_evidence", "Done requires a real change evidence ID")
            try:
                evidence = json.loads((self.state / "evidence" / (evidence_id + ".json")).read_bytes())
            except (OSError, ValueError) as exc:
                raise PcbAiError("invalid_evidence", "Change evidence is missing") from exc
            if (
                evidence.get("tool") not in {"set_value", "restore_checkpoint", "move_footprint",
                                             "set_track_width", "add_zone", "set_netclass", "autoroute", "autoplace",
                                             "add_symbol", "connect", "add_label", "replace_part", "add_block"}
                or evidence.get("target") != target
                or not evidence.get("report", {}).get("changed")
                or evidence["report"].get("before_sha256") == evidence["report"].get("after_sha256")
            ):
                raise PcbAiError(
                    "invalid_evidence", "Evidence does not prove a change on this target/revision"
                )
            saved["evidence_id"] = evidence_id
        saved["signature"] = self.signature(session, saved)
        payload["markers"] = [saved if m["n"] == args["n"] else m for m in payload["markers"]]
        candidate = "marker-" + secrets.token_hex(16)
        self.previews = {k: v for k, v in self.previews.items() if v["expires"] > time.monotonic()}
        if len(self.previews) >= 100:
            raise PcbAiError("too_many_candidates", "Too many marker previews")
        after = canonical(payload)
        self.previews[candidate] = dict(
            target=target,
            before=digest(raw),
            after=after,
            action="status",
            marker=saved,
            expires=time.monotonic() + 900,
        )
        return dict(
            candidate_id=candidate,
            markers_revision=digest(raw),
            marker=saved,
            mode="preview",
            after_sha256=digest(after),
            would_change=raw != after,
        )

    def apply(self, session, target, args, delete=False, status=False):
        if set(args) - {"session", "document", "revision", "markers_revision", "mode", "candidate_id"}:
            raise PcbAiError("invalid_arguments", "Apply takes candidate_id only, no new marker fields")
        candidate = self.previews.get(args.get("candidate_id"))
        if not candidate or candidate["expires"] <= time.monotonic():
            raise PcbAiError("invalid_candidate", "Marker preview is missing or expired")
        action = "status" if status else "delete" if delete else "set"
        if candidate["target"] != target or candidate["action"] != action:
            raise PcbAiError("wrong_target", "Marker preview target differs")
        with write_lock(session.root, self.state):
            session.validate(target["document"], target["revision"])
            current, _, raw = self.read(session)
            if (
                candidate["before"] != current["markers_revision"]
                or args["markers_revision"] != current["markers_revision"]
            ):
                raise PcbAiError("stale_markers", "Markers changed since preview")
            path = within(session.root, FILE, must_exist=False)
            checkpoint = self.history.checkpoint(
                session.id, FILE, raw, target["revision"], "Before marker edit"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            within(session.root, FILE, must_exist=False)
            # Reserve the monotonic counter before committing the file. A crash may skip a number, never reuse it.
            after = json.loads(candidate["after"])
            counter = self.state / ("marker-counter-" + session.id + ".json")
            old = json.loads(counter.read_text())["next_n"] if counter.exists() else 1
            atomic_write(counter, canonical(dict(next_n=max(old, after["next_n"]))))
            atomic_write(path, candidate["after"])
            del self.previews[args["candidate_id"]]
            return dict(
                checkpoint=checkpoint, markers_revision=digest(candidate["after"]), marker=candidate["marker"]
            )
