"""Event-driven backtest motoru.

Muhafazakâr varsayımlar (backtest her zaman gerçekten KÖTÜ olmalı, iyi değil):
- Limit entry: bar limit fiyatına dokunursa dolar (low <= entry, long).
  Fill barında stop da vurulmuşsa → İLK STOP sayılır (intra-bar sıra bilinemez).
- Aynı barda hem stop hem target → STOP sayılır.
- Stop çıkışı: stop-market → slippage aleyhe + taker fee.
- Entry ve target: limit → maker fee.
- Emir iptali: fill olmadan close FVG'yi tamamen geçerse veya süre dolarsa.
- Tek pozisyon: bir pozisyonun KAPANDIĞI barda yeni fill alınmaz (barın başında
  pozisyon hâlâ açıktı; bar içi çıkışı bilip yer açmak lookahead olur).
- Stop gap: bar stopun ötesinde açılırsa çıkış açılış fiyatından (stop'tan değil).
- liquidate_at_end=True (V2 protokolü): dönem sonunda açık pozisyon zorla
  kapatılır (reason="period_end", taker + aleyhe slippage).
- Gap stopu veya hedefi geçerse (dolum stopun/hedefin ötesinde): işlem GERÇEKLEŞİR
  ve aynı barda hemen kapanır, giriş+çıkış ücreti ve slippage ödenir
  (gap_stopouts / gap_target_exits). Çıkış slippage'i ham açılıştan. Market emir açılışta dolduğu için, stop vurulmamışsa
  aynı bardaki hedef teması da işlenir; limit emirde giriş barı hedef teması
  sayılmaz (bar içi sıra bilinmez).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import BacktestParams
from .strategy import PendingOrder


@dataclass
class ClosedTrade:
    side: str
    entry: float
    stop: float
    target: float
    exit_price: float
    exit_reason: str        # "stop" | "target" | "gap_target" | "period_end" (donem sonu tasfiyesi)
    entry_idx: int
    exit_idx: int
    pnl_usd: float
    pnl_r: float
    risk_amount: float
    position_size: float
    meta: dict = field(default_factory=dict)

    @property
    def is_win(self) -> bool:
        return self.pnl_usd > 0


@dataclass
class BacktestResult:
    trades: list[ClosedTrade] = field(default_factory=list)
    equity_curve: pd.Series | None = None
    cancelled_orders: int = 0
    expired_orders: int = 0
    invalid_geometry_orders: int = 0
    gap_stopouts: int = 0
    gap_target_exits: int = 0
    forced_closes: int = 0

    # --- metrikler ---
    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> list[ClosedTrade]:
        return [t for t in self.trades if t.is_win]

    @property
    def losses(self) -> list[ClosedTrade]:
        return [t for t in self.trades if not t.is_win]

    @property
    def win_rate(self) -> float:
        return len(self.wins) / len(self.trades) if self.trades else 0.0

    @property
    def profit_factor(self) -> float:
        gp = sum(t.pnl_usd for t in self.wins)
        gl = abs(sum(t.pnl_usd for t in self.losses))
        if gl == 0:
            return float("inf") if gp > 0 else 0.0
        return gp / gl

    @property
    def expectancy_r(self) -> float:
        if not self.trades:
            return 0.0
        return float(np.mean([t.pnl_r for t in self.trades]))

    @property
    def max_drawdown(self) -> float:
        if self.equity_curve is None or len(self.equity_curve) == 0:
            return 0.0
        eq = self.equity_curve.to_numpy()
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / peak
        return float(dd.max())

    def sharpe(self, bars_per_year: float) -> float:
        """Bar bazlı equity getirilerinden yıllıklandırılmış Sharpe."""
        if self.equity_curve is None or len(self.equity_curve) < 3:
            return 0.0
        rets = self.equity_curve.pct_change().dropna()
        if rets.std() == 0:
            return 0.0
        return float(rets.mean() / rets.std() * np.sqrt(bars_per_year))

    def summary(self, bars_per_year: float = 365 * 96) -> dict:
        by_session: dict[str, list[float]] = {}
        for t in self.trades:
            by_session.setdefault(t.meta.get("session", "?"), []).append(t.pnl_r)
        return {
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 3),
            "expectancy_r": round(self.expectancy_r, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "sharpe": round(self.sharpe(bars_per_year), 2),
            "final_balance": round(float(self.equity_curve.iloc[-1]), 2)
            if self.equity_curve is not None and len(self.equity_curve)
            else None,
            "longs": sum(1 for t in self.trades if t.side == "long"),
            "shorts": sum(1 for t in self.trades if t.side == "short"),
            "cancelled_orders": self.cancelled_orders,
            "expired_orders": self.expired_orders,
            "invalid_geometry_orders": self.invalid_geometry_orders,
            "gap_stopouts": self.gap_stopouts,
            "gap_target_exits": self.gap_target_exits,
            "forced_closes": self.forced_closes,
            "avg_win_r": round(
                float(np.mean([t.pnl_r for t in self.wins])), 3
            ) if self.wins else 0.0,
            "avg_loss_r": round(
                float(np.mean([t.pnl_r for t in self.losses])), 3
            ) if self.losses else 0.0,
            "session_expectancy_r": {
                k: round(float(np.mean(v)), 3) for k, v in sorted(by_session.items())
            },
        }


@dataclass
class _OpenPosition:
    order: PendingOrder
    entry_idx: int
    position_size: float
    risk_amount: float
    entry_fee: float
    entry_price: float = 0.0  # gerçek fill fiyatı (market'te open, limitte entry)


class Backtester:
    def __init__(self, params: BacktestParams = BacktestParams()):
        self.p = params

    def run(
        self,
        df: pd.DataFrame,
        orders: list[PendingOrder],
        liquidate_at_end: bool = False,
    ) -> BacktestResult:
        open_ = df["open"].to_numpy(dtype=float)
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        close = df["close"].to_numpy(dtype=float)
        n = len(df)

        # Emirleri oluşturulma barına göre grupla
        by_created: dict[int, list[PendingOrder]] = {}
        for o in orders:
            by_created.setdefault(o.created_idx, []).append(o)

        result = BacktestResult()
        balance = self.p.initial_balance
        equity = np.full(n, np.nan)

        pending: list[PendingOrder] = []
        open_pos: _OpenPosition | None = None

        for i in range(n):
            closed_this_bar = False
            # --- 1) Açık pozisyon yönetimi (bu barın high/low'una göre) ---
            if open_pos is not None and i > open_pos.entry_idx:
                o = open_pos.order
                exit_price = None
                reason = None
                if o.side == "long":
                    if low[i] <= o.stop:
                        # gap: bar stopun altında açıldıysa açılıştan çıkılır
                        exit_price = min(o.stop, open_[i]) * (1 - self.p.slippage_rate)
                        reason = "stop"
                    elif high[i] >= o.target:
                        exit_price = o.target
                        reason = "target"
                else:
                    if high[i] >= o.stop:
                        exit_price = max(o.stop, open_[i]) * (1 + self.p.slippage_rate)
                        reason = "stop"
                    elif low[i] <= o.target:
                        exit_price = o.target
                        reason = "target"

                if exit_price is not None:
                    balance = self._close(
                        result, open_pos, exit_price, reason, i, balance
                    )
                    open_pos = None
                    closed_this_bar = True

            # --- 2) Pending emirler: süre / fill / iptal ---
            still_pending: list[PendingOrder] = []
            for o in pending:
                if i > o.expiry_idx:
                    result.expired_orders += 1
                    continue

                # SIRA ÖNEMLİ: önce fill, sonra iptal kontrolü.
                # Fiyat FVG'yi geçip kapanıyorsa limit zaten dolmuştur;
                # önce iptal edilirse gerçekleşecek KAYIP işlemler atlanır
                # (anti-muhafazakâr olurdu).
                if o.market:
                    filled = True  # market: ilk barın open'ında dolar
                    fill_price = (
                        open_[i] * (1 + self.p.slippage_rate)
                        if o.side == "long"
                        else open_[i] * (1 - self.p.slippage_rate)
                    )
                    fee_rate = self.p.taker_fee
                else:
                    filled = (
                        low[i] <= o.entry if o.side == "long" else high[i] >= o.entry
                    )
                    fill_price = o.entry
                    fee_rate = self.p.maker_fee
                    # limit emir stopun ÖTESİNDE açılan barda dolduysa gerçek dolum
                    # açılış fiyatıdır (aşağıdaki gap-through-stop yolu işler)
                    if filled and (
                        open_[i] <= o.stop if o.side == "long" else open_[i] >= o.stop
                    ):
                        fill_price = open_[i]
                if filled and open_pos is None and not closed_this_bar:
                    long_ = o.side == "long"
                    through_stop = (
                        fill_price <= o.stop if long_ else fill_price >= o.stop
                    )
                    through_target = (
                        fill_price >= o.target if long_ else fill_price <= o.target
                    )
                    if through_stop or through_target:
                        # Gap stopu ya da hedefi geçti: emir zaten gönderildi, dolum
                        # GERÇEKLEŞİR ve hemen kapanır (maliyetsiz iptal iyimser olurdu).
                        #  - stop ötesi: hemen stop (kayıp)
                        #  - hedef ötesi: hemen kapanış (aynı açılış fiyatı, maliyetler dahil)
                        # Çıkış slippage'i HAM açılıştan hesaplanır (giriş slippage'li
                        # fiyata ikinci kez uygulanmaz). Çıkış taker.
                        # Boyut planlanan riskten (sinyal anındaki |entry-stop|).
                        planned = o.risk
                        if planned <= 0:
                            result.cancelled_orders += 1
                            continue
                        risk_amount = balance * self.p.risk_per_trade
                        size = risk_amount / planned
                        entry_fee = fill_price * size * fee_rate
                        pos = _OpenPosition(
                            o, i, size, risk_amount, entry_fee, fill_price
                        )
                        exit_price = open_[i] * (
                            1 - self.p.slippage_rate if long_
                            else 1 + self.p.slippage_rate
                        )
                        reason = "stop" if through_stop else "gap_target"
                        balance = self._close(
                            result, pos, exit_price, reason, i, balance
                        )
                        if through_stop:
                            result.gap_stopouts += 1
                        else:
                            result.gap_target_exits += 1
                        closed_this_bar = True
                        continue
                    real_risk = abs(fill_price - o.stop)
                    if real_risk <= 0:
                        result.cancelled_orders += 1
                        continue
                    risk_amount = balance * self.p.risk_per_trade
                    size = risk_amount / real_risk
                    entry_fee = fill_price * size * fee_rate
                    pos = _OpenPosition(o, i, size, risk_amount, entry_fee, fill_price)

                    # Muhafazakâr: fill barında stop da vurulduysa → anında stop
                    stopped_same_bar = (
                        low[i] <= o.stop if o.side == "long" else high[i] >= o.stop
                    )
                    target_same_bar = (
                        high[i] >= o.target if o.side == "long" else low[i] <= o.target
                    )
                    if stopped_same_bar:
                        exit_price = (
                            o.stop * (1 - self.p.slippage_rate)
                            if o.side == "long"
                            else o.stop * (1 + self.p.slippage_rate)
                        )
                        balance = self._close(
                            result, pos, exit_price, "stop", i, balance
                        )
                        closed_this_bar = True
                    elif o.market and target_same_bar:
                        # Market emir barın AÇILIŞINDA doldu: sıra bellidir, stop
                        # vurulmadıysa hedef teması gerçektir (stop+hedef → stop
                        # önceliği yukarıda zaten uygulandı).
                        balance = self._close(
                            result, pos, o.target, "target", i, balance
                        )
                        closed_this_bar = True
                    else:
                        open_pos = pos
                    continue  # fill oldu (veya aynı bar stop) → pending'den çık
                if filled and (open_pos is not None or closed_this_bar):
                    # Pozisyon doluyken (veya bu barda kapandıysa) fill almayız
                    # (tek pozisyon kuralı; bar içi çıkışı bilerek yer açmak lookahead)
                    result.cancelled_orders += 1
                    continue

                # Fill olmadan FVG tamamen geçildiyse setup geçersiz → iptal
                # (Not: intra-bar'da close her zaman [low, high] içinde olduğundan
                # bu dal pratikte güvenlik ağıdır.)
                if o.side == "long" and close[i] < o.cancel_beyond:
                    result.cancelled_orders += 1
                    continue
                if o.side == "short" and close[i] > o.cancel_beyond:
                    result.cancelled_orders += 1
                    continue
                still_pending.append(o)
            pending = still_pending

            # --- 3) Bu barın kapanışında oluşturulan yeni emirler ---
            for o in by_created.get(i, []):
                if o.risk > 0:
                    pending.append(o)

            # --- 4) Mark-to-market equity ---
            eq = balance
            if open_pos is not None:
                o = open_pos.order
                ep = open_pos.entry_price or o.entry
                if o.side == "long":
                    eq += (close[i] - ep) * open_pos.position_size
                else:
                    eq += (ep - close[i]) * open_pos.position_size
            equity[i] = eq

        # Dönem sonu tasfiyesi (SPEC_EKLERI E3b): açık pozisyon son barın kapanışından,
        # aleyhe slippage + taker ücretle zorla kapatılır ve işlem sayısına dahil edilir.
        if liquidate_at_end and open_pos is not None and n > 0:
            o = open_pos.order
            slip = self.p.slippage_rate
            exit_price = close[-1] * (1 - slip if o.side == "long" else 1 + slip)
            balance = self._close(
                result, open_pos, exit_price, "period_end", n - 1, balance
            )
            result.forced_closes += 1
            equity[n - 1] = balance
            open_pos = None

        result.equity_curve = pd.Series(equity, index=df.index).ffill().fillna(
            self.p.initial_balance
        )
        return result

    def _close(
        self,
        result: BacktestResult,
        pos: _OpenPosition,
        exit_price: float,
        reason: str,
        exit_idx: int,
        balance: float,
    ) -> float:
        o = pos.order
        ep = pos.entry_price or o.entry
        if o.side == "long":
            gross = (exit_price - ep) * pos.position_size
        else:
            gross = (ep - exit_price) * pos.position_size
        # target = limit (maker), stop = stop-market (taker)
        fee_rate = self.p.maker_fee if reason == "target" else self.p.taker_fee
        exit_fee = exit_price * pos.position_size * fee_rate
        pnl = gross - pos.entry_fee - exit_fee
        pnl_r = pnl / pos.risk_amount if pos.risk_amount else 0.0
        balance += pnl
        result.trades.append(
            ClosedTrade(
                side=o.side,
                entry=ep,   # gerçek dolum fiyatı (sinyal fiyatı meta'da)
                stop=o.stop,
                target=o.target,
                exit_price=exit_price,
                exit_reason=reason,
                entry_idx=pos.entry_idx,
                exit_idx=exit_idx,
                pnl_usd=pnl,
                pnl_r=pnl_r,
                risk_amount=pos.risk_amount,
                position_size=pos.position_size,
                meta={**o.meta, "signal_entry": o.entry},
            )
        )
        return balance


def monte_carlo_dd(trades_r: list[float], runs: int = 1000, seed: int = 42) -> dict:
    """İşlem sırasını karıştırarak drawdown dağılımı (R cinsinden)."""
    if not trades_r:
        return {"p95_dd_r": 0.0, "max_dd_r": 0.0}
    rng = np.random.default_rng(seed)
    arr = np.array(trades_r)
    dds = []
    for _ in range(runs):
        perm = rng.permutation(arr)
        eq = np.cumsum(perm)
        peak = np.maximum.accumulate(np.concatenate([[0], eq]))[1:]
        dds.append(float((peak - eq).max()))
    return {
        "p95_dd_r": round(float(np.percentile(dds, 95)), 2),
        "max_dd_r": round(float(np.max(dds)), 2),
    }
