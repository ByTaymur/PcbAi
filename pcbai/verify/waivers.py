"""Exact finding waivers: bounded data, visible disposition, previewed sidecar writes."""
import copy
import json
import os
import re
import secrets
import threading
import time
from datetime import date, datetime, timezone

from pcbai.core.contract import PcbAiError
from pcbai.core.registry import schema, validate
from pcbai.kicad.files import assert_closed, atomic_write, digest, within, write_lock, WAIVER_FILE, MAX_WAIVER_BYTES

FILE = WAIVER_FILE
MAX_BYTES = MAX_WAIVER_BYTES
MAX_RECORDS = 1000
POLICY_CEILING = 365  # largest PCBAI_WAIVER_MAX_DAYS: a longer record is invalid under every policy
ID = re.compile(r"^(erc|drc|parity):[^\s:*?]+:[0-9a-f]{12}(#[1-9][0-9]*)?$")
RECORD = schema(dict(finding_id=dict(type="string", maxLength=512),
                     reason=dict(type="string", maxLength=4096),
                     owner=dict(type="string", maxLength=256),
                     created=dict(type="string", maxLength=10),
                     expires=dict(type="string", maxLength=10)),
                ["finding_id", "reason", "owner", "created", "expires"])


def today():
    return datetime.now(timezone.utc).date()


def max_days():
    raw = os.environ.get("PCBAI_WAIVER_MAX_DAYS", "90")
    if not re.fullmatch(r"[1-9][0-9]{0,2}", raw) or not 1 <= int(raw) <= 365:
        raise PcbAiError("invalid_waiver_policy", "PCBAI_WAIVER_MAX_DAYS must be an integer from 1 to 365")
    return int(raw)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Invalid JSON constant")


def validate_record(record, day, limit, *, active=False):
    validate(RECORD, record)
    if not ID.fullmatch(record["finding_id"]) or not record["reason"].strip() or not record["owner"].strip():
        raise ValueError("Exact ERC/DRC/parity identity, reason and owner are required")
    created, expires = date.fromisoformat(record["created"]), date.fromisoformat(record["expires"])
    if created.isoformat() != record["created"] or expires.isoformat() != record["expires"]:
        raise ValueError("Dates must use YYYY-MM-DD")
    if created > day or not 0 < (expires - created).days <= (POLICY_CEILING if limit is None else limit):
        raise ValueError("Waiver dates exceed the allowed interval")
    if active and expires <= day:
        raise ValueError("A new or previewed waiver must not be expired")


def exceeds(record, limit):
    """Stored record longer than the current duration policy: shown and deletable, but it waives nothing (H3)."""
    return (date.fromisoformat(record["expires"]) - date.fromisoformat(record["created"])).days > limit


def decode(raw, day, limit):
    """Structural validation. The duration policy is applied per record by ``disposition`` so that a lowered
    PCBAI_WAIVER_MAX_DAYS never locks the whole file: such records stay readable and can be deleted."""
    try:
        if len(raw) > MAX_BYTES:
            raise ValueError("Waiver file exceeds the size limit")
        payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=_constant)
        if (not isinstance(payload, dict) or set(payload) != {"version", "waivers"}
                or type(payload["version"]) is not int or payload["version"] != 1
                or not isinstance(payload["waivers"], list) or len(payload["waivers"]) > MAX_RECORDS):
            raise ValueError("Invalid waiver envelope")
        identities = set()
        for record in payload["waivers"]:
            validate_record(record, day, None)
            if record["finding_id"] in identities:
                raise ValueError("Duplicate finding waiver")
            identities.add(record["finding_id"])
        return payload
    except (ValueError, UnicodeError, RecursionError, PcbAiError) as exc:
        raise PcbAiError("invalid_waivers", "Waiver data is invalid; it cannot certify checks or be overwritten") from exc


def read(root, day=None, limit=None):
    day = today() if day is None else day
    limit = max_days() if limit is None else limit
    path = within(root, FILE, must_exist=False)
    if not path.exists():
        return dict(version=1, waivers=[]), b"", day, limit
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError as exc:
        raise PcbAiError("invalid_waivers", "Cannot read the waiver file") from exc
    return decode(raw, day, limit), raw, day, limit


def raw_bytes(root):
    """Current sidecar bytes without validation (b"" when absent); bounded like ``read``."""
    path = within(root, FILE, must_exist=False)
    if not path.exists():
        return b""
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
    except OSError as exc:
        raise PcbAiError("invalid_waivers", "Cannot read the waiver file") from exc
    if len(raw) > MAX_BYTES:
        raise PcbAiError("invalid_waivers", "Waiver file exceeds the size limit")
    return raw


def disposition(findings, payload, day, limit=None):
    """Preserve exact IDs and multiplicity; never renormalize one finding at a time."""
    limit = max_days() if limit is None else limit
    exceeded = [dict(r) for r in payload["waivers"] if exceeds(r, limit)]
    records = {r["finding_id"]: r for r in payload["waivers"] if not exceeds(r, limit)}
    found = {f["finding_id"] for f in findings}
    active, waived = [], []
    for finding in findings:
        record = records.get(finding["finding_id"])
        if record and date.fromisoformat(record["expires"]) > day:
            waived.append(dict(finding=copy.deepcopy(finding), waiver=dict(record)))
        else:
            active.append(copy.deepcopy(finding))
    expired = [dict(r) for r in payload["waivers"] if date.fromisoformat(r["expires"]) <= day]
    orphaned = [dict(r) for r in payload["waivers"] if r["finding_id"] not in found]
    warnings = (["waiver_expired: " + r["finding_id"] for r in expired]
                + ["waiver_orphaned_in_scope: " + r["finding_id"] for r in orphaned]
                + [f"waiver_policy_exceeded: {r['finding_id']} (> {limit} days; delete or renew it)" for r in exceeded])
    return dict(active_findings=active, waived=waived, expired_waivers=expired,
                orphaned_waivers=orphaned, policy_exceeded_waivers=exceeded, next_waiver_expiry=min(
                    (r["waiver"]["expires"] for r in waived), default=None), waiver_warnings=warnings)


class Waivers:
    def __init__(self, state, history):
        self.state, self.history, self.previews = state, history, {}
        self.lock = threading.RLock()

    def get(self, session):
        payload, raw, day, limit = read(session.root)
        return dict(payload, waivers_revision=digest(raw), evaluated_on=day.isoformat(), max_days=limit,
                    policy_exceeded=[r["finding_id"] for r in payload["waivers"] if exceeds(r, limit)])

    def preview(self, session, target, args, *, delete=False, restore=False):
        with self.lock:
            if restore:
                return self._preview_restore(session, target, args)
            return self._preview(session, target, args, delete=delete)

    def _preview_restore(self, session, target, args):
        """Whole-file restore from a waiver checkpoint. Works on a corrupt current file: that is when it is needed."""
        raw = raw_bytes(session.root)
        if digest(raw) != args["waivers_revision"]:
            raise PcbAiError("stale_waivers", "Waivers changed; refresh and preview again")
        data = self.history.read(args.get("checkpoint_id"), session.id, FILE)
        day, limit = today(), max_days()
        if data:
            decode(data, day, limit)
        return self._store(target, raw, data, "restore", None, limit,
                           dict(checkpoint_id=args["checkpoint_id"], removes_file=not data))

    def _store(self, target, raw, data, operation, record, limit, extra=None):
        self.previews = {k: v for k, v in self.previews.items() if v["expires"] > time.monotonic()}
        if len(self.previews) >= 100:
            raise PcbAiError("too_many_candidates", "Too many waiver previews")
        candidate = "waiver-" + secrets.token_hex(16)
        self.previews[candidate] = dict(target=dict(target), before=digest(raw), data=data,
            operation=operation, record=copy.deepcopy(record), limit=limit, expires=time.monotonic() + 900)
        return dict(candidate_id=candidate, mode="preview", waiver=record, file=FILE,
                    waivers_revision=digest(raw), after_sha256=digest(data), would_change=raw != data, **(extra or {}))

    def _preview(self, session, target, args, *, delete=False):
        payload, raw, day, limit = read(session.root)
        if digest(raw) != args["waivers_revision"]:
            raise PcbAiError("stale_waivers", "Waivers changed; refresh and preview again")
        if delete:
            identity = args.get("finding_id")
            if not identity or not any(r["finding_id"] == identity for r in payload["waivers"]):
                raise PcbAiError("unknown_waiver", "Select an existing exact finding waiver")
            record = None
        else:
            record = args.get("waiver")
            try:
                validate_record(record, day, limit, active=True)
            except (ValueError, TypeError, PcbAiError) as exc:
                raise PcbAiError("invalid_waivers", "New waiver requires an exact ID, owner, reason and valid dates") from exc
            identity = record["finding_id"]
        records = [r for r in payload["waivers"] if r["finding_id"] != identity]
        if record:
            records.append(dict(record))
        data = json.dumps(dict(version=1, waivers=sorted(records, key=lambda r: r["finding_id"])),
                          ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")
        decode(data, day, limit)
        return self._store(target, raw, data, "delete" if delete else "set", record, limit)

    def apply(self, session, target, args, *, delete=False, restore=False):
        with self.lock:
            return self._apply(session, target, args, operation="restore" if restore else "delete" if delete else "set")

    def _apply(self, session, target, args, *, operation):
        if set(args) - {"session", "document", "revision", "mode", "candidate_id", "waivers_revision"}:
            raise PcbAiError("invalid_arguments", "Apply accepts only the preview identity and revisions")
        candidate = self.previews.get(args.get("candidate_id"))
        if not candidate or candidate["expires"] <= time.monotonic():
            raise PcbAiError("invalid_candidate", "Waiver preview is missing or expired")
        if candidate["target"] != target or candidate["operation"] != operation:
            raise PcbAiError("wrong_target", "Waiver preview belongs to another operation, session or revision")
        with write_lock(session.root, self.state):
            assert_closed(session.root)
            session.validate(target["document"], target["revision"])
            if operation == "restore":
                raw, day, limit = raw_bytes(session.root), today(), max_days()
            else:
                _, raw, day, limit = read(session.root)
            if digest(raw) != candidate["before"] or digest(raw) != args["waivers_revision"]:
                raise PcbAiError("stale_waivers", "Waivers changed since preview")
            if limit != candidate["limit"]:
                raise PcbAiError("stale_waivers", "Waiver duration policy changed; preview again")
            if candidate["data"]:
                decode(candidate["data"], day, limit)
            if candidate["record"]:
                try:
                    validate_record(candidate["record"], day, limit, active=True)
                except (ValueError, PcbAiError) as exc:
                    raise PcbAiError("invalid_waivers", "Previewed waiver is now expired or invalid") from exc
            path = within(session.root, FILE, must_exist=False)
            session.validate(target["document"], target["revision"])
            # Re-resolve and check the sidecar immediately before the checkpoint/write.
            if (path.read_bytes() if path.exists() else b"") != raw:
                raise PcbAiError("stale_waivers", "Waivers changed before checkpoint")
            cp = self.history.checkpoint(session.id, FILE, raw, target["revision"], "Waiver policy edit")
            if candidate["data"]:
                atomic_write(path, candidate["data"])
            elif path.exists():
                path.unlink()  # the checkpoint was taken before the file existed
            self.previews.pop(args["candidate_id"], None)
            updated = None
            try:
                updated = session.target(target["document"])
                matches = raw_bytes(session.root) == candidate["data"]
            except (OSError, PcbAiError):
                matches = False
            return dict(target=updated, target_before=target, checkpoint=cp,
                        before_file_exists=bool(raw), waivers_revision=digest(candidate["data"]),
                        changed=True, file=FILE, waiver=candidate["record"], readback_matches=matches)
