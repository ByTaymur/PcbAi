"""Audit declared dependencies and distributable bundles; external GPL motors must never be packaged/imported."""
import argparse
import ast
import json
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {"tracemaker", "tracemaker-bindings", "bindings", "kiutils", "easyeda2kicad", "freerouting"}


def audit(root):
    issues = []
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        dependencies.extend(group)
    for dependency in dependencies:
        name = dependency.split(";")[0].split("[")[0]
        for separator in ("<", ">", "=", "~", "!", " "):
            name = name.split(separator)[0]
        if name.lower().replace("_", "-") in FORBIDDEN:
            issues.append("Forbidden in-process dependency: " + dependency)
    for file in (root / "pcbai").rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for module in modules:
                if module.split(".")[0].lower().replace("_", "-") in FORBIDDEN:
                    issues.append(f"Forbidden import {file.relative_to(root)}:{node.lineno}: {module}")
    manifests = [(root / "vscode/pcbai-vscode/package.json"), (root / "kicad_plugin/plugin.json")]
    for manifest in manifests:
        if json.loads(manifest.read_text(encoding="utf-8")).get("license") != project["license"]["text"]:
            issues.append("Package license differs: " + str(manifest.relative_to(root)))
    for directory in (root / "vscode/pcbai-vscode/dist", root / "kicad_plugin/dist"):
        for bundle in directory.glob("*"):
            if bundle.suffix not in {".zip", ".vsix"}:
                continue
            with zipfile.ZipFile(bundle) as archive:
                for member in archive.namelist():
                    name = Path(member).name.lower()
                    if name.endswith((".exe", ".dll", ".jar")) or name.startswith(("tracemaker", "freerouting")):
                        issues.append(f"External engine/binary packaged: {bundle.name}: {member}")
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    issues = audit(args.root)
    for issue in issues:
        print(issue)
    if not issues:
        print("Declared dependencies, engine imports, package licenses and bundled binaries: clean")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
