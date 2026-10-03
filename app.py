from datetime import date, datetime
from pathlib import Path
import sqlite3

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DB_PATH = Path(__file__).with_name("attendance.db")

STUDENTS = {
    "C3:9F:43:07": "Purva",
    "36:4D:44:07": "Sejal",
    "D5:A3:43:07": "Dhanashree",
    "93:11:00:35": "Siddhi",
}


def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize_db():
    with connect_db() as db:
        db.execute("CREATE TABLE IF NOT EXISTS students (uid TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE)")

        old_sessions = []
        old_attendance = []
        columns = set()
        session_table = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='class_sessions'"
        ).fetchone()
        if session_table:
            columns = {row["name"] for row in db.execute("PRAGMA table_info(class_sessions)")}
            if "id" not in columns:
                # Upgrade the previous one-class-per-day database without losing its records.
                old_sessions = db.execute("SELECT class_date, created_at FROM class_sessions").fetchall()
                old_attendance = db.execute(
                    "SELECT class_date, uid, marked_at FROM attendance"
                ).fetchall()
                db.execute("DROP TABLE attendance")
                db.execute("DROP TABLE class_sessions")
                session_table = None

        if not session_table or "id" not in columns:
            db.execute("""
                CREATE TABLE class_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_date TEXT NOT NULL,
                    session_number INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (class_date, session_number)
                )
            """)
            db.execute("""
                CREATE TABLE attendance (
                    class_id INTEGER NOT NULL,
                    uid TEXT NOT NULL,
                    marked_at TEXT NOT NULL,
                    PRIMARY KEY (class_id, uid),
                    FOREIGN KEY (class_id) REFERENCES class_sessions(id),
                    FOREIGN KEY (uid) REFERENCES students(uid)
                )
            """)
            if old_sessions:
                for session in old_sessions:
                    db.execute(
                        "INSERT INTO class_sessions (class_date, session_number, created_at) VALUES (?, 1, ?)",
                        (session["class_date"], session["created_at"]),
                    )
                for record in old_attendance:
                    session = db.execute(
                        "SELECT id FROM class_sessions WHERE class_date = ? AND session_number = 1",
                        (record["class_date"],),
                    ).fetchone()
                    if session:
                        db.execute(
                            "INSERT OR IGNORE INTO attendance (class_id, uid, marked_at) VALUES (?, ?, ?)",
                            (session["id"], record["uid"], record["marked_at"]),
                        )
        db.executemany(
            "INSERT OR IGNORE INTO students (uid, name) VALUES (?, ?)",
            [(uid, name) for uid, name in STUDENTS.items()],
        )


@app.get("/")
def dashboard():
    initialize_db()
    with connect_db() as db:
        sessions = db.execute(
            "SELECT id, class_date, session_number FROM class_sessions "
            "ORDER BY class_date DESC, session_number DESC"
        ).fetchall()
        total_classes = len(sessions)
        students = db.execute("SELECT uid, name FROM students ORDER BY name").fetchall()
        summary = []
        for student in students:
            attended = db.execute("SELECT COUNT(*) FROM attendance WHERE uid = ?",
                                  (student["uid"],)).fetchone()[0]
            percent = round(attended * 100 / total_classes, 1) if total_classes else 0
            summary.append({"name": student["name"], "attended": attended,
                            "total": total_classes, "percent": percent})
        recent = []
        for session in sessions:
            names = db.execute(
                "SELECT s.name FROM attendance a JOIN students s USING(uid) "
                "WHERE a.class_id = ? ORDER BY s.name", (session["id"],)
            ).fetchall()
            recent.append({"date": session["class_date"],
                           "number": session["session_number"],
                           "present": ", ".join(row["name"] for row in names) or "None"})
    return render_template("index.html", summary=summary, sessions=recent,
                           today=date.today().isoformat(), total_classes=total_classes)


@app.post("/api/class/start")
def start_class():
    initialize_db()
    class_date = date.today().isoformat()
    with connect_db() as db:
        number = db.execute(
            "SELECT COALESCE(MAX(session_number), 0) + 1 FROM class_sessions WHERE class_date = ?",
            (class_date,),
        ).fetchone()[0]
        db.execute(
            "INSERT INTO class_sessions (class_date, session_number, created_at) VALUES (?, ?, ?)",
            (class_date, number, datetime.now().isoformat(timespec="seconds")),
        )
    return jsonify(ok=True, date=class_date, session=number,
                   message=f"Class {number} started for today.")


@app.post("/api/scan")
def scan():
    initialize_db()
    data = request.get_json(silent=True) or {}
    uid = str(data.get("uid", "")).strip().upper().replace("-", ":")
    if uid not in STUDENTS:
        print(f"Rejected unknown RFID UID: {uid or '(empty)'}", flush=True)
        return jsonify(ok=False, message="Unknown card."), 404

    class_date = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    with connect_db() as db:
        # If no class was started yet today, create the first one automatically.
        session = db.execute(
            "SELECT id, session_number FROM class_sessions WHERE class_date = ? "
            "ORDER BY session_number DESC LIMIT 1", (class_date,)
        ).fetchone()
        if session is None:
            db.execute(
                "INSERT INTO class_sessions (class_date, session_number, created_at) VALUES (?, 1, ?)",
                (class_date, now),
            )
            session = db.execute(
                "SELECT id, session_number FROM class_sessions WHERE class_date = ? AND session_number = 1",
                (class_date,),
            ).fetchone()
        result = db.execute(
            "INSERT OR IGNORE INTO attendance (class_id, uid, marked_at) VALUES (?, ?, ?)",
            (session["id"], uid, now),
        )
    duplicate = result.rowcount == 0
    if duplicate:
        print(f"Duplicate scan: {STUDENTS[uid]}, {class_date}, class {session['session_number']}", flush=True)
    else:
        print(f"Attendance saved: {STUDENTS[uid]}, {class_date}, class {session['session_number']}", flush=True)
    return jsonify(ok=True, name=STUDENTS[uid], date=class_date,
                   session=session["session_number"],
                   duplicate=duplicate,
                   message=(f"Already marked for class {session['session_number']}." if duplicate
                            else f"Attendance marked for class {session['session_number']}."))


if __name__ == "__main__":
    initialize_db()
    # Accessible to devices on the same Wi-Fi. Keep this server on a trusted network.
    app.run(host="0.0.0.0", port=5000, debug=False)
