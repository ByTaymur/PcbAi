"""Export a commit as a fresh single-commit repository for public release; local history stays private.

    python scripts/export_public.py <empty destination> --name <author> --email <public address> [--ref HEAD]

Machine-only files are left out. The export stops before committing if any file still contains this
machine's home path (any slash style) or the email of the private repository. Patterns are read from the
running machine, so this script itself names nobody. The handle in package manifests is not a path and
is allowed.
"""
import argparse
import io
import os
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".mcp.json"}


def git(*argv, cwd=ROOT, env=None):
    process = subprocess.run(["git", "-C", str(cwd), *argv], capture_output=True, shell=False, timeout=120,
                             env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if process.returncode:
        raise SystemExit(f"git {argv[0]} failed: " + process.stderr.decode("utf-8", "replace").strip())
    return process.stdout


def private_patterns(home=None, emails=()):
    """Home path in Windows, POSIX, escaped-JSON and Git Bash forms, plus private emails; case-insensitive."""
    home = Path(home or Path.home())
    patterns = [r"[\\/]+(?:users|home)[\\/]+" + re.escape(home.name) + r"(?![\w.-])"]
    patterns += [re.escape(e) for e in emails if e]
    return re.compile("|".join(patterns).encode(), re.IGNORECASE)


def leaks(root, pattern):
    found = []
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and ".git" not in path.relative_to(root).parts:
            for number, line in enumerate(path.read_bytes().splitlines(), 1):
                if pattern.search(line):
                    found.append(f"{path.relative_to(root).as_posix()}:{number}")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination.is_relative_to(ROOT.resolve()) or (destination.exists() and any(destination.iterdir())):
        raise SystemExit("Destination must be an empty folder outside this checkout")
    private_email = git("config", "user.email").decode().strip()
    if args.email.casefold() == private_email.casefold():
        raise SystemExit("Use a public (for example GitHub noreply) address, not the private repository email")
    archive = tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", args.ref)))
    members = [m for m in archive.getmembers() if m.name not in EXCLUDED]
    if any(not (m.isfile() or m.isdir()) for m in members):
        raise SystemExit("Links are not exported")
    destination.mkdir(parents=True, exist_ok=True)
    archive.extractall(destination, members, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    found = leaks(destination, private_patterns(emails=[private_email]))
    if found:
        raise SystemExit("Private data remains; nothing committed:\n  " + "\n  ".join(found))
    version = git("show", f"{args.ref}:pcbai/__init__.py").decode()
    version = re.search(r'__version__\s*=\s*"([^"]+)"', version).group(1)
    git("init", "-q", "-b", "main", cwd=destination)
    git("config", "user.name", args.name, cwd=destination)
    git("config", "user.email", args.email, cwd=destination)
    git("add", "-A", cwd=destination)
    identity = dict(os.environ, GIT_AUTHOR_NAME=args.name, GIT_AUTHOR_EMAIL=args.email,
                    GIT_COMMITTER_NAME=args.name, GIT_COMMITTER_EMAIL=args.email)
    git("commit", "-q", "-m", f"PcbAi {version}", cwd=destination, env=identity)
    print(f"{destination}: PcbAi {version}, 1 commit, {len(members)} entries; no private paths or email found")


if __name__ == "__main__":
    main()
