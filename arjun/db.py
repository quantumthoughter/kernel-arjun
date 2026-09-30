from __future__ import annotations

import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def ensure_database(dsn: str) -> None:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    dbname = info.get("dbname", "arjun")
    admin = dict(info)
    admin["dbname"] = "postgres"
    admin_dsn = psycopg.conninfo.make_conninfo(**admin)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        cur = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if cur.fetchone() is None:
            conn.execute(f'CREATE DATABASE "{dbname}"')


class DB:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    def init_schema(self) -> None:
        self.conn.execute(SCHEMA_PATH.read_text())

    def close(self) -> None:
        self.conn.close()

    # ---- goals ----

    def create_goal(self, title: str, dod: str, workspace: str, meta: dict | None = None) -> int:
        row = self.conn.execute(
            "INSERT INTO goals (title, dod, workspace, meta) VALUES (%s, %s, %s, %s) RETURNING id",
            (title, dod, workspace, json.dumps(meta or {})),
        ).fetchone()
        return row["id"]

    def get_goal(self, goal_id: int) -> dict | None:
        return self.conn.execute("SELECT * FROM goals WHERE id = %s", (goal_id,)).fetchone()

    def set_goal_status(self, goal_id: int, status: str) -> None:
        self.conn.execute(
            "UPDATE goals SET status = %s, updated_at = now() WHERE id = %s", (status, goal_id)
        )

    def list_goals(self, limit: int = 20) -> list[dict]:
        return self.conn.execute(
            "SELECT id, title, status, created_at FROM goals ORDER BY id DESC LIMIT %s", (limit,)
        ).fetchall()

    # ---- tasks ----

    def add_tasks(self, goal_id: int, tasks: list[dict], start_seq: int = 0) -> None:
        with self.conn.cursor() as cur:
            for i, t in enumerate(tasks, start=start_seq + 1):
                cur.execute(
                    "INSERT INTO tasks (goal_id, seq, title, detail) VALUES (%s, %s, %s, %s)",
                    (goal_id, i, str(t.get("title", "task")), str(t.get("detail", ""))),
                )

    def get_tasks(self, goal_id: int) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE goal_id = %s ORDER BY seq", (goal_id,)
        ).fetchall()

    def next_open_task(self, goal_id: int) -> dict | None:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE goal_id = %s AND status IN ('pending', 'running') "
            "ORDER BY seq LIMIT 1",
            (goal_id,),
        ).fetchone()

    def set_task_status(self, task_id: int, status: str, verify_note: str = "") -> None:
        self.conn.execute(
            "UPDATE tasks SET status = %s, verify_note = %s, updated_at = now() WHERE id = %s",
            (status, verify_note, task_id),
        )

    def reset_running_tasks(self, goal_id: int) -> None:
        self.conn.execute(
            "UPDATE tasks SET status = 'pending', updated_at = now() "
            "WHERE goal_id = %s AND status = 'running'",
            (goal_id,),
        )

    def task_counts(self, goal_id: int) -> dict:
        rows = self.conn.execute(
            "SELECT status, count(*) AS n FROM tasks WHERE goal_id = %s GROUP BY status",
            (goal_id,),
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    # ---- steps / events ----

    def add_step(
        self,
        goal_id: int,
        task_id: int | None,
        kind: str,
        action: dict,
        result: dict,
        status: str = "ok",
        fingerprint: str = "",
        model: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> int:
        row = self.conn.execute(
            "INSERT INTO steps (goal_id, task_id, kind, action, result, status, fingerprint, model, "
            "tokens_in, tokens_out) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                goal_id,
                task_id,
                kind,
                json.dumps(action),
                json.dumps(result),
                status,
                fingerprint,
                model,
                tokens_in,
                tokens_out,
            ),
        ).fetchone()
        return row["id"]

    def recent_steps(self, goal_id: int, limit: int = 6) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM steps WHERE goal_id = %s ORDER BY id DESC LIMIT %s", (goal_id, limit)
        ).fetchall()
        return list(reversed(rows))

    def count_steps(self, goal_id: int) -> int:
        return self.conn.execute(
            "SELECT count(*) AS n FROM steps WHERE goal_id = %s", (goal_id,)
        ).fetchone()["n"]

    def failed_fingerprints(self, goal_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT fingerprint, count(*) AS n FROM steps "
            "WHERE goal_id = %s AND fingerprint <> '' AND status <> 'ok' GROUP BY fingerprint",
            (goal_id,),
        ).fetchall()
        return {r["fingerprint"]: r["n"] for r in rows}

    def add_event(self, goal_id: int, step_id: int | None, type_: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO events (goal_id, step_id, type, payload) VALUES (%s, %s, %s, %s)",
            (goal_id, step_id, type_, json.dumps(payload)),
        )

    def recent_events(self, goal_id: int, limit: int = 30) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM events WHERE goal_id = %s ORDER BY id DESC LIMIT %s",
            (goal_id, limit),
        ).fetchall()

    # ---- checkpoints / artifacts ----

    def add_checkpoint(
        self, goal_id: int, task_id: int | None, step_id: int | None, working_memory: dict
    ) -> None:
        self.conn.execute(
            "INSERT INTO checkpoints (goal_id, task_id, step_id, working_memory) VALUES (%s, %s, %s, %s)",
            (goal_id, task_id, step_id, json.dumps(working_memory)),
        )

    def latest_checkpoint(self, goal_id: int) -> dict | None:
        return self.conn.execute(
            "SELECT * FROM checkpoints WHERE goal_id = %s ORDER BY id DESC LIMIT 1", (goal_id,)
        ).fetchone()

    def add_artifact(self, goal_id: int, step_id: int | None, path: str, sha256: str, kind: str) -> None:
        self.conn.execute(
            "INSERT INTO artifacts (goal_id, step_id, path, sha256, kind) VALUES (%s, %s, %s, %s, %s)",
            (goal_id, step_id, path, sha256, kind),
        )

    def artifact_count(self, goal_id: int) -> int:
        return self.conn.execute(
            "SELECT count(*) AS n FROM artifacts WHERE goal_id = %s", (goal_id,)
        ).fetchone()["n"]

    def list_artifacts(self, goal_id: int, limit: int = 20) -> list[dict]:
        return self.conn.execute(
            "SELECT * FROM artifacts WHERE goal_id = %s ORDER BY id DESC LIMIT %s",
            (goal_id, limit),
        ).fetchall()

    # ---- budgets ----

    def ensure_budget(
        self, goal_id: int, steps_limit: int, tokens_limit: int, wallclock_limit_sec: int
    ) -> None:
        self.conn.execute(
            "INSERT INTO budgets (goal_id, steps_limit, tokens_limit, wallclock_limit_sec) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (goal_id) DO NOTHING",
            (goal_id, steps_limit, tokens_limit, wallclock_limit_sec),
        )

    def get_budget(self, goal_id: int) -> dict:
        return self.conn.execute("SELECT * FROM budgets WHERE goal_id = %s", (goal_id,)).fetchone()

    def bump_steps(self, goal_id: int, n: int = 1) -> None:
        self.conn.execute("UPDATE budgets SET steps_used = steps_used + %s WHERE goal_id = %s", (n, goal_id))

    def bump_tokens(self, goal_id: int, tokens_in: int, tokens_out: int) -> None:
        self.conn.execute(
            "UPDATE budgets SET tokens_used = tokens_used + %s WHERE goal_id = %s",
            (tokens_in + tokens_out, goal_id),
        )

    # ---- locking ----

    def try_lock(self, goal_id: int) -> bool:
        row = self.conn.execute("SELECT pg_try_advisory_lock(%s) AS ok", (goal_id,)).fetchone()
        return bool(row["ok"])

    def unlock(self, goal_id: int) -> None:
        self.conn.execute("SELECT pg_advisory_unlock(%s)", (goal_id,))
