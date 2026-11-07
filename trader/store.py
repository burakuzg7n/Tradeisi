"""Kalici kayit: SQLite.

Tek dosya `out/trader.db`. Sinyaller, emirler, islemler, equity serisi ve
sistem olaylari kaydedilir. Dashboard ve raporlar bu dosyadan okur.

Tasarim: yazmalar tek consumer tarafindan yapilir; `check_same_thread=False`
FastAPI/TestClient farkli thread'lerden okuyabilsin diye.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    created_at TEXT NOT NULL,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    action TEXT NOT NULL,
    entry REAL, stop REAL, target REAL, weight REAL,
    accepted INTEGER NOT NULL,
    reject_reason TEXT,
    meta TEXT
);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_order_id TEXT UNIQUE,
    ts TEXT,
    strategy TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    kind TEXT NOT NULL,
    qty REAL,
    price REAL,
    stop REAL,
    target REAL,
    status TEXT,
    exchange TEXT,
    exchange_order_id TEXT,
    filled_qty REAL DEFAULT 0,
    avg_price REAL,
    fee REAL DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    meta TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry REAL, exit REAL, qty REAL,
    stop REAL, target REAL,
    pnl_usd REAL, pnl_r REAL,
    fees REAL DEFAULT 0, funding REAL DEFAULT 0,
    entry_ts TEXT, exit_ts TEXT,
    exit_reason TEXT,
    mode TEXT,
    meta TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_exit_ts ON trades(exit_ts);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);

CREATE TABLE IF NOT EXISTS equity (
    ts TEXT PRIMARY KEY,
    equity REAL, cash REAL, gross REAL, net REAL,
    mode TEXT, strategy TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT,
    source TEXT,
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """SQLite sarmalayici — hepsi senkron, thread-safe (check_same_thread=False)."""

    def __init__(self, path: str | Path = "out/trader.db"):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # ---------------- sinyaller ----------------

    def log_signal(self, signal: dict, accepted: bool,
                   reject_reason: str | None = None) -> int:
        cur = self.conn.execute(
            """INSERT INTO signals
               (ts, created_at, strategy, symbol, side, action, entry, stop, target,
                weight, accepted, reject_reason, meta)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                signal.get("ts") or _now(),
                _now(),
                signal.get("strategy", ""),
                signal.get("symbol", ""),
                signal.get("side", ""),
                signal.get("action", ""),
                signal.get("entry"),
                signal.get("stop"),
                signal.get("target"),
                signal.get("weight"),
                int(bool(accepted)),
                reject_reason,
                json.dumps(signal.get("meta", {}), default=str),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def recent_signals(self, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------------- emirler ----------------

    def upsert_order(self, order: dict) -> None:
        """Emir kaydini ekle/guncelle.

        KISMI guncelleme desteklenir: verilmeyen alanlar mevcut degeri
        KORUR. SQLite UPSERT'te NOT NULL kisiti, conflict cozumunden ONCE
        kontrol edildigi icin once var olup olmadigina bakip ayri INSERT veya
        UPDATE yoluna gideriz.
        """
        cols = ("client_order_id", "ts", "strategy", "symbol", "side", "kind", "qty",
                "price", "stop", "target", "status", "exchange", "exchange_order_id",
                "filled_qty", "avg_price", "fee", "created_at", "updated_at", "meta")
        values = []
        for c in cols:
            if c in ("created_at", "updated_at"):
                values.append(order.get(c) or _now())
            elif c == "meta":
                values.append(json.dumps(order["meta"], default=str)
                              if "meta" in order else None)
            else:
                values.append(order.get(c))

        client_id = order.get("client_order_id")
        row = self.conn.execute(
            "SELECT 1 FROM orders WHERE client_order_id = ?", (client_id,)
        ).fetchone()

        if row is None:
            placeholders = ",".join("?" for _ in cols)
            self.conn.execute(
                f"INSERT INTO orders ({','.join(cols)}) VALUES ({placeholders})",
                values,
            )
        else:
            provided = [c for c in cols if c not in ("client_order_id", "created_at")]
            # sadece VERILEN alanlari guncelle (verilmeyenler korunur)
            assignments = ",".join(
                f"{c}=COALESCE(?, orders.{c})" for c in provided
            )
            update_values = [values[cols.index(c)] for c in provided]
            self.conn.execute(
                f"""UPDATE orders SET {assignments}, updated_at=?
                    WHERE client_order_id=?""",
                update_values + [values[cols.index("updated_at")], client_id],
            )
        self.conn.commit()

    def get_order(self, client_order_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM orders WHERE client_order_id = ?", (client_order_id,)
        ).fetchone()
        return dict(row) if row else None

    def open_orders(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM orders WHERE status IN ('pending','open','partial') ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_orders(self, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------------- islemler ----------------

    def log_trade(self, trade: dict) -> int:
        cur = self.conn.execute(
            """INSERT INTO trades
               (strategy, symbol, side, entry, exit, qty, stop, target, pnl_usd,
                pnl_r, fees, funding, entry_ts, exit_ts, exit_reason, mode, meta)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                trade.get("strategy"), trade.get("symbol"), trade.get("side"),
                trade.get("entry"), trade.get("exit"), trade.get("qty"),
                trade.get("stop"), trade.get("target"), trade.get("pnl_usd"),
                trade.get("pnl_r"), trade.get("fees", 0.0), trade.get("funding", 0.0),
                trade.get("entry_ts"), trade.get("exit_ts"), trade.get("exit_reason"),
                trade.get("mode"), json.dumps(trade.get("meta", {}), default=str),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def recent_trades(self, limit: int = 100, strategy: str | None = None) -> list[dict]:
        if strategy:
            rows = self.conn.execute(
                "SELECT * FROM trades WHERE strategy = ? ORDER BY id DESC LIMIT ?",
                (strategy, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def trades_after(self, ts: str, strategy: str | None = None) -> list[dict]:
        if strategy:
            rows = self.conn.execute(
                "SELECT * FROM trades WHERE exit_ts > ? AND strategy = ? ORDER BY id",
                (ts, strategy),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM trades WHERE exit_ts > ? ORDER BY id", (ts,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------------- equity ----------------

    def record_equity(self, ts: str, equity: float, cash: float, gross: float,
                      net: float, mode: str = "", strategy: str = "") -> None:
        self.conn.execute(
            """INSERT INTO equity (ts, equity, cash, gross, net, mode, strategy)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(ts) DO UPDATE SET equity=excluded.equity,
                 cash=excluded.cash, gross=excluded.gross, net=excluded.net,
                 mode=excluded.mode, strategy=excluded.strategy""",
            (ts, equity, cash, gross, net, mode, strategy),
        )
        self.conn.commit()

    def equity_curve(self, strategy: str | None = None) -> list[dict]:
        if strategy:
            rows = self.conn.execute(
                "SELECT * FROM equity WHERE strategy = ? ORDER BY ts", (strategy,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM equity ORDER BY ts").fetchall()
        return [dict(r) for r in rows]

    # ---------------- olaylar ----------------

    def log_event(self, message: str, level: str = "info", source: str = "") -> None:
        self.conn.execute(
            "INSERT INTO events (ts, level, source, message) VALUES (?,?,?,?)",
            (_now(), level, source, message),
        )
        self.conn.commit()

    def recent_events(self, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------------- anahtar-deger ----------------

    def set_kv(self, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO kv (k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (key, json.dumps(value, default=str)),
        )
        self.conn.commit()

    def get_kv(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["v"])
        except (json.JSONDecodeError, TypeError):
            return default

    # ---------------- ozet ----------------

    def stats(self, strategy: str | None = None) -> dict:
        if strategy:
            rows = self.conn.execute(
                "SELECT pnl_usd, pnl_r FROM trades WHERE strategy = ? AND exit_ts IS NOT NULL",
                (strategy,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT pnl_usd, pnl_r FROM trades WHERE exit_ts IS NOT NULL"
            ).fetchall()
        pnls = [float(r["pnl_usd"] or 0.0) for r in rows]
        rs = [float(r["pnl_r"] or 0.0) for r in rows]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        gp = sum(wins)
        gl = abs(sum(losses))
        eq = self.equity_curve(strategy)
        equity_now = float(eq[-1]["equity"]) if eq else None
        peak = 0.0
        dd = 0.0
        for point in eq:
            e = float(point["equity"])
            peak = max(peak, e)
            if peak > 0:
                dd = max(dd, (peak - e) / peak)
        return {
            "closed_trades": len(pnls),
            "win_rate": (len(wins) / len(pnls)) if pnls else 0.0,
            "profit_factor": (gp / gl) if gl > 0 else None,
            "expectancy_r": (sum(rs) / len(rs)) if rs else 0.0,
            "total_pnl_usd": sum(pnls),
            "equity": equity_now,
            "max_drawdown": dd,
        }

    def close(self) -> None:
        self.conn.close()
