"""V3 çok sembollü 15m yürütme motoru (docs/V3_SPEC_TASLAK.md §4.4–§5, §6a).

Niyetleri (strategy_v3.Intent) alır; boyut, dolum, stop/hedef/gap/zaman çıkışı,
funding, muhasebe günü, 15m MTM equity, sermaye tükenmesi ve günlük seri burada.

Bir zaman damgasındaki (ts) akış:
  A) Açılış (o ts'de mumu olan her sembol):
     (0) vadesi geçmiş pozisyon (gününün 23:45 mumu eksikti) → bekleyen zaman çıkışı:
         open × (1 ∓ s), taker; o mumda başka kontrol yok.
     Bekleyen emir: dolum mumu tam t+15dk ise dolum F = open × (1 ± s), taker; ham
         açılış veya F stop ötesindeyse acil çıkış open × (1 ∓ s), taker
         (gap_through_stop). Dolum mumu yoksa (sembolün sonraki mumu daha geç) iptal.
     Giriş mumu olmayan pozisyonda: açılış stop ötesinde → gap_stop open × (1 ∓ s),
         taker; açılış hedefin katı ötesinde → gap_target T, maker, slippage yok.
  B) Mum içi: stop teması (LONG low ≤ M) → M × (1 ∓ s), taker (aynı mumda hedef de
     olsa stop); değilse hedef katı aşımı (LONG high > T) → T, maker.
  C) 23:45 mumunda hâlâ açıksa kapanışta zaman çıkışı close × (1 ∓ s), taker.
  D) Damga sonu: tüm çıkışlardan sonra bakiye ≤ 0 → sermaye tükendi (kalıcı).
     Equity (MTM, son mevcut kapanış; tahakkuk eden funding değerleme anı = mum
     kapanışı ts + 15dk'ya kadar, o an dahil). Bu damgada kapanan tetiklerden emir:
     miktar = risk × bakiye ÷ |P − M| (bakiye bu damganın çıkışlarından sonra).
Funding: [dolum anı, çıkış anı] içindeki her 00/08/16 UTC anı için nominal × oran;
dolum veya çıkış tam o ana denk gelirse ödenir. Çıkış anı: açılış çıkışlarında mumun
açılışı, mum içi çıkışlarda mumun açılışı (o an pozisyon açıktı), normal zaman
çıkışında 23:45 + 15dk (= 00:00).
Muhasebe günü: normal zaman çıkışı → 23:45 mumunun günü; diğerleri → yürütme mumunun
açılış günü.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .strategy_v3 import BAR_MS, DAY_MS, LAST_SLOT, RR, Intent

FUNDING_HOURS = (0, 8, 16)
HOUR_MS = 3_600_000


@dataclass(frozen=True)
class V3Params:
    initial_balance: float = 10_000.0
    risk_per_trade: float = 0.01      # Z2 [SAPMA]
    taker_fee: float = 0.00055
    maker_fee: float = 0.0002
    slippage: float = 0.0003
    funding_rate: float = 0.0001


@dataclass
class V3Trade:
    symbol: str
    side: str
    fill_ts: int
    exit_ts: int          # funding için yürütme anı
    acct_day: int
    entry: float
    exit: float
    stop: float
    target: float
    qty: float
    risk_usd: float
    entry_fee: float
    exit_fee: float
    funding: float
    reason: str
    pnl: float

    @property
    def r(self) -> float:
        return self.pnl / self.risk_usd if self.risk_usd else 0.0


@dataclass
class _Pos:
    symbol: str
    side: str
    fill_ts: int
    F: float
    M: float
    T: float
    qty: float
    risk_usd: float
    entry_fee: float
    due_ts: int           # gününün 23:45 mumu açılışı
    last_close: float


@dataclass
class _Order:
    intent: Intent
    qty: float
    risk_usd: float
    fill_ts: int


@dataclass
class V3Result:
    trades: list = field(default_factory=list)
    equity: pd.Series | None = None
    counters: dict = field(default_factory=dict)
    capital_exhausted: bool = False
    start_day: int = 0
    end_day: int = 0

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

    def daily_returns(self, initial: float) -> pd.Series:
        """§6a: dönemin TÜM UTC günleri; r_d = o güne yazılan net PnL ÷ başlangıç."""
        days = pd.Index(range(self.start_day, self.end_day + 1), name="day")
        s = pd.Series(0.0, index=days)
        for t in self.trades:
            s.loc[t.acct_day] += t.pnl
        return s / initial


def funding_count(fill_ts: int, exit_ts: int) -> int:
    """[fill_ts, exit_ts] (iki uç dahil) aralığındaki 00/08/16 UTC anı sayısı."""
    n = 0
    first = (fill_ts // (8 * HOUR_MS)) * 8 * HOUR_MS
    t = first if first >= fill_ts else first + 8 * HOUR_MS
    while t <= exit_ts:
        n += 1
        t += 8 * HOUR_MS
    return n


def newey_west_t(x: np.ndarray) -> tuple[float, float, int, float]:
    """Ortalama, HAC standart hata (Bartlett, L = floor(4(T/100)^(2/9))), t. SE ≤ 0 → t = nan."""
    x = np.asarray(x, dtype=float)
    T = len(x)
    L = int(math.floor(4 * (T / 100) ** (2 / 9)))
    m = x.mean()
    e = x - m
    var = float(e @ e) / T
    for k in range(1, L + 1):
        w = 1 - k / (L + 1)
        var += 2 * w * float(e[k:] @ e[:-k]) / T
    se = math.sqrt(var / T) if var > 0 else 0.0
    t = m / se if se > 0 else float("nan")
    return m, se, L, t


def run_v3(bars: dict, intents: dict, start_day: int, end_day: int,
           p: V3Params = V3Params()) -> V3Result:
    """bars: {sembol: DataFrame(open/high/low/close), index = açılış ms}.
    intents: {sembol: [Intent]}. Dönem: start_day 00:00 → end_day 23:45 mumu (dahil)."""
    lo, hi = start_day * DAY_MS, (end_day + 1) * DAY_MS
    data = {}
    for s, df in bars.items():
        d = df[(df.index >= lo) & (df.index < hi)]
        data[s] = {int(t): (float(a), float(b), float(c), float(e))
                   for t, a, b, c, e in zip(d.index, d["open"], d["high"], d["low"], d["close"])}
    timeline = sorted({t for s in data for t in data[s]})
    by_trigger: dict[int, list] = {}
    for s, lst in intents.items():
        for it in lst:
            if start_day <= it.day <= end_day:
                by_trigger.setdefault(it.trigger_ts, []).append(it)

    s_, tk, mk, fr = p.slippage, p.taker_fee, p.maker_fee, p.funding_rate
    res = V3Result(start_day=start_day, end_day=end_day, counters={
        "orders": 0, "orders_cancelled_missing_fill_bar": 0, "orders_skipped_busy": 0,
        "orders_blocked_no_capital": 0, "gap_through_stop": 0, "gap_stop": 0, "gap_target": 0,
        "stop": 0, "target": 0, "time_exit": 0, "time_exit_deferred": 0,
        "mtm_carried_marks": 0,
    })
    balance = p.initial_balance
    pos: dict[str, _Pos] = {}
    orders: dict[str, _Order] = {}
    eq_ts, eq_val = [], []

    def close(sym: str, price: float, exec_ts: int, funding_ts: int, acct_day: int,
              reason: str, maker: bool) -> None:
        nonlocal balance
        q = pos.pop(sym)
        sign = 1.0 if q.side == "long" else -1.0
        exit_fee = price * q.qty * (mk if maker else tk)
        funding = q.F * q.qty * fr * funding_count(q.fill_ts, funding_ts)
        pnl = sign * (price - q.F) * q.qty - q.entry_fee - exit_fee - funding
        balance += pnl
        res.counters[reason] += 1
        res.trades.append(V3Trade(sym, q.side, q.fill_ts, funding_ts, acct_day, q.F, price, q.M,
                                  q.T, q.qty, q.risk_usd, q.entry_fee, exit_fee, funding, reason, pnl))

    for ts in timeline:
        day = ts // DAY_MS
        slot = (ts % DAY_MS) // BAR_MS
        for sym in data:
            bar = data[sym].get(ts)
            if bar is None:
                continue
            o, h, l, c = bar
            entry_bar = False
            # A(0) bekleyen zaman çıkışı
            q = pos.get(sym)
            if q is not None and ts > q.due_ts:
                adv = o * (1 - s_) if q.side == "long" else o * (1 + s_)
                close(sym, adv, ts, ts, day, "time_exit_deferred", maker=False)
                continue
            # A: bekleyen emir
            od = orders.get(sym)
            if od is not None:
                del orders[sym]
                if ts != od.fill_ts:
                    res.counters["orders_cancelled_missing_fill_bar"] += 1
                else:
                    it = od.intent
                    long_ = it.side == "long"
                    F = o * (1 + s_) if long_ else o * (1 - s_)
                    T = F + RR * abs(F - it.M) if long_ else F - RR * abs(F - it.M)
                    due = day * DAY_MS + LAST_SLOT * BAR_MS
                    pos[sym] = _Pos(sym, it.side, ts, F, it.M, T, od.qty, od.risk_usd,
                                    F * od.qty * tk, due, c)
                    entry_bar = True
                    beyond = (o <= it.M or F <= it.M) if long_ else (o >= it.M or F >= it.M)
                    if beyond:
                        adv = o * (1 - s_) if long_ else o * (1 + s_)
                        close(sym, adv, ts, ts, day, "gap_through_stop", maker=False)
                        continue
            q = pos.get(sym)
            if q is None:
                continue
            long_ = q.side == "long"
            # A: gap stop / gap hedef (giriş mumu hariç)
            if not entry_bar:
                if (long_ and o <= q.M) or (not long_ and o >= q.M):
                    close(sym, o * (1 - s_) if long_ else o * (1 + s_), ts, ts, day, "gap_stop", False)
                    continue
                if (long_ and o > q.T) or (not long_ and o < q.T):
                    close(sym, q.T, ts, ts, day, "gap_target", maker=True)
                    continue
            # B: mum içi — stop önce, hedef katı aşım
            if (long_ and l <= q.M) or (not long_ and h >= q.M):
                px = q.M * (1 - s_) if long_ else q.M * (1 + s_)
                close(sym, px, ts, ts, day, "stop", False)
                continue
            if (long_ and h > q.T) or (not long_ and l < q.T):
                close(sym, q.T, ts, ts, day, "target", maker=True)
                continue
            q.last_close = c
            # C: normal zaman çıkışı
            if slot == LAST_SLOT:
                close(sym, c * (1 - s_) if long_ else c * (1 + s_), ts, ts + BAR_MS, day,
                      "time_exit", False)
        # D: sermaye, equity, yeni emirler
        if balance <= 0:
            res.capital_exhausted = True
        eq = balance
        for sym, q in pos.items():
            if ts not in data[sym]:
                res.counters["mtm_carried_marks"] += 1
            sign = 1.0 if q.side == "long" else -1.0
            # değerleme anı = bu damganın mum KAPANIŞI (ts + 15dk); o ana denk gelen
            # funding (ör. 07:45 mumunun kapanışı 08:00) bu equity'ye dahildir
            eq += sign * (q.last_close - q.F) * q.qty - q.entry_fee \
                - q.F * q.qty * fr * funding_count(q.fill_ts, ts + BAR_MS)
        eq_ts.append(ts)
        eq_val.append(eq)
        for it in by_trigger.get(ts, []):
            if it.symbol in pos or it.symbol in orders:
                res.counters["orders_skipped_busy"] += 1
                continue
            if res.capital_exhausted or balance <= 0:
                res.counters["orders_blocked_no_capital"] += 1
                continue
            risk_usd = p.risk_per_trade * balance
            qty = risk_usd / abs(it.P - it.M)
            if not (qty > 0 and math.isfinite(qty)):
                continue
            orders[it.symbol] = _Order(it, qty, risk_usd, ts + BAR_MS)
            res.counters["orders"] += 1
    if pos:
        raise RuntimeError(f"dönem sonunda açık pozisyon: {sorted(pos)} (d_son kuralı ihlali)")
    res.counters["orders_pending_at_end"] = len(orders)
    res.equity = pd.Series(eq_val, index=pd.Index(eq_ts, name="ts"), dtype=float)
    return res
