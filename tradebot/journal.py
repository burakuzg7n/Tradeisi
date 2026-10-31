"""Journal — her sinyal ve işlem kalıcı kayıt altında (SQLite).

PostgreSQL'e geçiş: şema uyumlu tutuldu; sadece bağlantı katmanı değişir.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    setup TEXT,
    session TEXT,
    htf_bias TEXT,
    accepted INTEGER NOT NULL,
    reject_reason TEXT,
    raw JSON
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER REFERENCES signals(id),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    position_size REAL NOT NULL,
    risk_amount REAL NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    exit_price REAL,
    exit_reason TEXT,
    pnl_usd REAL,
    pnl_r REAL,
    session TEXT,
    setup_score REAL,
    notes TEXT,
    paper INTEGER NOT NULL DEFAULT 1
);
"""


class Journal:
    def __init__(self, db_path: str = "journal.db"):
        # check_same_thread=False: FastAPI/TestClient farklı thread'lerden
        # erişebilir; yazmalar tek consumer üzerinden serileştiği için güvenli.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def log_signal(
        self, payload: dict, accepted: bool, reject_reason: str | None = None
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO signals
               (received_at, symbol, direction, entry, stop_loss, take_profit,
                setup, session, htf_bias, accepted, reject_reason, raw)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                self._now(),
                payload.get("symbol"),
                payload.get("direction"),
                payload.get("entry"),
                payload.get("stop_loss"),
                payload.get("take_profit"),
                payload.get("setup"),
                payload.get("session"),
                payload.get("htf_bias"),
                int(accepted),
                reject_reason,
                json.dumps(payload),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def open_trade(
        self,
        signal_id: int,
        payload: dict,
        position_size: float,
        risk_amount: float,
        paper: bool = True,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO trades
               (signal_id, symbol, direction, entry, stop_loss, take_profit,
                position_size, risk_amount, opened_at, session, paper)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                signal_id,
                payload.get("symbol"),
                payload.get("direction"),
                payload.get("entry"),
                payload.get("stop_loss"),
                payload.get("take_profit"),
                position_size,
                risk_amount,
                self._now(),
                payload.get("session"),
                int(paper),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_reason: str,
        pnl_usd: float,
        pnl_r: float,
        notes: str | None = None,
    ) -> None:
        self.conn.execute(
            """UPDATE trades SET closed_at=?, exit_price=?, exit_reason=?,
               pnl_usd=?, pnl_r=?, notes=? WHERE id=?""",
            (self._now(), exit_price, exit_reason, pnl_usd, pnl_r, notes, trade_id),
        )
        self.conn.commit()

    def stats(self) -> dict:
        row = self.conn.execute(
            """SELECT COUNT(*) AS n,
                      SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) AS wins,
                      SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END) AS gp,
                      SUM(CASE WHEN pnl_usd < 0 THEN -pnl_usd ELSE 0 END) AS gl,
                      AVG(pnl_r) AS exp_r
               FROM trades WHERE closed_at IS NOT NULL"""
        ).fetchone()
        n = row["n"] or 0
        gl = row["gl"] or 0.0
        return {
            "closed_trades": n,
            "win_rate": (row["wins"] or 0) / n if n else 0.0,
            "profit_factor": (row["gp"] or 0.0) / gl if gl else None,
            "expectancy_r": row["exp_r"] or 0.0,
        }

    def close(self) -> None:
        self.conn.close()
