"""Testnet / canli yurutucu.

Bu katman `tradebot/live.py` + `tradebot/execution.py` icindeki kayitli dört
yuksek ciddiyetli hatayi kapatir (bkz. `trader/exchange.py` basligi):

  1) Cift emir riski      -> idempotent clientOrderId + gonderim oncesi sorgu
  2) Takipsiz kismi dolum -> dolum miktari ayri tutulur, iptalde dolmus
                              kisim kapanis olarak kaydedilir
  3) Yeniden baslatma      -> `reconcile()` borsadaki acik emir/pozisyonlari
                              yerel kayitlarla birlestirir, eksik SL/TP'yi
                              yeniden asar
  4) Tahmini P&L           -> P&L gercek dolum verisinden hesaplanir

Emir akisi:
    sinyal (bar kapanisi) -> risk kontrolu -> idempotent emir -> takip ->
    kismi/tam dolum -> pozisyon -> stop/target -> kapanis -> gercek P&L

Yalnizca kapisi ACIK stratejiler calisir (`trader.gates.check`).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd

from .config import CostModel, ExchangeSettings, RiskSettings
from .exchange import CcxtAdapter, ExchangeOrder, make_client_order_id
from .gates import check as gate_check
from .notify import (TelegramNotifier, fmt_kill_switch, fmt_signal,
                     fmt_trade_closed, fmt_trade_opened)
from .risk import RiskEngine
from .store import Store
from .strategy import Panel, Signal

TF_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}


@dataclass
class TrackedOrder:
    client_order_id: str
    exchange_order_id: str | None
    symbol: str
    side: str                 # "buy" | "sell"
    qty: float
    filled_qty: float = 0.0
    avg_price: float = 0.0
    price: float | None = None
    stop: float | None = None
    target: float | None = None
    risk_amount: float = 0.0
    status: str = "pending"    # pending | partial | open | closed | cancelled
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy: str = ""

    @property
    def remaining(self) -> float:
        return max(self.qty - self.filled_qty, 0.0)


@dataclass
class TrackedPosition:
    symbol: str
    side: str                 # "long" | "short"
    qty: float
    entry_price: float
    stop: float | None = None
    target: float | None = None
    risk_amount: float = 0.0
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy: str = ""
    reconciled: bool = False  # borsadan bulundu (bizim kaydimiz disinda)
    protective: bool = False  # SL/TP borsaya asildi mi


class LiveRunner:
    def __init__(
        self,
        strategy,
        symbols: list[str],
        adapter: CcxtAdapter,
        store: Store,
        settings: ExchangeSettings,
        risk_settings: RiskSettings | None = None,
        costs: CostModel | None = None,
        notifier: TelegramNotifier | None = None,
        initial_equity: float = 1000.0,
        mode: str = "testnet",
        history_bars: int = 400,
        poll_seconds: int = 30,
    ):
        self.strategy = strategy
        self.symbols = symbols
        self.adapter = adapter
        self.store = store
        self.settings = settings
        self.costs = costs or CostModel()
        self.notifier = notifier or TelegramNotifier()
        self.mode = mode
        self.history_bars = history_bars
        self.poll_seconds = poll_seconds
        self.risk = RiskEngine(risk_settings or RiskSettings(), initial_equity,
                               state=store.get_kv(f"risk_state:{strategy.name}"))
        self.orders: dict[str, TrackedOrder] = {}
        self.positions: dict[str, TrackedPosition] = {}
        self._stop = False

    # ==================================================================
    # 1) UZLASTIRMA (yeniden baslatma)
    # ==================================================================

    async def reconcile(self) -> dict:
        """Borsadaki gercek durumu yerel kayitlarla birlestir."""
        await self.adapter.load_markets()
        adopted_orders = 0
        adopted_positions = 0

        # --- acik emirler
        for sym in self.symbols:
            for raw in await self.adapter.fetch_open_orders(sym):
                client_id = _client_id_of(raw)
                if not client_id or not client_id.startswith("tb-"):
                    continue   # bizim degil, dokunma
                if client_id in self.orders:
                    continue
                amount = float(raw.get("amount") or 0.0)
                filled = float(raw.get("filled") or 0.0)
                price = float(raw["price"]) if raw.get("price") else None
                avg = float(raw["average"]) if raw.get("average") else (price or 0.0)
                self.orders[client_id] = TrackedOrder(
                    client_order_id=client_id,
                    exchange_order_id=str(raw.get("id")) if raw.get("id") else None,
                    symbol=sym,
                    side=str(raw.get("side") or "buy"),
                    qty=amount,
                    filled_qty=filled,
                    avg_price=avg,
                    price=price,
                    status="partial" if 0 < filled < amount else "pending",
                )
                adopted_orders += 1
                self.store.log_event(
                    f"UZLASTIRMA: acik emir alindi {sym} {client_id} "
                    f"({filled}/{amount})", source="live",
                )

        # --- acik pozisyonlar
        for raw in await self.adapter.fetch_positions(self.symbols):
            sym = _strip(raw.get("symbol") or "")
            qty = _position_qty(raw)
            if qty <= 0:
                continue
            side = _position_side(raw)
            entry = float(raw.get("entryPrice") or 0.0)
            if sym in self.positions:
                pos = self.positions[sym]
                pos.qty = qty
                if entry:
                    pos.entry_price = entry
                continue
            self.positions[sym] = TrackedPosition(
                symbol=sym, side=side, qty=qty, entry_price=entry,
                opened_at=datetime.now(timezone.utc),
                strategy=self.strategy.name, reconciled=True,
            )
            adopted_positions += 1
            self.store.log_event(
                f"UZLASTIRMA: acik pozisyon bulundu {sym} {side} qty={qty} "
                f"entry={entry} — koruma emirleri yeniden asilacak",
                level="warn", source="live",
            )
            self.store.log_signal({
                "ts": datetime.now(timezone.utc).isoformat(),
                "strategy": self.strategy.name, "symbol": sym, "side": side,
                "action": "reconciled_position", "meta": {"qty": qty, "entry": entry},
            }, True, "borsada acik pozisyon bulundu (uzlastirma)")

        # --- koruma emirlerini yeniden as
        for pos in self.positions.values():
            if not pos.protective:
                await self._attach_protective(pos)

        self.store.log_event(
            f"Uzlastirma tamam: {adopted_orders} emir, {adopted_positions} pozisyon",
            source="live",
        )
        return {"orders": adopted_orders, "positions": adopted_positions}

    # ==================================================================
    # 2) SINYAL -> EMIR
    # ==================================================================

    async def fetch_frames(self) -> dict[str, pd.DataFrame]:
        frames: dict[str, pd.DataFrame] = {}
        for sym in self.symbols:
            try:
                df = await self.adapter.fetch_ohlcv(
                    sym, self.strategy.timeframe, limit=self.history_bars
                )
            except Exception as exc:
                self.store.log_event(f"{sym} veri cekilemedi: {exc}",
                                     level="warn", source="live")
                continue
            if len(df) == 0:
                continue
            frames[sym] = df.iloc[:-1]  # kapanmamis son bar atilir
        return frames

    async def scan(self) -> int:
        frames = await self.fetch_frames()
        if not frames:
            return 0
        last_ts = max(df.index[-1] for df in frames.values())
        signals = self.strategy.generate(Panel(frames), last_ts)
        placed = 0
        for sig in signals:
            payload = {**sig.to_dict(), "strategy": self.strategy.name}
            ok, msg = await self._accept_signal(sig, payload)
            if not ok:
                self.store.log_signal(payload, False, msg)
                continue
            self.store.log_signal(payload, True)
            placed += 1
        return placed

    async def _accept_signal(self, sig: Signal, payload: dict) -> tuple[bool, str]:
        ok, msg = self.risk.can_trade()
        if not ok:
            if self.risk.kill_switch_active:
                await self.notifier.send(fmt_kill_switch(
                    msg, self.risk.daily_pnl_r, self.risk.weekly_pnl_r,
                    self.risk.current_drawdown,
                ))
            return False, msg

        if len(self.positions) >= self.risk.p.max_positions and \
                sig.symbol not in self.positions:
            return False, "pozisyon limiti"

        if sig.action == "target_weight":
            return await self._place_weight_order(sig, payload)
        if sig.action == "open":
            return await self._place_open_order(sig, payload)
        if sig.action == "close":
            return await self._place_close_order(sig, payload)
        return False, f"bilinmeyen aksiyon {sig.action}"

    async def _place_weight_order(self, sig: Signal, payload: dict) -> tuple[bool, str]:
        equity = self.risk.current_balance
        if equity <= 0:
            return False, "equity <= 0"
        target_notional = float(sig.weight or 0.0) * equity
        pos = self.positions.get(sig.symbol)
        current = 0.0
        if pos:
            current = (1 if pos.side == "long" else -1) * pos.qty * pos.entry_price
        delta = target_notional - current
        price = self._last_price(sig.symbol)
        if price <= 0:
            return False, "fiyat yok"
        qty = abs(delta) / price
        if qty <= 0 or qty * price < 5.0:
            return False, "emir minimumunun altinda"
        side = "buy" if delta > 0 else "sell"
        client_id = make_client_order_id(
            "w", self.strategy.name, sig.symbol, str(sig.ts or ""), round(qty, 8)
        )
        return await self._send(client_id, sig.symbol, side, qty, payload)

    async def _place_open_order(self, sig: Signal, payload: dict) -> tuple[bool, str]:
        if sig.entry is None or sig.stop is None or sig.target is None:
            return False, "eksik geometri"
        risk_dist = abs(sig.entry - sig.stop)
        if risk_dist <= 0:
            return False, "stop == entry"
        risk_amount = self.risk.current_balance * self.risk.p.risk_per_trade
        qty = risk_amount / risk_dist
        side = "buy" if sig.side == "long" else "sell"
        order_type = getattr(sig, "order_type", "market")
        client_id = make_client_order_id(
            "o", self.strategy.name, sig.symbol, str(sig.ts or ""), round(qty, 8)
        )
        ok, msg = await self._send(client_id, sig.symbol, side, qty, payload,
                                   stop=sig.stop, target=sig.target,
                                   order_type=order_type, limit_price=sig.entry)
        if ok:
            self.risk.pending_risk[sig.symbol] = risk_amount  # type: ignore[attr-defined]
        return ok, msg

    async def _place_close_order(self, sig: Signal, payload: dict) -> tuple[bool, str]:
        pos = self.positions.get(sig.symbol)
        if not pos:
            return False, "pozisyon yok"
        side = "sell" if pos.side == "long" else "buy"
        client_id = make_client_order_id(
            "c", self.strategy.name, sig.symbol, str(sig.ts or ""), round(pos.qty, 8)
        )
        return await self._send(client_id, sig.symbol, side, pos.qty, payload,
                                reduce_only=True)

    async def _send(self, client_id: str, symbol: str, side: str, qty: float,
                    payload: dict, stop: float | None = None,
                    target: float | None = None, reduce_only: bool = False,
                    order_type: str = "market",
                    limit_price: float | None = None) -> tuple[bool, str]:
        params: dict = {}
        if stop is not None:
            params["stopLoss"] = {"triggerPrice": stop, "orderType": "Market"}
        if target is not None:
            params["takeProfit"] = {"triggerPrice": target, "orderType": "Limit"}
        if reduce_only:
            params["reduceOnly"] = True
        if self.settings.exchange_id == "bybit":
            params["positionIdx"] = 0
        else:
            params.pop("stopLoss", None)
            params.pop("takeProfit", None)
            if stop is not None:
                params["stopLossPrice"] = stop
            if target is not None:
                params["takeProfitPrice"] = target

        # 1) YEREL KAYIT: gonderimden once "sending" olarak yaz.
        #    Crash olursa buradan devam edebiliriz.
        self.store.upsert_order({
            "client_order_id": client_id, "ts": datetime.now(timezone.utc).isoformat(),
            "strategy": self.strategy.name, "symbol": symbol, "side": side,
            "kind": order_type, "qty": qty, "price": limit_price, "stop": stop,
            "target": target, "status": "sending", "exchange": self.settings.exchange_id,
            "exchange_order_id": None, "filled_qty": 0, "avg_price": None, "fee": 0,
            "meta": payload.get("meta", {}),
        })

        try:
            order = await self.adapter.place_order(
                client_order_id=client_id, symbol=symbol, side=side,
                amount=qty, order_type=order_type,
                price=limit_price if order_type == "limit" else None,
                params=params,
            )
        except Exception as exc:
            self.store.upsert_order({
                "client_order_id": client_id, "status": "error",
                "exchange": self.settings.exchange_id,
                "meta": {"error": str(exc)[:400]},
            })
            self.store.log_event(f"EMIR HATASI {symbol}: {exc}", level="error", source="live")
            return False, f"emir hatasi: {exc}"

        self._track_order(order, stop=stop, target=target)
        self.store.upsert_order({
            "client_order_id": client_id, "status": "sent",
            "exchange": self.settings.exchange_id,
            "exchange_order_id": order.exchange_order_id,
            "filled_qty": order.filled, "avg_price": order.average_price,
            "fee": order.fee,
        })
        self.store.log_event(
            f"EMIR: {symbol} {side} qty={qty:.6f} id={client_id}", source="live"
        )
        await self.notifier.send(fmt_signal(payload, True))
        return True, "OK"

    def _track_order(self, order: ExchangeOrder, stop: float | None = None,
                     target: float | None = None) -> None:
        existing = self.orders.get(order.client_order_id)
        if existing:
            existing.filled_qty = order.filled
            existing.avg_price = order.average_price or existing.avg_price
            existing.exchange_order_id = order.exchange_order_id or existing.exchange_order_id
            existing.status = "open" if order.is_filled else (
                "partial" if order.filled > 0 else "pending")
            return
        self.orders[order.client_order_id] = TrackedOrder(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            symbol=order.symbol, side=order.side, qty=order.amount,
            filled_qty=order.filled, avg_price=order.average_price or 0.0,
            price=order.price, stop=stop, target=target,
            status="open" if order.is_filled else (
                "partial" if order.filled > 0 else "pending"),
            strategy=self.strategy.name,
        )

    # ==================================================================
    # 3) YASAM DONGUSU YONETIMI
    # ==================================================================

    async def manage(self) -> None:
        """Emir dolumlarini, pozisyon kapanislarini ve korumayi yonet."""
        # --- emirler
        for client_id, tracked in list(self.orders.items()):
            if tracked.status in ("closed", "cancelled"):
                continue
            try:
                raw = await self.adapter.exchange.fetch_order(
                    tracked.exchange_order_id,
                    self.adapter.sym(tracked.symbol),
                )
            except Exception:
                continue
            if not raw:
                continue
            filled = float(raw.get("filled") or 0.0)
            status = str(raw.get("status") or "")
            avg = float(raw["average"]) if raw.get("average") else tracked.avg_price
            newly_filled = filled - tracked.filled_qty
            tracked.filled_qty = filled
            tracked.avg_price = avg
            self.store.upsert_order({
                "client_order_id": client_id,
                "symbol": tracked.symbol,
                "side": tracked.side,
                "kind": "market",
                "qty": tracked.qty,
                "strategy": tracked.strategy or self.strategy.name,
                "exchange": self.settings.exchange_id,
                "exchange_order_id": tracked.exchange_order_id,
                "filled_qty": filled,
                "avg_price": avg,
                "status": status,
            })

            if newly_filled > 0:
                self._apply_fill(tracked, newly_filled, avg)

            if status == "canceled" or status == "expired":
                # DUZELTILMIS HALI (eski hatayi kapatir): emir iptal edilince
                # DOLMUS KISIM KAYBOLMAZ. O kismi bir POZISYON olarak takipte
                # kalir ve normal kapanis akisinda gercek P&L ile kapanir.
                tracked.status = "cancelled"
                self.store.upsert_order({
                    "client_order_id": client_id,
                    "symbol": tracked.symbol,
                    "side": tracked.side,
                    "kind": "market",
                    "qty": tracked.qty,
                    "strategy": tracked.strategy or self.strategy.name,
                    "status": "cancelled",
                })
                if tracked.filled_qty > 0:
                    pos = self.positions.get(tracked.symbol)
                    if pos is None:
                        # pozisyon kaydi yoksa olustur (takipsiz pozisyon kalmasin)
                        side = "long" if tracked.side == "buy" else "short"
                        self.positions[tracked.symbol] = TrackedPosition(
                            symbol=tracked.symbol, side=side, qty=tracked.filled_qty,
                            entry_price=tracked.avg_price, stop=tracked.stop,
                            target=tracked.target, risk_amount=tracked.risk_amount,
                            strategy=self.strategy.name,
                        )
                    self.store.log_event(
                        f"EMIR IPTAL {tracked.symbol}: dolmus {tracked.filled_qty} "
                        f"miktar POZISYON olarak takipte kaliyor",
                        level="warn", source="live",
                    )
            elif status == "closed" and tracked.filled_qty > 0:
                tracked.status = "closed"

        # --- pozisyonlar
        raw_positions = await self.adapter.fetch_positions(self.symbols)
        by_symbol = {}
        for raw in raw_positions:
            sym = _strip(raw.get("symbol") or "")
            qty = _position_qty(raw)
            if qty > 0:
                by_symbol[sym] = (raw, qty)

        for sym, pos in list(self.positions.items()):
            if sym not in by_symbol:
                # Borsada pozisyon yok -> KAPANDI. P&L gercek dolumdan.
                await self._close_position(pos, "closed")
                continue
            raw, qty = by_symbol[sym]
            pos.qty = qty
            entry = float(raw.get("entryPrice") or 0.0)
            if entry:
                pos.entry_price = entry
            # yazilmis stop/target borsada mi? degilse yeniden as
            if not pos.protective:
                await self._attach_protective(pos)
            # yazilim stopu (borsa emri olusturmada sorun varsa yedek)
            await self._software_stop(pos, raw)

    def _apply_fill(self, tracked: TrackedOrder, delta_qty: float, avg_price: float) -> None:
        """Yeni dolum -> pozisyon guncelle (kismi dolum DESTEKLENIR)."""
        pos = self.positions.get(tracked.symbol)
        if pos is None:
            side = "long" if tracked.side == "buy" else "short"
            self.positions[tracked.symbol] = TrackedPosition(
                symbol=tracked.symbol, side=side, qty=delta_qty,
                entry_price=avg_price, stop=tracked.stop, target=tracked.target,
                risk_amount=tracked.risk_amount, strategy=self.strategy.name,
            )
            pos = self.positions[tracked.symbol]
        else:
            total = pos.qty + delta_qty
            if total > 0:
                pos.entry_price = (
                    pos.entry_price * pos.qty + avg_price * delta_qty) / total
            pos.qty = total
        pos.stop = tracked.stop or pos.stop
        pos.target = tracked.target or pos.target
        self.store.log_event(
            f"DOLUM {tracked.symbol} {tracked.side} +{delta_qty:.6f} @ {avg_price} "
            f"(toplam {pos.qty:.6f})", source="live",
        )
        self.store.log_signal({
            "ts": datetime.now(timezone.utc).isoformat(),
            "strategy": self.strategy.name, "symbol": tracked.symbol,
            "side": pos.side, "action": "position_increased",
            "entry": pos.entry_price, "meta": {"qty": pos.qty},
        }, True)
        self.notifier and asyncio.create_task(self.notifier.send(fmt_trade_opened(
            tracked.symbol, pos.side, pos.qty, pos.entry_price,
            pos.stop, pos.target, tracked.risk_amount,
        )))

    async def _close_position(self, pos: TrackedPosition, reason: str) -> None:
        """Pozisyon kapandi -> GERCEK P&L hesapla (fiyat tahmini YOK)."""
        pnl_usd, pnl_r, exit_price, fees = await self._pnl_from_trades(pos, reason)
        self.store.log_trade({
            "strategy": self.strategy.name, "symbol": pos.symbol, "side": pos.side,
            "entry": pos.entry_price, "exit": exit_price, "qty": pos.qty,
            "stop": pos.stop, "target": pos.target,
            "pnl_usd": pnl_usd, "pnl_r": pnl_r, "fees": fees, "funding": 0.0,
            "entry_ts": pos.opened_at.isoformat(),
            "exit_ts": datetime.now(timezone.utc).isoformat(),
            "exit_reason": reason, "mode": self.mode, "meta": {},
        })
        self.risk.record_result(pnl_r, pos.risk_amount or max(abs(pnl_usd), 1e-9))
        self.store.set_kv(f"risk_state:{self.strategy.name}", self.risk.state())
        self.positions.pop(pos.symbol, None)
        await self.notifier.send(fmt_trade_closed(
            pos.symbol, pos.side, pnl_r, pnl_usd, reason))
        self.store.log_event(
            f"POZISYON KAPANDI {pos.symbol} {pnl_r:+.2f}R ({reason})", source="live")

    async def _pnl_from_trades(self, pos: TrackedPosition, reason: str):
        """Gercek dolum verisinden P&L. Hata olursa 0 doner — TAHMIN YAPILMAZ."""
        since_ms = int(pos.opened_at.timestamp() * 1000)
        try:
            trades = await self.adapter.fetch_my_trades(pos.symbol, since_ms=since_ms)
        except Exception as exc:
            self.store.log_event(f"P&L sorgusu basarisiz {pos.symbol}: {exc}",
                                 level="error", source="live")
            return 0.0, 0.0, 0.0, 0.0

        sign = 1 if pos.side == "long" else -1
        close_side = "sell" if pos.side == "long" else "buy"
        close_qty = 0.0
        close_notional = 0.0
        fees = 0.0
        for t in trades:
            fee = t.get("fee") or {}
            cost = float(fee.get("cost") or 0.0) if isinstance(fee, dict) else 0.0
            if str(t.get("side")) == close_side:
                q = float(t.get("amount") or 0.0)
                close_qty += q
                close_notional += q * float(t.get("price") or 0.0)
                fees += cost
            else:
                fees += cost
        if close_qty <= 0:
            return 0.0, 0.0, pos.entry_price, fees
        exit_price = close_notional / close_qty
        gross = (exit_price - pos.entry_price) * close_qty * sign
        pnl_usd = gross - fees
        risk = pos.risk_amount or max(abs(pos.entry_price) * close_qty *
                                       self.risk.p.risk_per_trade, 1e-9)
        return pnl_usd, (pnl_usd / risk), exit_price, fees

    async def _attach_protective(self, pos: TrackedPosition) -> None:
        """Borsaya stop + target emirleri as (uzlastirmada eksikse)."""
        if pos.stop is None and pos.target is None:
            return
        side = "sell" if pos.side == "long" else "buy"
        try:
            existing = await self.adapter.fetch_open_orders(pos.symbol)
        except Exception:
            existing = []
        have_stop = any(
            _order_has_trigger(o, pos.stop) for o in existing
        )
        have_target = any(
            _order_has_trigger(o, pos.target) for o in existing
        )
        if have_stop and have_target:
            pos.protective = True
            return
        params: dict = {"reduceOnly": True}
        if self.settings.exchange_id == "bybit":
            params["positionIdx"] = 0
        try:
            if pos.stop is not None and not have_stop:
                await self.adapter.exchange.create_order(
                    symbol=self.adapter.sym(pos.symbol), type="market", side=side,
                    amount=pos.qty, price=None,
                    params={**params,
                            "stopLoss": {"triggerPrice": pos.stop, "orderType": "Market"},
                            "clientOrderId": make_client_order_id("sl", pos.symbol,
                                                                 str(pos.stop))},
                )
            if pos.target is not None and not have_target:
                await self.adapter.exchange.create_order(
                    symbol=self.adapter.sym(pos.symbol), type="limit", side=side,
                    amount=pos.qty, price=pos.target,
                    params={**params, "clientOrderId": make_client_order_id(
                        "tp", pos.symbol, str(pos.target))},
                )
            pos.protective = True
            self.store.log_event(
                f"KORUMA EMRILERI ASILDI {pos.symbol} stop={pos.stop} target={pos.target}",
                source="live")
        except Exception as exc:
            self.store.log_event(
                f"KORUMA EMRI HATASI {pos.symbol}: {exc}", level="error", source="live")

    async def _software_stop(self, pos: TrackedPosition, raw_position: dict) -> None:
        """Borsa stopu yoksa yazilim stopu ile kapat (yedek)."""
        if pos.stop is None:
            return
        mark = float(raw_position.get("markPrice") or 0.0)
        if mark <= 0:
            return
        hit = (pos.side == "long" and mark <= pos.stop) or \
              (pos.side == "short" and mark >= pos.stop)
        if not hit:
            return
        client_id = make_client_order_id("sstop", self.strategy.name, pos.symbol,
                                         str(pos.stop))
        if client_id in self.orders:
            return
        side = "sell" if pos.side == "long" else "buy"
        params = {"reduceOnly": True}
        if self.settings.exchange_id == "bybit":
            params["positionIdx"] = 0
        try:
            order = await self.adapter.exchange.create_order(
                symbol=self.adapter.sym(pos.symbol), type="market", side=side,
                amount=pos.qty, price=None,
                params={**params, "clientOrderId": client_id},
            )
            self._track_order(order)
            self.store.log_event(
                f"YAZILIM STOPU TETIKLENDI {pos.symbol} mark={mark} stop={pos.stop}",
                level="warn", source="live")
        except Exception as exc:
            self.store.log_event(f"Yazilim stopu hatasi: {exc}", level="error", source="live")

    def _last_price(self, symbol: str) -> float:
        pos = self.positions.get(symbol)
        if pos and pos.entry_price:
            return pos.entry_price
        return 0.0

    # ==================================================================
    # 4) ANA DONGU
    # ==================================================================

    async def run_forever(self) -> None:
        from .notify import fmt_start

        decision = gate_check(self.strategy, self.mode)
        if not decision.allowed:
            raise PermissionError(decision.reason)

        await self.reconcile()
        self.store.log_event(
            f"Live motoru basladi: {self.strategy.name} mod={self.mode} "
            f"semboller={','.join(self.symbols)}", source="live")
        await self.notifier.send(fmt_start(
            "TESTNET (sahte para)" if self.mode == "testnet" else "CANLI",
            self.strategy.name, self.symbols))
        try:
            while not self._stop:
                try:
                    await self.manage()
                    await self.scan()
                    self.store.set_kv(f"risk_state:{self.strategy.name}", self.risk.state())
                except Exception as exc:
                    self.store.log_event(f"Dongu hatasi: {exc}", level="error", source="live")
                await asyncio.sleep(self.poll_seconds)
        finally:
            self.store.set_kv(f"risk_state:{self.strategy.name}", self.risk.state())

    def stop(self) -> None:
        self._stop = True


# --------------------------------------------------------------------------
# yardimcilar
# --------------------------------------------------------------------------

def _client_id_of(raw: dict) -> str | None:
    for key in ("clientOrderId", "orderLinkId", "newClientOrderId"):
        value = raw.get(key)
        if value:
            return str(value)
    info = raw.get("info") or {}
    if isinstance(info, dict):
        for key in ("clientOrderId", "orderLinkId", "newClientOrderId"):
            value = info.get(key)
            if value:
                return str(value)
    return None


def _strip(symbol: str) -> str:
    if "/" not in symbol:
        return symbol
    base, _, rest = symbol.partition("/")
    return f"{base}{rest.split(':')[0]}"


def _position_qty(raw: dict) -> float:
    """Pozisyon miktarini borsa formatindan cikar (contracts/amount/size)."""
    for key in ("contracts", "amount", "size", "positionAmt", "qty"):
        value = raw.get(key)
        if value in (None, ""):
            continue
        try:
            qty = abs(float(value))
        except (TypeError, ValueError):
            continue
        if qty > 0:
            return qty
    return 0.0


def _position_side(raw: dict) -> str:
    """Pozisyon yonu: ccxt unified 'long'/'short'; bybit raw 'Buy'/'Sell'."""
    value = raw.get("side")
    text = str(value).strip().lower() if value is not None else ""
    if text in ("long", "buy", "1"):
        return "long"
    if text in ("short", "sell", "-1", "2"):
        return "short"
    info = raw.get("info") or {}
    if isinstance(info, dict):
        text = str(info.get("side") or "").strip().lower()
        if text in ("buy", "long", "1"):
            return "long"
        if text in ("sell", "short", "2", "-1"):
            return "short"
        try:
            idx = int(info.get("positionIdx", 0))
            return "long" if idx == 0 else "short"
        except (TypeError, ValueError):
            pass
    return "long"


def _order_has_trigger(raw: dict, price: float | None) -> bool:
    if price is None:
        return False
    info = raw.get("info") or {}
    if not isinstance(info, dict):
        return False
    candidates = [
        raw.get("stopLossPrice"), raw.get("takeProfitPrice"),
        info.get("stopLoss"), info.get("takeProfit"),
        info.get("triggerPrice"),
    ]
    sl = info.get("stopLoss")
    if isinstance(sl, dict):
        candidates.append(sl.get("triggerPrice"))
    tp = info.get("takeProfit")
    if isinstance(tp, dict):
        candidates.append(tp.get("triggerPrice"))
    for c in candidates:
        if c in (None, ""):
            continue
        try:
            if abs(float(c) - float(price)) < 1e-8:
                return True
        except (TypeError, ValueError):
            continue
    return False
