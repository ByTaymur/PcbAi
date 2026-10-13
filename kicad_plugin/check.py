from pathlib import Path

from pcbai_kicad import client_for, current_project, message, run, session_for

SHOWN = 8


def describe(response):
    if not response.get("ok"):
        return ["Çalışmadı: " + response.get("summary", "")]
    lines = [response["summary"] + (f"  (kanıt {response['evidence_id']})" if response.get("evidence_id") else "")]
    lines += ["! " + w for w in response.get("warnings", [])]
    findings = response.get("findings", [])
    for finding in findings[:SHOWN]:
        where = ""
        items = finding.get("items") or []
        if items and items[0].get("pos"):
            where = f" @ ({items[0]['pos']['x']}, {items[0]['pos']['y']}) mm"
        lines.append(f"  [{finding.get('severity')}] {finding.get('description')}{where}")
    if len(findings) > SHOWN:
        lines.append(f"  … {len(findings) - SHOWN} bulgu daha (VS Code: PcbAi → ERC ve DRC çalıştır)")
    return lines


def check():
    project, board = current_project()
    client = client_for(project)
    session = session_for(client, project)
    root = Path(session["root"])
    documents = session.get("documents", [])
    schematic = project.with_suffix(".kicad_sch").relative_to(root).as_posix()
    lines = ["Kaydedilmiş dosyalar denetlendi; kaydedilmemiş değişiklikler dahil değil.", ""]
    if schematic in documents:
        erc = client.request("POST", "/call", {"name": "erc", "arguments": {"session": session["id"],
                                                                           "document": schematic}})
        lines += ["ERC · " + schematic, *describe(erc), ""]
    pcb = board.relative_to(root).as_posix()
    drc = client.request("POST", "/call", {"name": "drc", "arguments": {
        "session": session["id"], "document": pcb, "parity": schematic in documents}})
    lines += ["DRC · " + pcb, *describe(drc)]
    message("\n".join(lines))


run(check)
