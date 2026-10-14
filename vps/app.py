#!/usr/bin/env python3
"""Workout Tracker - standalone server for VPS.
Stdlib only (no pip dependencies). SQLite storage.

Run:  python3 app.py            (PORT env, default 8000)
Auth: Bearer token from WORKOUT_TOKEN env, or .token file in working dir
      (auto-generated on first run if missing).
"""
import json
import os
import re
import secrets
import sqlite3
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "workout.db")
TOKEN_PATH = os.path.join(BASE_DIR, ".token")

PORT = int(os.environ.get("PORT", "8000"))


def get_token():
    tok = os.environ.get("WORKOUT_TOKEN")
    if tok:
        return tok.strip()
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            return f.read().strip()
    tok = secrets.token_urlsafe(24)
    with open(TOKEN_PATH, "w") as f:
        f.write(tok)
    os.chmod(TOKEN_PATH, 0o600)
    print("Generated new login token, saved to .token")
    return tok


TOKEN = get_token()


def get_password():
    pw = os.environ.get("WORKOUT_PASSWORD")
    if pw and pw.strip():
        return pw.strip()
    pp = os.path.join(BASE_DIR, ".password")
    if os.path.exists(pp):
        with open(pp) as f:
            pw = f.read().strip()
            return pw or None
    return None


PASSWORD = get_password()
if PASSWORD:
    print("Password login aktif (dari WORKOUT_PASSWORD/.password)")
DB_LOCK = threading.Lock()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS session_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id INTEGER NOT NULL REFERENCES session_exercises(id) ON DELETE CASCADE,
    set_no INTEGER NOT NULL,
    weight REAL NOT NULL DEFAULT 0,
    reps INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS template_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sets INTEGER NOT NULL DEFAULT 3,
    reps_min INTEGER,
    reps_max INTEGER,
    weight_min REAL,
    weight_max REAL,
    note TEXT DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0
);
"""


def seed():
    """Seed today's chest session + templates on a fresh database."""
    with DB_LOCK, db() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
        m = conn.execute("SELECT COUNT(*) c FROM templates").fetchone()["c"]
        if n or m:
            return
        today = date.today().isoformat()
        cur = conn.execute(
            "INSERT INTO sessions (date, name) VALUES (?, ?)", (today, "Chest")
        )
        sid = cur.lastrowid
        chest = [
            ("Smith Machine Bench Press", [(10, 6), (15, 7), (15, 8), (20, 6)]),
            ("Smith Machine Incline Press", [(10, 8), (10, 7), (10, 7), (15, 2)]),
            ("Pec Deck", [(12, 6), (16, 8), (20, 6), (16, 13)]),
        ]
        for pos, (ename, sets) in enumerate(chest):
            cur = conn.execute(
                "INSERT INTO session_exercises (session_id, name, position) VALUES (?, ?, ?)",
                (sid, ename, pos),
            )
            eid = cur.lastrowid
            for i, (w, r) in enumerate(sets, 1):
                conn.execute(
                    "INSERT INTO sets (exercise_id, set_no, weight, reps) VALUES (?, ?, ?, ?)",
                    (eid, i, w, r),
                )
        templates = [
            ("Chest", [
                ("Smith Machine Bench Press", 4, 6, 10, 10, 20, ""),
                ("Smith Machine Incline Press", 4, 7, 8, 10, 15, ""),
                ("Pec Deck", 4, 6, 13, 12, 20, ""),
            ]),
            ("Back", [
                ("Lat Pulldown", 4, 8, 10, 35, 40, ""),
                ("Seated Cable Row", 4, 8, 10, 30, 35, ""),
                ("One-arm Dumbbell Row", 3, 8, 10, 14, 16, "per sisi"),
                ("Straight-arm Cable Pulldown", 3, 10, 12, 15, 20, ""),
                ("Back Extension", 2, 12, 15, 0, 0, "bodyweight"),
            ]),
            ("Kaki", []),
            ("Bahu", []),
            ("Lengan", []),
        ]
        for tpos, (tname, exs) in enumerate(templates):
            cur = conn.execute(
                "INSERT INTO templates (name, position) VALUES (?, ?)", (tname, tpos)
            )
            tid = cur.lastrowid
            for epos, (ename, ns, rmin, rmax, wmin, wmax, note) in enumerate(exs):
                conn.execute(
                    """INSERT INTO template_exercises
                       (template_id, name, sets, reps_min, reps_max, weight_min, weight_max, note, position)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (tid, ename, ns, rmin, rmax, wmin, wmax, note, epos),
                )
        conn.commit()
        print(f"Seeded DB: chest session {today} + 5 templates")


def row_to_dict(r):
    return dict(r) if r is not None else None


# ---------------- API helpers ----------------

def session_summary(conn, s):
    exs = conn.execute(
        "SELECT id FROM session_exercises WHERE session_id = ? ORDER BY position", (s["id"],)
    ).fetchall()
    n_ex = len(exs)
    vol = 0
    for e in exs:
        v = conn.execute(
            "SELECT COALESCE(SUM(weight * reps), 0) v FROM sets WHERE exercise_id = ?",
            (e["id"],),
        ).fetchone()["v"]
        vol += v or 0
    d = row_to_dict(s)
    d["exercises"] = n_ex
    d["volume"] = vol
    return d


def session_detail(conn, sid):
    s = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if not s:
        return None
    d = row_to_dict(s)
    exs = conn.execute(
        "SELECT * FROM session_exercises WHERE session_id = ? ORDER BY position", (sid,)
    ).fetchall()
    out = []
    for e in exs:
        ed = row_to_dict(e)
        ed["sets"] = [
            row_to_dict(r)
            for r in conn.execute(
                "SELECT * FROM sets WHERE exercise_id = ? ORDER BY set_no", (e["id"],)
            ).fetchall()
        ]
        out.append(ed)
    d["exercises"] = out
    return d


def template_detail(conn, t):
    d = row_to_dict(t)
    d["exercises"] = [
        row_to_dict(r)
        for r in conn.execute(
            "SELECT * FROM template_exercises WHERE template_id = ? ORDER BY position",
            (t["id"],),
        ).fetchall()
    ]
    return d


# ---------------- HTTP handler ----------------

class Handler(BaseHTTPRequestHandler):
    server_version = "WorkoutTracker/1.0"

    def log_message(self, *a):
        pass  # quiet; systemd journal keeps stdout anyway

    def _send(self, code, obj=None, ctype="application/json"):
        body = b"" if obj is None else (
            obj.encode() if isinstance(obj, str) else json.dumps(obj).encode()
        )
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw) if raw else {}
        except (ValueError, json.JSONDecodeError):
            return None

    def _auth_ok(self):
        auth = self.headers.get("Authorization", "")
        if auth == "Bearer %s" % TOKEN:
            return True
        return bool(PASSWORD) and auth == "Bearer %s" % PASSWORD

    def _route(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # Static UI (no auth needed to load the page; API enforces auth)
        if self.command == "GET" and path == "/":
            with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                html = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        if self.command == "GET" and path == "/api/ping":
            self._send(200, {"ok": True})
            return

        if not path.startswith("/api/"):
            self._send(404, {"error": "not found"})
            return
        if not self._auth_ok():
            self._send(401, {"error": "unauthorized"})
            return

        body = self._body() if self.command in ("POST", "PUT", "PATCH") else {}
        if body is None:
            self._send(400, {"error": "bad json"})
            return

        with DB_LOCK, db() as conn:
            try:
                result = self._api(conn, self.command, path, qs, body)
            except ValueError as e:
                self._send(400, {"error": str(e)})
                return
            except Exception as e:
                # Never drop the connection silently: report server errors as JSON.
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})
                except Exception:
                    pass
                return
            if result is None:
                self._send(404, {"error": "not found"})
                return
            code, obj = result
            conn.commit()
            self._send(code, obj)

    def _api(self, conn, method, path, qs, body):
        m_id = re.match(r"^/api/sessions/(\d+)$", path)
        m_ex = re.match(r"^/api/sessions/(\d+)/exercises$", path)
        m_st = re.match(r"^/api/templates/(\d+)/start-from-template$", path)
        m_eid = re.match(r"^/api/exercises/(\d+)$", path)
        m_esets = re.match(r"^/api/exercises/(\d+)/sets$", path)
        m_set = re.match(r"^/api/sets/(\d+)$", path)
        m_tpl = re.match(r"^/api/templates/(\d+)$", path)
        m_tpex = re.match(r"^/api/templates/(\d+)/exercises$", path)
        m_tpe = re.match(r"^/api/template-exercises/(\d+)$", path)

        # ---- sessions ----
        if path == "/api/sessions" and method == "GET":
            rows = conn.execute("SELECT * FROM sessions ORDER BY date DESC, id DESC").fetchall()
            return 200, [session_summary(conn, s) for s in rows]
        if path == "/api/sessions" and method == "POST":
            name = (body.get("name") or "Workout").strip() or "Workout"
            sdate = body.get("date") or date.today().isoformat()
            cur = conn.execute(
                "INSERT INTO sessions (date, name, notes) VALUES (?, ?, ?)",
                (sdate, name, body.get("notes", "")),
            )
            return 201, session_detail(conn, cur.lastrowid)
        if m_id and method == "GET":
            d = session_detail(conn, int(m_id.group(1)))
            return (200, d) if d else None
        if m_id and method == "DELETE":
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (int(m_id.group(1)),))
            return (204, None) if cur.rowcount else None
        if m_ex and method == "POST":
            sid = int(m_ex.group(1))
            if not conn.execute("SELECT 1 FROM sessions WHERE id = ?", (sid,)).fetchone():
                return None
            name = (body.get("name") or "").strip()
            if not name:
                raise ValueError("nama gerakan wajib diisi")
            pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 p FROM session_exercises WHERE session_id = ?",
                (sid,),
            ).fetchone()["p"]
            cur = conn.execute(
                "INSERT INTO session_exercises (session_id, name, position) VALUES (?, ?, ?)",
                (sid, name, pos),
            )
            return 201, row_to_dict(
                conn.execute("SELECT * FROM session_exercises WHERE id = ?", (cur.lastrowid,)).fetchone()
            )
        if m_eid and method == "DELETE":
            cur = conn.execute("DELETE FROM session_exercises WHERE id = ?", (int(m_eid.group(1)),))
            return (204, None) if cur.rowcount else None
        if m_esets and method == "POST":
            eid = int(m_esets.group(1))
            if not conn.execute("SELECT 1 FROM session_exercises WHERE id = ?", (eid,)).fetchone():
                return None
            sno = conn.execute(
                "SELECT COALESCE(MAX(set_no), 0) + 1 n FROM sets WHERE exercise_id = ?", (eid,)
            ).fetchone()["n"]
            cur = conn.execute(
                "INSERT INTO sets (exercise_id, set_no, weight, reps, failed) VALUES (?, ?, ?, ?, ?)",
                (eid, sno, float(body.get("weight", 0) or 0), int(body.get("reps", 0) or 0),
                 1 if body.get("failed") else 0),
            )
            return 201, row_to_dict(
                conn.execute("SELECT * FROM sets WHERE id = ?", (cur.lastrowid,)).fetchone()
            )
        if m_set and method == "PUT":
            sid_ = int(m_set.group(1))
            cur = conn.execute(
                "UPDATE sets SET weight = ?, reps = ?, failed = ? WHERE id = ?",
                (float(body.get("weight", 0) or 0), int(body.get("reps", 0) or 0),
                 1 if body.get("failed") else 0, sid_),
            )
            if not cur.rowcount:
                return None
            return 200, row_to_dict(
                conn.execute("SELECT * FROM sets WHERE id = ?", (sid_,)).fetchone()
            )
        if m_set and method == "DELETE":
            cur = conn.execute("DELETE FROM sets WHERE id = ?", (int(m_set.group(1)),))
            return (204, None) if cur.rowcount else None

        # ---- templates ----
        if path == "/api/templates" and method == "GET":
            rows = conn.execute("SELECT * FROM templates ORDER BY position").fetchall()
            return 200, [template_detail(conn, t) for t in rows]
        if path == "/api/templates" and method == "POST":
            name = (body.get("name") or "").strip()
            if not name:
                raise ValueError("nama template wajib diisi")
            pos = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 p FROM templates").fetchone()["p"]
            cur = conn.execute("INSERT INTO templates (name, position) VALUES (?, ?)", (name, pos))
            return 201, template_detail(conn, conn.execute(
                "SELECT * FROM templates WHERE id = ?", (cur.lastrowid,)).fetchone())
        if m_tpl and method == "PUT":
            tid = int(m_tpl.group(1))
            name = (body.get("name") or "").strip()
            if not name:
                raise ValueError("nama template wajib diisi")
            cur = conn.execute("UPDATE templates SET name = ? WHERE id = ?", (name, tid))
            if not cur.rowcount:
                return None
            return 200, template_detail(conn, conn.execute(
                "SELECT * FROM templates WHERE id = ?", (tid,)).fetchone())
        if m_tpl and method == "DELETE":
            cur = conn.execute("DELETE FROM templates WHERE id = ?", (int(m_tpl.group(1)),))
            return (204, None) if cur.rowcount else None
        if m_tpex and method == "POST":
            tid = int(m_tpex.group(1))
            if not conn.execute("SELECT 1 FROM templates WHERE id = ?", (tid,)).fetchone():
                return None
            name = (body.get("name") or "").strip()
            if not name:
                raise ValueError("nama gerakan wajib diisi")
            pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 p FROM template_exercises WHERE template_id = ?",
                (tid,),
            ).fetchone()["p"]
            cur = conn.execute(
                """INSERT INTO template_exercises
                   (template_id, name, sets, reps_min, reps_max, weight_min, weight_max, note, position)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tid, name, int(body.get("sets", 3) or 3),
                 body.get("reps_min"), body.get("reps_max"),
                 body.get("weight_min"), body.get("weight_max"),
                 body.get("note", ""), pos),
            )
            return 201, row_to_dict(conn.execute(
                "SELECT * FROM template_exercises WHERE id = ?", (cur.lastrowid,)).fetchone())
        if m_tpe and method == "PUT":
            teid = int(m_tpe.group(1))
            cols = ("name", "sets", "reps_min", "reps_max", "weight_min", "weight_max", "note")
            vals = [body.get(c) for c in cols]
            if vals[0] is not None and not str(vals[0]).strip():
                raise ValueError("nama gerakan wajib diisi")
            cur = conn.execute(
                """UPDATE template_exercises SET name=?, sets=?, reps_min=?, reps_max=?,
                   weight_min=?, weight_max=?, note=? WHERE id=?""",
                (*vals, teid),
            )
            if not cur.rowcount:
                return None
            return 200, row_to_dict(conn.execute(
                "SELECT * FROM template_exercises WHERE id = ?", (teid,)).fetchone())
        if m_tpe and method == "DELETE":
            cur = conn.execute("DELETE FROM template_exercises WHERE id = ?", (int(m_tpe.group(1)),))
            return (204, None) if cur.rowcount else None
        if m_st and method == "POST":
            tid = int(m_st.group(1))
            t = conn.execute("SELECT * FROM templates WHERE id = ?", (tid,)).fetchone()
            if not t:
                return None
            cur = conn.execute(
                "INSERT INTO sessions (date, name) VALUES (?, ?)",
                (date.today().isoformat(), t["name"]),
            )
            sid = cur.lastrowid
            exs = conn.execute(
                "SELECT * FROM template_exercises WHERE template_id = ? ORDER BY position", (tid,)
            ).fetchall()
            for epos, e in enumerate(exs):
                conn.execute(
                    "INSERT INTO session_exercises (session_id, name, position) VALUES (?, ?, ?)",
                    (sid, e["name"], epos),
                )
            return 201, session_detail(conn, sid)

        # ---- progress ----
        if path == "/api/progress" and method == "GET":
            name = (qs.get("name", [""])[0] or "").strip()
            if not name:
                # distinct exercise names for the picker
                rows = conn.execute(
                    "SELECT DISTINCT name FROM session_exercises ORDER BY name"
                ).fetchall()
                return 200, {"names": [r["name"] for r in rows], "points": []}
            rows = conn.execute(
                """SELECT s.date AS d, st.weight, st.reps
                   FROM sets st
                   JOIN session_exercises se ON se.id = st.exercise_id
                   JOIN sessions s ON s.id = se.session_id
                   WHERE se.name = ?
                   ORDER BY s.date, s.id, st.set_no""",
                (name,),
            ).fetchall()
            by_date = {}
            for r in rows:
                p = by_date.setdefault(r["d"], {"max_weight": 0, "max_reps": 0, "volume": 0})
                p["max_weight"] = max(p["max_weight"], r["weight"] or 0)
                p["max_reps"] = max(p["max_reps"], r["reps"] or 0)
                p["volume"] += (r["weight"] or 0) * (r["reps"] or 0)
            points = [{"date": d, **v} for d, v in sorted(by_date.items())]
            return 200, {"names": [], "points": points}

        return None

    do_GET = _route
    do_POST = _route
    do_PUT = _route
    do_DELETE = _route


def main():
    with DB_LOCK, db() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    seed()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Workout Tracker listening on 0.0.0.0:{PORT}")
    print(f"DB: {DB_PATH}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
