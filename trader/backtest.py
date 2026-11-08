"""Portfoy backtest motoru — coklu sembol, gercekci dolum, muhafazakar varsayimlar.

MUHAFAZAKAR VARSAYIMLAR (motor her zaman gercekten KOTU olmali):
  * Ayni barda hem stop hem hedef vurursa -> STOP sayilir (bar ici sira bilinmez).
  * Limit emir: dolum ancak fiyat seviyeye dokunursa (low <= entry long / high >= entry short).
    Stopun/hedefin OTESINDE gap acilan barda dolum acilis fiyatidir.
  * Market emir: BIR SONRAKI barin open'inda dolar (sinyal barinda degil) -> lookahead yok.
  * Limit giris barinda hedef temasi SAYILMAZ (bar ici sira bilinmez); stop sayilir.
  * Stop gap: bar stopun otesinde acilirsa cikis acilis fiyatindan (stop'tan degil) + slippage.
  * Ucret: limit giris/hedef cikis maker, market giris/stop cikis taker.
  * Slippage daima aleyhe.
  * Funding (perpetual): gercek oranlarla 8 saatte bir; pozisyon acikken uygulanir.
    Pozitif oranda long odar, short alir.
  * Ayni anda tek pozisyon/sembol (net pozisyon).

Lookahead:
  * Sinyal, barin KAPANISINDA uretilir (`generate(panel, ts)`).
  * Market emirler ts'den SONRAKI barin open'inda dolar.
  * Stratejiye yalnizca ts ve oncesi barlar gecer (`history_bars` penceresi).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import CostModel, RiskSettings
from .strategy import Panel, Signal

# --------------------------------------------------------------------------
# Saf (side-effect'siz) yardimcilar — determinizm icin ayri fonksiyonlar
# --------------------------------------------------------------------------


def gross_exposure(positions: dict, targets: dict, prices: dict) -> float:
    """Rebalance sonrasi olusacak BRUT pozisyon tutari.

    NEDEN AYRI BIR FONKSIYON?
      Motor iki seyi birden yapmaliydi: (1) sembolleri sabit sirada gezmek
      ve (2) float toplamini almak. `set` uzerinde gezmek Python'da hash
      sirasina baglidir (`PYTHONHASHSEED` her surecte degisir) ve float
      toplami siraya baglidir (1e16 + 1.0 + 1.0 != 1.0 + 1.0 + 1e16).
      Ikisi birlestiginde sonuc 1 ULP (1e-16) kadar oynuyor, `cap` kontrolu
      `result_gross > cap` seklinde OLDUGU ICIN kenar durumunda karar
      donuyor ve portfoy yorumu kausik sekilde ayrisiyor.

      Burada:
        * semboller `sorted()` ile sabit sirada gezilir,
        * toplam `math.fsum` ile alinir — fsum tam (dogru yuvarlanmis)
          toplam verir ve SIRAYA BAGIMLI DEGILDIR.

      Bu sayede brüt pozisyon toplami, sembollerin hangi sirada
      bulundugundan bagimsiz olarak HER ZAMAN ayni sonucu verir.
    """
    parts: list[float] = []
    for sym in sorted(set(positions) | set(targets)):
        if sym in targets:
            parts.append(abs(targets[sym]))
        else:
            pos = positions[sym]
            mark = prices.get(sym, 0.0) or pos.entry_price
            parts.append(abs(pos.sign * pos.qty * mark))
    return math.fsum(parts)


# --------------------------------------------------------------------------


@dataclass
class Order:
    symbol: str
    side: str                 # "buy" | "sell"
    kind: str                 # "market" | "limit"
    qty: float
    price: float | None = None
    reduce_only: bool = False
    stop: float | None = None
    target: float | None = None
    strategy: str = ""
    client_order_id: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class Position:
    symbol: str
    side: str                 # "long" | "short"
    qty: float
    entry_price: float
    stop: float | None
    target: float | None
    opened_ts: pd.Timestamp
    risk_amount: float
    entry_fee: float = 0.0
    funding_paid: float = 0.0
    strategy: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def sign(self) -> int:
        return 1 if self.side == "long" else -1

    def notional(self, price: float) -> float:
        return abs(self.qty) * price


@dataclass
class ClosedTrade:
    symbol: str
    side: str
    entry: float
    exit: float
    qty: float
    stop: float | None
    target: float | None
    pnl_usd: float
    pnl_r: float
    fees: float
    funding: float
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    exit_reason: str
    strategy: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class BacktestResult:
    trades: list[ClosedTrade] = field(default_factory=list)
    equity_curve: pd.Series | None = None
    initial_equity: float = 0.0
    final_equity: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    funding_paid: float = 0.0
    fees_paid: float = 0.0
    rejected_signals: list[dict] = field(default_factory=list)
    accepted_signals: list[dict] = field(default_factory=list)
    gap_stopouts: int = 0
    kill_switch_triggered: bool = False
    kill_switch_reason: str = ""

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> list[ClosedTrade]:
        return [t for t in self.trades if t.pnl_usd > 0]

    @property
    def losses(self) -> list[ClosedTrade]:
        return [t for t in self.trades if t.pnl_usd <= 0]

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
        if self.equity_curve is None or len(self.equity_curve) < 2:
            return 0.0
        eq = self.equity_curve.to_numpy(dtype=float)
        peak = np.maximum.accumulate(eq)
        dd = (peak - eq) / np.maximum(peak, 1e-12)
        return float(dd.max())


# --------------------------------------------------------------------------


class Backtester:
    """Coklu sembollu, portfoy duzeyinde event-driven backtest."""

    def __init__(
        self,
        costs: CostModel | None = None,
        risk: RiskSettings | None = None,
        initial_equity: float = 10_000.0,
        history_bars: int = 400,
        min_trade_notional: float = 10.0,
    ):
        self.costs = costs or CostModel()
        self.risk = risk or RiskSettings()
        self.initial_equity = initial_equity
        self.history_bars = history_bars
        self.min_trade_notional = min_trade_notional

    # ------------------------------------------------------------------

    def run(
        self,
        data: dict[str, pd.DataFrame],
        strategy,
        funding: dict[str, pd.DataFrame] | None = None,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        apply_kill_switch: bool = True,
    ) -> BacktestResult:
        data = self._slice(data, start, end)
        if not data:
            return BacktestResult(initial_equity=self.initial_equity,
                                  final_equity=self.initial_equity)

        funding = funding or {}
        timeline = sorted(set().union(*[set(df.index) for df in data.values()]))
        # funding oranlari zaman -> (symbol -> toplam oran)
        funding_map = self._funding_map(funding, timeline)

        cash = self.initial_equity
        positions: dict[str, Position] = {}
        pending_market: list[Order] = []
        open_limits: list[Order] = []
        result = BacktestResult(initial_equity=self.initial_equity)
        peak_equity = self.initial_equity
        equity_vals: list[float] = []
        equity_idx: list[pd.Timestamp] = []

        # sinyaller icin pencere (lookahead yok)
        panel_cache: dict[str, pd.DataFrame] = {}

        for t in timeline:
            symbols_at_t = [s for s, df in data.items() if t in df.index]
            if not symbols_at_t:
                continue
            # Bu bardan HENUZ dolmus pozisyonlar: ayni bar icinde tekrar
            # stop/target kontrolu YAPILMAZ (limit giris barinda hedef sayilmaz).
            opened_this_bar: set[str] = set()

            # ---- 1) market emirleri: BIR ONCEKI bardan gelenler, open'da dolar
            for sym in symbols_at_t:
                bar = data[sym].loc[t]
                due = [o for o in pending_market if o.symbol == sym]
                pending_market = [o for o in pending_market if o.symbol != sym]
                for o in due:
                    cash, positions, opened = self._execute_market(
                        o, bar, cash, positions, t, result
                    )
                    if opened:
                        opened_this_bar.add(sym)
                        # ayni bar icinde stop/target kontrolu (stop oncelikli)
                        cash, positions = self._check_exits(
                            sym, bar, cash, positions, t, result,
                            allow_target=(o.kind == "market"),
                        )

            # ---- 2) limit emirler
            for sym in symbols_at_t:
                bar = data[sym].loc[t]
                still: list[Order] = []
                for o in open_limits:
                    if o.symbol != sym:
                        still.append(o)
                        continue
                    filled_price = self._limit_fill(o, bar)
                    if filled_price is None:
                        still.append(o)
                        continue
                    cash, positions, opened = self._execute_limit(
                        o, filled_price, cash, positions, t, result
                    )
                    if opened:
                        opened_this_bar.add(sym)
                        cash, positions = self._check_exits(
                            sym, bar, cash, positions, t, result, allow_target=False
                        )
                open_limits = still

            # ---- 3) mevcut pozisyonlarin stop/target kontrolu
            for sym in symbols_at_t:
                if sym in opened_this_bar:
                    continue      # bu bardan yeni dolmus -> zaten kontrol edildi
                if sym in positions:
                    bar = data[sym].loc[t]
                    cash, positions = self._check_exits(
                        sym, bar, cash, positions, t, result, allow_target=True
                    )

            # ---- 4) funding
            for sym, rate in funding_map.get(t, {}).items():
                pos = positions.get(sym)
                if pos is None or pos.qty == 0:
                    continue
                price = self._last_close(data, sym, t)
                if price <= 0:
                    continue
                notional = pos.notional(price)
                cash += -pos.sign * notional * rate
                pos.funding_paid += -pos.sign * notional * rate
                result.funding_paid += -pos.sign * notional * rate

            # ---- 5) equity (mark-to-market)
            #  `math.fsum`: toplama sirasi degisse de sonuc DEGISMESIN
            #  (float toplamasi siraya baglidir).
            equity = cash + math.fsum(
                self._unrealized(p, self._last_close(data, sym, t))
                for sym, p in positions.items()
            )
            equity_vals.append(equity)
            equity_idx.append(t)
            peak_equity = max(peak_equity, equity)

            # ---- 6) drawdown kill switch
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0.0
            if apply_kill_switch and dd >= self.risk.max_drawdown_pct:
                result.kill_switch_triggered = True
                result.kill_switch_reason = (
                    f"max drawdown {dd:.2%} >= {self.risk.max_drawdown_pct:.2%}"
                )
                # yeni sinyal uretilmez (acik pozisyonlar yonetilmeye devam eder)

            # ---- 7) sinyaller
            risk_off = apply_kill_switch and result.kill_switch_triggered
            for sym in symbols_at_t:
                df = data[sym]
                # get_loc yerine searchsorted: yinelenen zaman damgalarinda
                # get_loc dilim dondurup hata veriyor.
                pos = int(df.index.searchsorted(t, side="right")) - 1
                lo = max(0, pos - self.history_bars + 1)
                panel_cache[sym] = df.iloc[lo: pos + 1]
            signals = strategy.generate(Panel(panel_cache), t)
            prices = {sym: self._last_close(data, sym, t) for sym in symbols_at_t}
            new_orders, accepted, rejected = self._orders_from_signals(
                signals, positions, equity, t, prices, risk_off=risk_off
            )
            result.accepted_signals.extend(accepted)
            result.rejected_signals.extend(rejected)
            for o in new_orders:
                if o.kind == "market":
                    pending_market.append(o)
                else:
                    open_limits.append(o)

        # ---- kapanis: acik pozisyonlar son kapanista tasfiye edilir
        if positions:
            last_ts = timeline[-1]
            for sym in list(positions.keys()):
                price = self._last_close(data, sym, last_ts)
                if price <= 0:
                    continue
                pos = positions.pop(sym)
                slip = self.costs.slippage_rate
                exit_price = price * (1 - slip) if pos.side == "long" else price * (1 + slip)
                cash = self._close_position(
                    pos, exit_price, last_ts, "period_end", cash, result
                )

        result.equity_curve = pd.Series(equity_vals, index=pd.DatetimeIndex(equity_idx))
        result.final_equity = cash
        result.gross_exposure = result.gross_exposure
        if len(result.equity_curve):
            result.final_equity = float(result.equity_curve.iloc[-1])
        return result

    # ------------------------------------------------------------------
    # yardimcilar
    # ------------------------------------------------------------------

    def _slice(self, data, start, end) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for sym, df in data.items():
            if df is None or len(df) == 0:
                continue
            d = df
            if start is not None:
                d = d.loc[d.index >= pd.Timestamp(start, tz="UTC")]
            if end is not None:
                d = d.loc[d.index <= pd.Timestamp(end, tz="UTC")]
            if len(d):
                out[sym] = d
        return out

    def _funding_map(self, funding: dict[str, pd.DataFrame],
                     timeline=None) -> dict:
        """Funding olaylarini bar zaman damgalarina esler.

        Binance funding kayitlari 00:00/08:00/16:00 UTC'ye yakin ama birkac
        milisaniye sapmayla gelir. Dogrudan eslestirme (funding_map.get(t))
        bu yuzden neredeyse hicbir olayi yakalayamaz.

        Kural: bir funding olayi, ACILIS zamani <= olay ani olan en son bara
        atanir. Boylece gunluk barda 3 olay (00/08/16) dogru bara duser,
        hicbir olay kacmaz ve olaylar iki kez sayilmaz.

        Ayni bara düsen birden fazla olayin oranlari toplanir (odeme tutari
        oranla dogrusal oldugu icin toplam dogru sonuc verir).
        """
        out: dict[pd.Timestamp, dict[str, float]] = {}
        if timeline is None or len(timeline) == 0:
            return out
        tl = pd.DatetimeIndex(timeline)
        tl_ns = tl.asi8
        bar_delta = self._bar_delta(tl)
        last_close = tl[-1] + bar_delta

        for sym, df in funding.items():
            if df is None or len(df) == 0:
                continue
            for ts, rate in zip(df.index, df["funding_rate"].to_numpy(dtype=float)):
                f = pd.Timestamp(ts)
                if f > last_close:
                    continue          # donemin disi -> uygulanmaz
                pos = int(np.searchsorted(tl_ns, f.value, side="right")) - 1
                if pos < 0:
                    continue          # ilk bardan once -> uygulanmaz
                bar_ts = tl[pos]
                bucket = out.setdefault(bar_ts, {})
                bucket[sym] = bucket.get(sym, 0.0) + float(rate)
        return out

    @staticmethod
    def _bar_delta(tl: pd.DatetimeIndex) -> pd.Timedelta:
        """Bardaki tipik sure (gunluk icin 1 gun)."""
        if len(tl) < 2:
            return pd.Timedelta(days=1)
        diffs = pd.Series(tl).diff().dropna()
        if len(diffs) == 0:
            return pd.Timedelta(days=1)
        return pd.Timedelta(diffs.median())

    @staticmethod
    def _last_close(data, symbol: str, ts) -> float:
        df = data.get(symbol)
        if df is None or len(df) == 0:
            return 0.0
        sub = df.loc[df.index <= ts]
        return float(sub["close"].iloc[-1]) if len(sub) else 0.0

    @staticmethod
    def _unrealized(pos: Position, price: float) -> float:
        if price <= 0:
            return 0.0
        return (price - pos.entry_price) * pos.qty * pos.sign

    def _limit_fill(self, o: Order, bar: pd.Series) -> float | None:
        """Limit emrin dolum fiyati; dolmuyorsa None."""
        if o.price is None:
            return None
        if o.side == "buy":
            if float(bar["low"]) > o.price:
                return None
            # stopun/hedefin otesinde gap acildiysa acilis fiyati dolumdur
            if float(bar["open"]) <= o.price:
                return float(bar["open"])
            return o.price
        if float(bar["high"]) < o.price:
            return None
        if float(bar["open"]) >= o.price:
            return float(bar["open"])
        return o.price

    def _execute_market(self, o: Order, bar, cash, positions, ts, result):
        slip = self.costs.slippage_rate
        price = float(bar["open"])
        fill = price * (1 + slip) if o.side == "buy" else price * (1 - slip)
        fee = fill * o.qty * self.costs.taker_fee
        cash -= fee
        result.fees_paid += fee
        return self._apply_fill(o, fill, fee, cash, positions, ts, result)

    def _execute_limit(self, o: Order, fill_price: float, cash, positions, ts, result):
        fee = fill_price * o.qty * self.costs.maker_fee
        cash -= fee
        result.fees_paid += fee
        return self._apply_fill(o, fill_price, fee, cash, positions, ts, result)

    def _apply_fill(self, o: Order, fill: float, fee: float, cash, positions, ts, result):
        """Net pozisyon modeli: ayni sembolde pozisyon varsa ortalanir."""
        existing = positions.get(o.symbol)
        if existing is not None:
            same_side = (existing.side == "long" and o.side == "buy") or \
                        (existing.side == "short" and o.side == "sell")
            if same_side:
                total_qty = existing.qty + o.qty
                existing.entry_price = (
                    existing.entry_price * existing.qty + fill * o.qty
                ) / total_qty
                existing.risk_amount *= total_qty / existing.qty
                existing.qty = total_qty
                existing.entry_fee += fee
                existing.stop = o.stop if o.stop is not None else existing.stop
                existing.target = o.target if o.target is not None else existing.target
                cash = self._maybe_gap_stopout(existing, ts, cash, positions, result)
                return cash, positions, False
            # karsi yon: kismi kapatma veya tam donus
            close_qty = min(existing.qty, o.qty)
            if close_qty > 0:
                exit_price = fill
                cash = self._close_position(
                    existing, exit_price, ts, "rebalance", cash, result,
                    qty=close_qty,
                )
            if o.qty >= existing.qty - 1e-12:
                # TAM KAPAMA: pozisyon kayitlardan SILINMELI ( aksi halde
                # ayni pozisyon donem sonunda ikinci kez kapanir).
                positions.pop(o.symbol, None)
                rem = o.qty - existing.qty
                if rem > 1e-12:
                    new_pos = Position(
                        symbol=o.symbol,
                        side="long" if o.side == "buy" else "short",
                        qty=rem,
                        entry_price=fill,
                        stop=o.stop,
                        target=o.target,
                        opened_ts=ts,
                        risk_amount=abs(fill - o.stop) * rem if o.stop else
                        fill * rem * self.risk.risk_per_trade,
                        entry_fee=fee * (rem / o.qty) if o.qty else fee,
                        strategy=o.strategy,
                        meta=dict(o.meta),
                    )
                    positions[o.symbol] = new_pos
                    cash = self._maybe_gap_stopout(new_pos, ts, cash, positions, result)
            else:
                # KISMI KAPAMA: kalan miktar korunur (pozisyon miktarı,
                # giris ücreti, funding ve risk payı orantili azalir).
                ratio = (existing.qty - close_qty) / existing.qty
                existing.qty -= close_qty
                existing.entry_fee *= ratio
                existing.funding_paid *= ratio
                existing.risk_amount *= ratio
            return cash, positions, False

        pos = Position(
            symbol=o.symbol,
            side="long" if o.side == "buy" else "short",
            qty=o.qty,
            entry_price=fill,
            stop=o.stop,
            target=o.target,
            opened_ts=ts,
            risk_amount=abs(fill - o.stop) * o.qty if o.stop else
            fill * o.qty * self.risk.risk_per_trade,
            entry_fee=fee,
            strategy=o.strategy,
            meta=dict(o.meta),
        )
        positions[o.symbol] = pos
        cash = self._maybe_gap_stopout(pos, ts, cash, positions, result)
        return cash, positions, True

    def _maybe_gap_stopout(self, pos: Position, ts, cash, positions, result):
        """Dolum fiyati zaten stopun OTESINDEyse: aninda stop-out (gap stopout).

        Emir zaten gonderilmis ve dolmus oldugu icin "iptal" mumkun degil;
        kaybetmek gercekci davranistir. Cikis dolum fiyatindan (+ aleyhe slippage).
        """
        if pos.stop is None:
            return cash
        through = (pos.entry_price <= pos.stop) if pos.side == "long" \
            else (pos.entry_price >= pos.stop)
        if not through:
            return cash
        slip = self.costs.slippage_rate
        exit_price = pos.entry_price * (1 - slip) if pos.side == "long" \
            else pos.entry_price * (1 + slip)
        positions.pop(pos.symbol, None)
        result.gap_stopouts += 1
        return self._close_position(pos, exit_price, ts, "stop", cash, result)

    def _check_exits(self, symbol, bar, cash, positions, ts, result, allow_target: bool):
        pos = positions.get(symbol)
        if pos is None:
            return cash, positions
        o = float(bar["open"])
        h = float(bar["high"])
        low = float(bar["low"])
        slip = self.costs.slippage_rate

        if pos.side == "long":
            if pos.stop is not None and low <= pos.stop:
                # gap: bar stopun altinda acildiysa acilistan cikilir
                exit_price = min(pos.stop, o) * (1 - slip)
                reason = "stop"
            elif allow_target and pos.target is not None and h >= pos.target:
                exit_price = pos.target
                reason = "target"
            else:
                return cash, positions
        else:
            if pos.stop is not None and h >= pos.stop:
                exit_price = max(pos.stop, o) * (1 + slip)
                reason = "stop"
            elif allow_target and pos.target is not None and low <= pos.target:
                exit_price = pos.target
                reason = "target"
            else:
                return cash, positions

        positions.pop(symbol, None)
        cash = self._close_position(pos, exit_price, ts, reason, cash, result)
        return cash, positions

    def _close_position(self, pos: Position, exit_price: float, ts, reason: str,
                        cash: float, result: BacktestResult,
                        qty: float | None = None) -> float:
        q = pos.qty if qty is None else qty
        if q <= 0:
            return cash
        fee_rate = self.costs.maker_fee if reason == "target" else self.costs.taker_fee
        exit_fee = exit_price * q * fee_rate
        gross = (exit_price - pos.entry_price) * q * pos.sign
        share = (q / pos.qty) if pos.qty else 0.0
        entry_fee_share = pos.entry_fee * share
        funding_share = pos.funding_paid * share
        # R payi: kapanan MIKTARLA orantili risk payi (kismi kapamada tam
        # pozisyon riski kullanilirsa R carpani yanlis olur).
        risk_share = pos.risk_amount * share if pos.qty else pos.risk_amount
        pnl = gross - entry_fee_share - exit_fee + funding_share
        cash += gross - exit_fee + funding_share
        result.fees_paid += exit_fee

        trade = ClosedTrade(
            symbol=pos.symbol,
            side=pos.side,
            entry=pos.entry_price,
            exit=exit_price,
            qty=q,
            stop=pos.stop,
            target=pos.target,
            pnl_usd=pnl,
            pnl_r=(pnl / risk_share) if risk_share else 0.0,
            fees=entry_fee_share + exit_fee,
            funding=funding_share,
            entry_ts=pos.opened_ts,
            exit_ts=ts,
            exit_reason=reason,
            strategy=pos.strategy,
            meta=dict(pos.meta),
        )
        result.trades.append(trade)
        return cash

    # ------------------------------------------------------------------
    # sinyal -> emir
    # ------------------------------------------------------------------

    def _orders_from_signals(self, signals, positions, equity, ts,
                             prices: dict[str, float] | None = None,
                             risk_off: bool = False):
        orders: list[Order] = []
        accepted: list[dict] = []
        rejected: list[dict] = []
        prices = prices or {}
        if equity <= 0:
            return orders, accepted, rejected

        weight_signals = [s for s in signals if s.action == "target_weight"]
        other_signals = [s for s in signals if s.action != "target_weight"]

        # --- hedef agirlik -> fark emirleri
        #  Asagidaki blokta iki kural vardir:
        #   a) Kalan pozisyon sayisi tavani: rebalance SONRASI acik olacak
        #      sembol sayisi hesaplanir. (Eski hata: max_new = max_positions -
        #      len(positions) degeri 0 ciktiginda, mevcut pozisyonlarin
        #      DUZELTME emirleri de reddediliyordu; portföy donuyordu.)
        #   b) Brüt kaldirac tavani: |delta| toplami degil, rebalance SONRASI
        #      OLUSACAK brüt pozisyon olceklenir.
        specs: list[tuple[Signal, float, float]] = []  # (sinyal, hedef, mevcut)
        targets: dict[str, float] = {}
        weight_rejected: set[str] = set()
        for s in weight_signals:
            w = float(s.weight or 0.0)
            target_notional = w * equity
            pos = positions.get(s.symbol)
            current_notional = 0.0
            if pos is not None:
                # Mevcut pozisyonun PIYASA DEGERI (giris fiyati degil):
                # hedef agirlik equity'nin ANLIK degerine gore tanimlidir.
                mark = prices.get(s.symbol, 0.0) or pos.entry_price
                current_notional = pos.sign * pos.qty * mark
            targets[s.symbol] = target_notional
            delta = target_notional - current_notional
            if abs(delta) < self.min_trade_notional:
                continue
            if risk_off and abs(target_notional) > abs(current_notional):
                # Kill switch aktif: pozisyon BUYUTULMEZ, yalnizca kucultulur.
                # (Eski davranis: sinyal uretimi tamamen duruyordu; bu, portföyü
                #  dondurup hem riski hem de olcumü anlamsizlastiriyordu.)
                rejected.append({**s.to_dict(),
                                 "reject_reason": "kill switch: risk arttirilamaz"})
                weight_rejected.add(s.symbol)
                continue
            specs.append((s, target_notional, current_notional))

        # --- toplam brüt kaldirac tavani (rebalance sonucu brüt pozisyon)
        #  `gross_exposure` saf ve SIRA BAGIMSIZDIR (sorted + math.fsum):
        #  set uzerinde gezmek + elle float toplamak ayni veriden farkli
        #  sonuc uretiyordu (bkz. docs/KOSU_GECMISI_SEPET_MOMENTUM.md).
        result_gross = gross_exposure(positions, targets, prices)
        cap = self.risk.max_gross_leverage * equity
        if cap > 0 and result_gross > cap:
            scale = cap / result_gross
            targets = {k: v * scale for k, v in targets.items()}
            specs = [(s, t * scale, c) for s, t, c in specs]

        # --- kalan pozisyon sayisi tavani (rebalance sonrasi acik olacaklar)
        open_now = set(positions.keys())
        closes = {s.symbol for s, t, c in specs
                  if abs(t) <= 1e-12 and abs(c) > 1e-12}
        new_open = {s.symbol for s, t, c in specs
                    if abs(c) <= 1e-12 and abs(t) > 1e-12}
        projected_open = len(open_now - closes) + len(new_open)
        if projected_open > self.risk.max_positions:
            overflow = projected_open - self.risk.max_positions
            # en kucuk hedef notionaline sahip yeni acilisleri reddet
            candidates = sorted(
                [x for x in specs if x[0].symbol in new_open],
                key=lambda x: abs(x[1]))
            drop: set[str] = set()
            for s, t, c in candidates:
                if overflow <= 0:
                    break
                drop.add(s.symbol)
                overflow -= 1
            for s, t, c in specs:
                if s.symbol in drop:
                    rejected.append({**s.to_dict(), "reject_reason": "pozisyon limiti"})
                    weight_rejected.add(s.symbol)
            specs = [x for x in specs if x[0].symbol not in drop]

        requested: list[tuple[Signal, float]] = []
        for s, t, c in specs:
            requested.append((s, t - c))

        for s, delta in requested:
            if s.symbol in weight_rejected:
                continue
            side = "buy" if delta > 0 else "sell"
            price = prices.get(s.symbol, 0.0)
            if price <= 0:
                rejected.append({**s.to_dict(), "reject_reason": "fiyat yok"})
                continue
            # delta NOTIONAL'dir -> miktara cevir
            qty = abs(delta) / price
            if qty <= 0:
                continue
            orders.append(Order(
                symbol=s.symbol,
                side=side,
                kind="market",
                qty=qty,
                strategy=getattr(s, "strategy", "") or "unknown",
                client_order_id=self._client_id(ts, s.symbol, side, qty),
                meta={"weight": s.weight, **{k: v for k, v in s.meta.items()
                                             if k != "strategy"}},
            ))
            accepted.append(s.to_dict())

        # --- open/close sinyalleri (stop/target'li tekil girisler)
        for s in other_signals:
            if s.action == "close":
                pos = positions.get(s.symbol)
                if pos is None:
                    rejected.append({**s.to_dict(), "reject_reason": "pozisyon yok"})
                    continue
                orders.append(Order(
                    symbol=s.symbol,
                    side="sell" if pos.side == "long" else "buy",
                    kind="market",
                    qty=pos.qty,
                    reduce_only=True,
                    strategy=getattr(s, "strategy", "") or "unknown",
                    client_order_id=self._client_id(ts, s.symbol, "close", pos.qty),
                    meta=dict(s.meta),
                ))
                accepted.append(s.to_dict())
            elif s.action == "open":
                if risk_off:
                    rejected.append({**s.to_dict(),
                                     "reject_reason": "kill switch: yeni pozisyon acilamaz"})
                    continue
                if s.entry is None or s.stop is None or s.target is None:
                    rejected.append({**s.to_dict(), "reject_reason": "eksik geometri"})
                    continue
                risk_dist = abs(s.entry - s.stop)
                if risk_dist <= 0:
                    rejected.append({**s.to_dict(), "reject_reason": "stop == entry"})
                    continue
                budget = equity * self.risk.risk_per_trade
                qty = budget / risk_dist
                notional = qty * s.entry
                if notional > self.risk.max_gross_leverage * equity:
                    qty *= (self.risk.max_gross_leverage * equity) / notional
                kind = "limit" if getattr(s, "order_type", "market") == "limit" else "market"
                orders.append(Order(
                    symbol=s.symbol,
                    side="buy" if s.side == "long" else "sell",
                    kind=kind,
                    qty=qty,
                    price=s.entry if kind == "limit" else None,
                    stop=s.stop,
                    target=s.target,
                    strategy=getattr(s, "strategy", "") or "unknown",
                    client_order_id=self._client_id(ts, s.symbol, s.side, qty),
                    meta=dict(s.meta),
                ))
                accepted.append(s.to_dict())
            else:
                rejected.append({**s.to_dict(), "reject_reason": f"bilinmeyen aksiyon {s.action}"})

        return orders, accepted, rejected

    @staticmethod
    def _client_id(ts, symbol: str, side: str, qty: float) -> str:
        """Deterministik idempotency anahtari — ayni sinyal icin her zaman ayni."""
        import hashlib

        raw = f"{ts.isoformat()}|{symbol}|{side}|{qty:.10f}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:20]
        return f"tb-{symbol.replace('/', '').replace(':', '')}-{digest}"


def monte_carlo_dd(trades_r: list[float], runs: int = 2000, seed: int = 42) -> dict:
    """Islem sirasini karistirarak drawdown dagilimi (R cinsinden)."""
    if not trades_r:
        return {"p95_dd_r": 0.0, "max_dd_r": 0.0, "mean_dd_r": 0.0}
    rng = np.random.default_rng(seed)
    arr = np.asarray(trades_r, dtype=float)
    dds = np.empty(runs, dtype=float)
    for i in range(runs):
        perm = rng.permutation(arr)
        eq = np.cumsum(perm)
        peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
        dds[i] = float((peak - eq).max())
    return {
        "mean_dd_r": round(float(dds.mean()), 2),
        "p95_dd_r": round(float(np.percentile(dds, 95)), 2),
        "max_dd_r": round(float(dds.max()), 2),
    }
