from __future__ import annotations

import json
import sqlite3
import threading
import datetime as dt
from pathlib import Path
from typing import Any

from web.backend.embedded.llm_clients.model_catalog import MODEL_OPTIONS

DB_PATH = Path("web") / "tradingagents_web.db"


class Database:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    error TEXT,
                    report_dir TEXT,
                    report_files_json TEXT,
                    final_state_json TEXT
                )
                """
            )
            cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(runs)").fetchall()}
            if "progress" not in cols:
                self.conn.execute("ALTER TABLE runs ADD COLUMN progress INTEGER NOT NULL DEFAULT 0")
            if "cancel_requested" not in cols:
                self.conn.execute("ALTER TABLE runs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_events_run_id_id ON run_events(run_id, id)"
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_providers (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_name TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK(mode IN ('quick','deep')),
                    label TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(provider_name) REFERENCES llm_providers(name) ON DELETE CASCADE
                )
                """
            )
            self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_llm_models_provider_mode_value ON llm_models(provider_name, mode, value)"
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_tickers (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    exchange TEXT,
                    type TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._seed_model_catalog_if_empty()

    def _now(self) -> str:
        return dt.datetime.utcnow().isoformat()

    def _seed_model_catalog_if_empty(self) -> None:
        row = self.conn.execute("SELECT COUNT(*) AS c FROM llm_providers").fetchone()
        if row and int(row["c"]) > 0:
            return
        now = self._now()
        for provider, modes in MODEL_OPTIONS.items():
            self.conn.execute(
                "INSERT OR IGNORE INTO llm_providers(name, created_at) VALUES(?, ?)",
                (provider, now),
            )
            for mode in ("quick", "deep"):
                for label, value in modes.get(mode, []):
                    self.conn.execute(
                        """
                        INSERT OR IGNORE INTO llm_models(provider_name, mode, label, value, created_at)
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        (provider, mode, label, value, now),
                    )
        default_provider = "openai" if "openai" in MODEL_OPTIONS else next(iter(MODEL_OPTIONS.keys()), "")
        default_quick = MODEL_OPTIONS.get(default_provider, {}).get("quick", [("", "")])[0][1] if default_provider else ""
        default_deep = MODEL_OPTIONS.get(default_provider, {}).get("deep", [("", "")])[0][1] if default_provider else ""
        if default_provider:
            self.conn.execute(
                "INSERT OR REPLACE INTO app_settings(key, value) VALUES('default_provider', ?)",
                (default_provider,),
            )
        if default_quick:
            self.conn.execute(
                "INSERT OR REPLACE INTO app_settings(key, value) VALUES('default_quick_model', ?)",
                (default_quick,),
            )
        if default_deep:
            self.conn.execute(
                "INSERT OR REPLACE INTO app_settings(key, value) VALUES('default_deep_model', ?)",
                (default_deep,),
            )

    def create_run(self, row: dict[str, Any]) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO runs(run_id, ticker, analysis_date, status, created_at, report_files_json)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    row["run_id"],
                    row["ticker"],
                    row["analysis_date"],
                    row["status"],
                    row["created_at"],
                    "[]",
                ),
            )

    def update_run(self, run_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        keys = list(kwargs.keys())
        values = [kwargs[k] for k in keys]
        sets = ", ".join(f"{k}=?" for k in keys)
        with self._lock, self.conn:
            self.conn.execute(f"UPDATE runs SET {sets} WHERE run_id=?", (*values, run_id))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [self._row_to_run(r) for r in rows]

    def add_event(self, run_id: str, ts: str, event_type: str, payload: dict[str, Any]) -> int:
        with self._lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO run_events(run_id, ts, event_type, payload_json) VALUES(?, ?, ?, ?)",
                (run_id, ts, event_type, json.dumps(payload, ensure_ascii=False)),
            )
            return int(cur.lastrowid)

    def list_events(
        self, run_id: str, after_id: int = 0, event_types: list[str] | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT id, run_id, ts, event_type, payload_json FROM run_events WHERE run_id=? AND id>?"
        params: list[Any] = [run_id, after_id]
        if event_types:
            placeholders = ",".join(["?"] * len(event_types))
            sql += f" AND event_type IN ({placeholders})"
            params.extend(event_types)
        sql += " ORDER BY id ASC"
        with self._lock:
            rows = self.conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            result.append(
                {
                    "id": r["id"],
                    "run_id": r["run_id"],
                    "ts": r["ts"],
                    "event_type": r["event_type"],
                    "payload": json.loads(r["payload_json"]),
                }
            )
        return result

    def _row_to_run(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "run_id": row["run_id"],
            "ticker": row["ticker"],
            "analysis_date": row["analysis_date"],
            "status": row["status"],
            "created_at": row["created_at"],
            "progress": row["progress"] if "progress" in row.keys() else 0,
            "cancel_requested": bool(row["cancel_requested"]) if "cancel_requested" in row.keys() else False,
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
            "error": row["error"],
            "report_dir": row["report_dir"],
            "report_files": json.loads(row["report_files_json"] or "[]"),
            "final_state": json.loads(row["final_state_json"]) if row["final_state_json"] else None,
        }

    def delete_run(self, run_id: str) -> bool:
        with self._lock, self.conn:
            cur = self.conn.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
            self.conn.execute("DELETE FROM run_events WHERE run_id=?", (run_id,))
            return cur.rowcount > 0

    def get_model_catalog(self) -> dict[str, Any]:
        with self._lock:
            providers = [r["name"] for r in self.conn.execute("SELECT name FROM llm_providers ORDER BY name ASC").fetchall()]
            model_rows = self.conn.execute(
                "SELECT id, provider_name, mode, label, value FROM llm_models ORDER BY provider_name ASC, mode ASC, id ASC"
            ).fetchall()
            setting_rows = self.conn.execute("SELECT key, value FROM app_settings").fetchall()

        models: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for p in providers:
            models[p] = {"quick": [], "deep": []}
        for r in model_rows:
            p = r["provider_name"]
            if p not in models:
                models[p] = {"quick": [], "deep": []}
            models[p][r["mode"]].append(
                {"id": int(r["id"]), "label": r["label"], "value": r["value"]}
            )

        settings = {r["key"]: r["value"] for r in setting_rows}
        default_provider = settings.get("default_provider") or (providers[0] if providers else "")
        default_quick_model = settings.get("default_quick_model", "")
        default_deep_model = settings.get("default_deep_model", "")
        return {
            "providers": providers,
            "models": models,
            "defaults": {
                "provider": default_provider,
                "quick_model": default_quick_model,
                "deep_model": default_deep_model,
            },
        }

    def create_provider(self, name: str) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO llm_providers(name, created_at) VALUES(?, ?)",
                (name.strip(), self._now()),
            )

    def rename_provider(self, old_name: str, new_name: str) -> bool:
        with self._lock, self.conn:
            exists = self.conn.execute("SELECT 1 FROM llm_providers WHERE name=?", (old_name,)).fetchone()
            if not exists:
                return False
            self.conn.execute("UPDATE llm_providers SET name=? WHERE name=?", (new_name, old_name))
            self.conn.execute("UPDATE llm_models SET provider_name=? WHERE provider_name=?", (new_name, old_name))
            return True

    def delete_provider(self, name: str) -> bool:
        with self._lock, self.conn:
            cur = self.conn.execute("DELETE FROM llm_providers WHERE name=?", (name,))
            self.conn.execute("DELETE FROM llm_models WHERE provider_name=?", (name,))
            return cur.rowcount > 0

    def create_model(self, provider_name: str, mode: str, label: str, value: str) -> int:
        with self._lock, self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO llm_models(provider_name, mode, label, value, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (provider_name, mode, label, value, self._now()),
            )
            return int(cur.lastrowid)

    def update_model(self, model_id: int, mode: str, label: str, value: str) -> bool:
        with self._lock, self.conn:
            cur = self.conn.execute(
                "UPDATE llm_models SET mode=?, label=?, value=? WHERE id=?",
                (mode, label, value, model_id),
            )
            return cur.rowcount > 0

    def delete_model(self, model_id: int) -> bool:
        with self._lock, self.conn:
            cur = self.conn.execute("DELETE FROM llm_models WHERE id=?", (model_id,))
            return cur.rowcount > 0

    def set_model_defaults(self, provider: str, quick_model: str, deep_model: str) -> None:
        with self._lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO app_settings(key, value) VALUES('default_provider', ?)", (provider,))
            self.conn.execute("INSERT OR REPLACE INTO app_settings(key, value) VALUES('default_quick_model', ?)", (quick_model,))
            self.conn.execute("INSERT OR REPLACE INTO app_settings(key, value) VALUES('default_deep_model', ?)", (deep_model,))

    def list_saved_tickers(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT symbol, name, exchange, type FROM saved_tickers ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "symbol": r["symbol"],
                "name": r["name"],
                "exchange": r["exchange"],
                "type": r["type"],
            }
            for r in rows
        ]

    def save_tickers(self, items: list[dict[str, Any]]) -> int:
        now = self._now()
        with self._lock, self.conn:
            for item in items:
                self.conn.execute(
                    """
                    INSERT INTO saved_tickers(symbol, name, exchange, type, created_at)
                    VALUES(?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        name=excluded.name,
                        exchange=excluded.exchange,
                        type=excluded.type
                    """,
                    (
                        str(item.get("symbol", "")).strip().upper(),
                        str(item.get("name", "")).strip(),
                        item.get("exchange"),
                        item.get("type"),
                        now,
                    ),
                )
        return len(items)

    def delete_saved_ticker(self, symbol: str) -> bool:
        with self._lock, self.conn:
            cur = self.conn.execute("DELETE FROM saved_tickers WHERE symbol=?", (symbol.strip().upper(),))
            return cur.rowcount > 0


DB = Database()
