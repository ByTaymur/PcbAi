import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="PcbAi local KiCad core")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Inspect environment without changing settings")
    commands.add_parser("stop", help="Gracefully stop an already running authenticated service")
    server = commands.add_parser("serve", help="Run the authenticated loopback service")
    server.add_argument("--project", action="append", default=[], help="Existing .kicad_pro to register")
    summary = commands.add_parser("inspect", help="Inspect a saved KiCad project")
    summary.add_argument("project")
    args = parser.parse_args()
    if args.command == "doctor":
        from pcbai.doctor import inspect
        print(json.dumps(inspect(), ensure_ascii=False, indent=2))
    elif args.command == "stop":
        from mcp_server.client import Client
        print(json.dumps(Client().shutdown(), ensure_ascii=False, indent=2))
    elif args.command == "serve":
        from pcbai.service.server import serve
        serve(args.project)
    else:
        from pcbai.config import state_directory
        from pcbai.tools.engine import Engine
        from pcbai.service.sessions import Sessions
        registered = Sessions([args.project])
        engine = Engine([args.project], state_directory(s.root for s in registered.entries.values()))
        session = next(iter(engine.sessions.entries))
        print(json.dumps(engine.call("project_summary", {"session": session}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
