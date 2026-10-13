"""Explicit check coverage; omissions and crashes outrank findings."""
from pcbai.core.contract import PcbAiError
from pcbai.verify.limits import require


def entry(check_id, *, required=True, status="ran", reason=None, limit_id=None,
          inputs_sha256=None, tool=None, tool_version=None, seconds=0):
    if status not in {"ran", "skipped", "failed", "not_applicable"}:
        raise PcbAiError("invalid_manifest", "Unknown check status")
    if status in {"skipped", "failed"} and not reason:
        raise PcbAiError("invalid_manifest", "Incomplete checks need a reason")
    if limit_id is not None:
        require(limit_id)
    row = dict(check_id=check_id, required=required, status=status, reason=reason,
               inputs_sha256=inputs_sha256, tool=tool or check_id, tool_version=tool_version, seconds=seconds)
    if limit_id:
        row["limit_id"] = limit_id
    return row


def verification(checks, findings):
    required = [row for row in checks if row["required"]]
    if not required or any(row["status"] != "ran" for row in required):
        return "checks_incomplete"
    return "checks_findings" if findings else "checks_ok"
