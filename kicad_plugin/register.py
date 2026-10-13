from pcbai_kicad import client_for, current_project, message, run, session_for


def register():
    project, _board = current_project()
    client = client_for(project)
    session = session_for(client, project)
    message(f"{project.name} PcbAi'ye kayıtlı.\nOturum: {session['id']}\n\n"
            "MCP ajanları (Claude Code, Codex, Cline) bu projeyi pcbai_status ile görür.\n"
            "PcbAi yalnızca kaydedilmiş dosyaları okur; şematik değişikliği için KiCad kapalı olmalı.")


run(register)
