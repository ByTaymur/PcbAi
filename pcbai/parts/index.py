"""Private SQLite FTS5 metadata index. Queries and library text remain data."""
import json
import re
import sqlite3
import threading
from contextlib import closing

from pcbai.core.contract import PcbAiError
from pcbai.kicad.files import within
from pcbai.kicad.files import digest
from pcbai.permissions import assert_unlinked
from pcbai.parts.library import read_metadata, roots
from pcbai.sch.model import properties


class PartIndex:
    def __init__(self, state):
        self.path = state / "parts-index.sqlite"
        self.lock = threading.RLock()
        self.warnings = []

    def ensure(self):
        for path in (self.path, *(self.path.with_name(self.path.name + s) for s in ("-journal", "-wal", "-shm"))):
            assert_unlinked(path)
        symbol_root, _ = roots()
        files = sorted(symbol_root.glob("*.kicad_sym"))
        if not files:
            raise PcbAiError("missing_dependency", "KiCad symbol libraries are not installed/configured")
        inputs = []
        for file in files:
            path = within(symbol_root, file.name)
            if path.stat().st_size > 64 * 1024 * 1024:
                raise PcbAiError("invalid_library", "Library is too large")
            inputs.append((path, digest(path.read_bytes())))
        manifest = json.dumps([(str(path), sha) for path, sha in inputs])
        with closing(sqlite3.connect(self.path, timeout=30)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            cached = db.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()
            if cached and cached[0] == manifest:
                saved = db.execute("SELECT value FROM meta WHERE key='warnings'").fetchone()
                self.warnings = json.loads(saved[0]) if saved else []
                return
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS parts USING fts5(id UNINDEXED, name, description, keywords, metadata UNINDEXED)")
            db.execute("DELETE FROM parts")
            warnings = []
            for file, sha in inputs:
                data, nodes = read_metadata(file)
                if digest(data) != sha:
                    raise PcbAiError("stale_library", "Library changed while rebuilding the index; search again")
                rows = []
                metadata_cache = {}
                def inherited(key, seen=(), entries=nodes, cache=metadata_cache):
                    if key in seen or len(seen) >= 16 or key not in entries:
                        raise PcbAiError("invalid_library", "Metadata inheritance is missing, cyclic or too deep")
                    if key in cache:
                        return cache[key]
                    entry = entries[key]
                    parent = entry.child("extends")
                    parent_props, depth = inherited(parent.value(), (*seen, key)) if parent else ({}, 0)
                    if depth >= 16:
                        raise PcbAiError("invalid_library", "Metadata inheritance is too deep")
                    props = dict(parent_props)
                    props.update(properties(entry))
                    cache[key] = (props, depth + 1)
                    return cache[key]
                for name in nodes:
                    identifier = file.stem + ":" + name
                    try:
                        props, _ = inherited(name)
                    except PcbAiError as exc:
                        warnings.append(dict(lib_id=identifier, code=exc.code, reason=str(exc)))
                        continue
                    metadata = dict(lib_id=identifier, footprint=props.get("Footprint", ""),
                                    datasheet=props.get("Datasheet", ""), source="kicad", trusted=False,
                                    library_sha256=sha)
                    rows.append((identifier, name, props.get("Description", ""), props.get("ki_keywords", ""), json.dumps(metadata)))
                db.executemany("INSERT INTO parts VALUES(?,?,?,?,?)", rows)
            db.execute("INSERT OR REPLACE INTO meta VALUES('manifest',?)", (manifest,))
            db.execute("INSERT OR REPLACE INTO meta VALUES('warnings',?)", (json.dumps(warnings),))
            self.warnings = warnings

    def search(self, text, limit=20):
        if not isinstance(text, str) or not 1 <= len(text) <= 512:
            raise PcbAiError("invalid_arguments", "Search text must contain 1–512 characters")
        tokens = re.findall(r"\w+(?:[.-]\w+)*", text, flags=re.UNICODE)
        if not tokens or len(tokens) > 32 or not 1 <= limit <= 100:
            raise PcbAiError("invalid_arguments", "Use 1–32 search terms and limit 1–100")
        query = " AND ".join('"' + t.replace('"', '""') + '"' + ("*" if not t[0].isdigit() else "") for t in tokens)
        with self.lock:
            self.ensure()
            with closing(sqlite3.connect(self.path, timeout=30)) as db:
                rows = db.execute("SELECT id,name,description,metadata FROM parts WHERE parts MATCH ? ORDER BY rank,id LIMIT ?",
                                  (query, limit)).fetchall()
        return [dict(json.loads(metadata), name=name, description=description) for _, name, description, metadata in rows]
