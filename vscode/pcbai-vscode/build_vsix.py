"""Package the extension as a .vsix without Node/vsce (standard library only).

    python vscode/pcbai-vscode/build_vsix.py      -> vscode/pcbai-vscode/dist/pcbai-vscode-<version>.vsix
Install:  code --install-extension <vsix> --force
The PcbAi checkout path is written into the package as the default "pcbai.root".
"""
import json
import argparse
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INCLUDE = ["package.json", "extension.js", "board_view.js", "sch_view.js", "view3d.js", "sidebar_view.js", "agents.js", "agent_prompt.js", "engine_view.js", "part_assist.js", "mcp_setup.js", "handoff.js", "mcp_tools.json", "README.md"]

CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension=".json" ContentType="application/json"/><Default Extension=".js" ContentType="application/javascript"/>
<Default Extension=".md" ContentType="text/markdown"/><Default Extension=".vsixmanifest" ContentType="text/xml"/>
<Default Extension=".css" ContentType="text/css"/><Default Extension=".txt" ContentType="text/plain"/>
<Default Extension=".svg" ContentType="image/svg+xml"/><Default Extension=".png" ContentType="image/png"/>
</Types>"""

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="{name}" Version="{version}" Publisher="{publisher}" />
    <DisplayName>{display}</DisplayName>
    <Description xml:space="preserve">{description}</Description>
    <Categories>Other</Categories>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{engine}" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="ui,workspace" />
    </Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true" />
  </Assets>
</PackageManifest>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service-root', type=Path, default=ROOT, help='Configured checkout with the service .venv')
    args = parser.parse_args()
    service_root = args.service_root.resolve()
    if not (service_root / 'pcbai/__init__.py').is_file():
        parser.error('Service root must contain PcbAi core')
    pkg = json.loads((HERE / "package.json").read_text(encoding="utf-8"))
    schema = HERE / 'schemas/circuit.schema.json'
    if schema.is_file() and schema.read_bytes() != (ROOT / 'pcbai/ir/circuit.schema.json').read_bytes():
        raise ValueError('Bundled IR schema differs from canonical core schema')
    # The extension has its own version: VS Code caches an installed version's manifest, so every
    # extension change needs a new version even when the core is unchanged.
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / f"{pkg['name']}-{pkg['version']}.vsix"
    manifest = MANIFEST.format(name=pkg["name"], version=pkg["version"], publisher=pkg["publisher"],
                               display=escape(pkg["displayName"]), description=escape(pkg["description"]),
                               engine=pkg["engines"]["vscode"])
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("extension.vsixmanifest", manifest)
        for name in INCLUDE:
            z.write(HERE / name, "extension/" + name)
        z.write(ROOT / "LICENSE", "extension/LICENSE")
        for folder in ("media", "syntaxes", "snippets", "language-configuration", "schemas"):
            for path in sorted((HERE / folder).rglob("*")):
                if path.is_file():
                    z.write(path, "extension/" + path.relative_to(HERE).as_posix())
        z.writestr("extension/defaults.json", json.dumps({"root": str(service_root)}, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
