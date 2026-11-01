"""Plan B ortak sermayeli, günlük, çok sembollü portföy motoru.

Bu modül SİNYAL ÜRETMEZ. Her sembol için önceden hesaplanmış günlük sütunları
(entry_signal, exit_signal, atr) alır ve yürütür. Sinyal/kanal/ATR hesabı ayrı
modüldedir (Plan B strateji PR'ı).

Kurallar: DEVIR_NOTU §9 + docs/SPEC_EKLERI.md E3b, E3c, E5, E5b, E6, E7, E7b, E8,
E11, E12, E13. Maliyet modeli V2 motoruyla aynı (config.BacktestParams):
market giriş/çıkışlar ve stop-market = taker; tüm dolumlarda aleyhe slippage.

Girdi biçimi
------------
frames: {sembol: DataFrame}, index = UTC gün indeksi (int, 1970-01-01'den gün),
sütunlar: open, high, low, close, entry_signal (bool), exit_signal (bool), atr (float).
Sinyaller ve atr o günün KAPANIŞINDA bilinen değerlerdir (hesaplayan modülün sorumluluğu).

Bir günün akışı (D, takvim = dönem içinde en az bir sembolün barı olan günler, E12)
-----------------------------------------------------------------------------------
Açılış (yalnız D'de barı olan semboller):
  1. Bekleyen kanal çıkışları (E6/E5b/E11): açılış × (1 − slip), taker. Açılış stopun
     altında olsa da sebep 'channel_exit' (E11) ve sayaç artar. Kontenjan HEMEN boşalır.
  2. Gap stop: kanal çıkışı beklemeyen pozisyonda açılış <= stop → açılış × (1 − slip),
     taker, sebep 'stop'. Kontenjan ertesi güne kadar dolu sayılır (E7b).
  3. Yeni girişler (E7/E7b): önceki takvim gününün (D−1) kapanışında üretilmiş giriş
     sinyalleri, öncelik sırasıyla (BTC, ETH, SOL, BNB). D'de barı olmayan sembolün
     sinyali iptal (E5b). Boş kontenjana sığmayan sinyal iptal. Boyut = açılış öncesi
     gerçekleşmiş bakiye (D−1 sonu) × risk ÷ (2 × ATR_sinyal_günü). Dolum = açılış ×
     (1 + slip), taker. Stop = dolum − 2 × ATR (sabit, E6).
Gün içi:
  4. Stop: low <= stop → min(stop, açılış) × (1 − slip), taker, sebep 'stop' (giriş
     günü dahil; giriş günü açılış stopun altındaysa açılış fiyatı).
     Kontenjan ertesi güne kadar dolu (E7b).
Kapanış:
  5. Açık pozisyonda exit_signal → bekleyen kanal çıkışı (sembolün sonraki mevcut
     barının açılışında yürütülür; E5b).
  6. Pozisyonsuz sembolde entry_signal → yalnız ertesi takvim günü için bekleyen giriş.
  7. Günlük equity (E12/E15) = gerçekleşmiş bakiye + açık pozisyonların (son mevcut
     kapanış − giriş) × miktar − giriş ücreti − o güne kadar (o gün dahil) biriken
     funding. Çıkış ücreti dahil değildir.

Funding (E8): nominal = dolum × miktar; açık kalınan her UTC takvim günü (giriş ve
çıkış günü dahil) × %0,03; kapanışta PnL'den düşülür.

Dönem sonu (E3b/E5b/E13): her sembolün dönem içindeki SON mevcut barının kapanışında
(adım 5'te, o günün akışı içinde) açık pozisyonu × (1 − slip), taker, sebep 'period_end'
ile tasfiye edilir; funding o güne kadar sayılır. Kontenjan ve bakiye sonraki günlerde
bunu görür. Son barda yeni çıkış/giriş emri üretilmez; bekleyen emirler kendiliğinden
iptal olur. Not: "son mevcut bar" dönem sonu verisiyle belirlenir (E13 tanımı).

Sermaye tükenmesi (E16): açılış öncesi gerçekleşmiş bakiye <= 0 ise yeni giriş yapılmaz
(entries_blocked_no_capital); açık pozisyonlar kurallarına göre kapanır. Hesaplanan
miktar pozitif ve sonlu değilse giriş yapılmaz (long-only).

Dönem başı (E3c): bakiye = initial_balance, pozisyon ve bekleyen emir yok. Dönem
başından önceki sinyaller hiçbir emir üretmez (yalnız gösterge ısınması içindir).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import BacktestParams

PRIORITY = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")
REQUIRED = ("open", "high", "low", "close", "entry_signal", "exit_signal", "atr")


@dataclass(frozen=True)
class PlanBParams:
    initial_balance: float = 10_000.0     # E7b
    risk_per_trade: float = 0.005         # §9
    max_positions: int = 2                # §9
    atr_mult: float = 2.0                 # §9 / E6
    funding_per_day: float = 0.0003       # E8
    taker_fee: float = BacktestParams.taker_fee        # maliyet modeli aynı
    slippage_rate: float = BacktestParams.slippage_rate


@dataclass
class PBTrade:
    symbol: str
    entry_day: int
    exit_day: int
    entry: float
    exit: float
    stop: float
    qty: float
    risk_amount: float
    entry_fee: float
    exit_fee: float
    funding: float
    reason: str
    pnl: float

    @property
    def pnl_r(self) -> float:
        return self.pnl / self.risk_amount if self.risk_amount else 0.0


@dataclass
class _Pos:
    symbol: str
    entry_day: int
    entry: float
    stop: float
    qty: float
    risk_amount: float
    entry_fee: float
    last_close: float
    exit_pending: bool = False


@dataclass
class PBResult:
    trades: list = field(default_factory=list)
    equity: pd.Series | None = None          # index: gün indeksi
    counters: dict = field(default_factory=dict)
    missing_day_valuations: dict = field(default_factory=dict)

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def profit_factor(self) -> float:
        gp = sum(t.pnl for t in self.trades if t.pnl > 0)
        gl = abs(sum(t.pnl for t in self.trades if t.pnl <= 0))
        if gl == 0:
            return float("inf") if gp > 0 else 0.0
        return gp / gl

    @property
    def max_drawdown(self) -> float:
        if self.equity is None or len(self.equity) == 0:
            return 0.0
        eq = self.equity.to_numpy(dtype=float)
        peak = np.maximum.accumulate(eq)
        return float(((peak - eq) / peak).max())

    @property
    def final_balance(self) -> float:
        return float(self.equity.iloc[-1]) if self.equity is not None and len(self.equity) else 0.0


class PortfolioError(ValueError):
    pass


def _validate(frames: dict, priority) -> None:
    for sym, df in frames.items():
        if sym not in priority:
            raise PortfolioError(f"{sym}: öncelik listesinde yok")
        missing = [c for c in REQUIRED if c not in df.columns]
        if missing:
            raise PortfolioError(f"{sym}: eksik sütun {missing}")
        if not df.index.is_monotonic_increasing or df.index.has_duplicates:
            raise PortfolioError(f"{sym}: gün indeksi sıralı/tekil değil")


def run_portfolio(frames: dict, start_day: int, end_day: int,
                  p: PlanBParams = PlanBParams(), priority=PRIORITY) -> PBResult:
    """start_day..end_day (dahil) dönemini çalıştırır. Gün indeksleri int."""
    _validate(frames, priority)
    order = [s for s in priority if s in frames]
    bars = {s: {int(d): row for d, row in zip(frames[s].index, frames[s].itertuples(index=False))}
            for s in order}
    calendar = sorted({d for s in order for d in bars[s] if start_day <= d <= end_day})
    # E5b/E13: her sembolün dönem içindeki son mevcut barı (tasfiye o barın kapanışında)
    last_in_period = {s: max((d for d in bars[s] if start_day <= d <= end_day), default=None)
                      for s in order}

    res = PBResult(counters={
        "channel_exits": 0, "channel_exit_through_stop": 0, "deferred_channel_exits": 0,
        "gap_stops": 0, "stops": 0, "entry_day_stops": 0,
        "entries_cancelled_capacity": 0, "entries_cancelled_missing_bar": 0,
        "entries_skipped_invalid_atr": 0, "entries_blocked_no_capital": 0,
        "forced_closes": 0,
    })
    res.missing_day_valuations = {s: 0 for s in order}
    slip, fee, fund = p.slippage_rate, p.taker_fee, p.funding_per_day

    balance = p.initial_balance
    positions: dict[str, _Pos] = {}
    pending_entries: dict[str, tuple[int, float]] = {}   # sembol -> (sinyal günü, atr)
    locked_until: dict[str, int] = {}                    # stop kontenjanı: bu güne kadar (hariç) dolu
    last_bar_day: dict[str, int] = {}
    equity_days, equity_vals = [], []

    def close_pos(pos: _Pos, price: float, day: int, reason: str) -> None:
        nonlocal balance
        exit_fee = price * pos.qty * fee
        funding = pos.entry * pos.qty * fund * (day - pos.entry_day + 1)
        pnl = (price - pos.entry) * pos.qty - pos.entry_fee - exit_fee - funding
        balance += pnl
        res.trades.append(PBTrade(pos.symbol, pos.entry_day, day, pos.entry, price, pos.stop,
                                  pos.qty, pos.risk_amount, pos.entry_fee, exit_fee, funding,
                                  reason, pnl))
        del positions[pos.symbol]

    for D in calendar:
        balance_before_open = balance
        # sinyal günü D−1 olmayan bekleyen girişler: sembolün D'de barı yok → iptal (E5b)
        for s in list(pending_entries):
            sig_day, _ = pending_entries[s]
            if sig_day != D - 1 or D not in bars[s]:
                res.counters["entries_cancelled_missing_bar"] += 1
                del pending_entries[s]

        # 1-2. açılış çıkışları
        for s in order:
            pos = positions.get(s)
            if pos is None or D not in bars[s]:
                continue
            o = bars[s][D].open
            if pos.exit_pending:
                if last_bar_day.get(s, D) < D - 1:
                    res.counters["deferred_channel_exits"] += 1
                if o <= pos.stop:
                    res.counters["channel_exit_through_stop"] += 1
                res.counters["channel_exits"] += 1
                close_pos(pos, o * (1 - slip), D, "channel_exit")
            elif o <= pos.stop:
                res.counters["gap_stops"] += 1
                res.counters["stops"] += 1
                close_pos(pos, o * (1 - slip), D, "stop")
                locked_until[s] = D + 1

        # 3. yeni girişler
        for s in order:
            if s not in pending_entries:
                continue
            sig_day, atr = pending_entries.pop(s)
            occupied = len(positions) + sum(1 for x, u in locked_until.items() if u > D)
            if occupied >= p.max_positions:
                res.counters["entries_cancelled_capacity"] += 1
                continue
            if not (atr > 0 and math.isfinite(atr)):
                res.counters["entries_skipped_invalid_atr"] += 1
                continue
            if not balance_before_open > 0:           # E16: sermaye tükendi
                res.counters["entries_blocked_no_capital"] += 1
                continue
            bar = bars[s][D]
            fill = bar.open * (1 + slip)
            dist = p.atr_mult * atr
            risk_amount = balance_before_open * p.risk_per_trade
            qty = risk_amount / dist
            if not (qty > 0 and math.isfinite(qty)):  # long-only: miktar daima pozitif
                res.counters["entries_skipped_invalid_atr"] += 1
                continue
            positions[s] = _Pos(s, D, fill, fill - dist, qty, risk_amount,
                                fill * qty * fee, bar.close)

        # 4. gün içi stop
        for s in order:
            pos = positions.get(s)
            if pos is None or D not in bars[s]:
                continue
            if bars[s][D].low <= pos.stop:
                res.counters["stops"] += 1
                if pos.entry_day == D:
                    res.counters["entry_day_stops"] += 1
                # giriş günü açılış stopun altındaysa (çok küçük ATR) dolum açılıştan
                px = min(pos.stop, bars[s][D].open)
                close_pos(pos, px * (1 - slip), D, "stop")
                locked_until[s] = D + 1

        # 5-6. kapanış: dönem içindeki son barında tasfiye (E3b/E5b/E13), aksi halde sinyaller
        for s in order:
            if D not in bars[s]:
                continue
            bar = bars[s][D]
            pos = positions.get(s)
            last_bar_day[s] = D
            if D == last_in_period[s]:
                if pos is not None:
                    pos.last_close = bar.close
                    res.counters["forced_closes"] += 1
                    close_pos(pos, bar.close * (1 - slip), D, "period_end")
                continue                      # son barda yeni emir üretilmez
            if pos is not None:
                pos.last_close = bar.close
                if bool(bar.exit_signal):
                    pos.exit_pending = True
            elif bool(bar.entry_signal):
                pending_entries[s] = (D, float(bar.atr))

        # 7. equity (E12: barı olmayan sembol son kapanışla)
        eq = balance
        for s, pos in positions.items():
            if D not in bars[s]:
                res.missing_day_valuations[s] += 1
            eq += ((pos.last_close - pos.entry) * pos.qty - pos.entry_fee
                   - pos.entry * pos.qty * fund * (D - pos.entry_day + 1))
        equity_days.append(D)
        equity_vals.append(eq)

    if positions:  # her açık pozisyonun sembolü dönem içinde son barına ulaşmış olmalı
        raise PortfolioError(f"dönem sonunda kapanmamış pozisyon: {sorted(positions)}")
    res.equity = pd.Series(equity_vals, index=pd.Index(equity_days, name="day"), dtype=float)
    return res
