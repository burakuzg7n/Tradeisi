"""Paper trading motoru.

PAPER = GERCEK PARA YOK. Borsadan SADECE fiyat verisi okunur; emirler
simule edilir.

Tasarim: paper sonucu ile backtest sonucu AYNI metodolojiyi paylasir, cunku
paper motoru backtest motorunun deterministik oynatimidir (replay):
  1) Borsadan guncel, kapanmis barlar cekilir ve yerel onbellege yazilir.
  2) Strateji tum birikmis veri uzerinde ** bastan ** calistirilir.
  3) Motor, daha once journal'a yazilmamis YENI islemleri ve sinyalleri
     bulur, journal'a yazar, Telegram'a gonderir.

Boylece "backtest X diyor, live Y diyor" tutarsizligi yapısal olarak
imkansiz olur: ayni motor, ayni veri, ayni kod.

Bekleme: stratejinin bar periyodunun kapanisini bekler (or. 1d -> her gece
00:05 UTC). Her turda borsadan yeni barlar alir.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

from .backtest import Backtester
from .config import CostModel, RiskSettings
from .exchange import CcxtAdapter
from .notify import TelegramNotifier, fmt_trade_closed, fmt_trade_opened
from .risk import RiskEngine
from .store import Store
from .strategy import Panel

TF_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}


@dataclass
class PaperConfig:
    exchange: str = "binance"
    timeframe: str = "1d"
    symbols: tuple[str, ...] = ()
    initial_equity: float = 1000.0
    history_bars: int = 400
    offline: bool = False          # True: borsaya gitmez, yerel veriyi kullanir


class PaperEngine:
    def __init__(self, strategy, config: PaperConfig, store: Store,
                 notifier: TelegramNotifier | None = None,
                 costs: CostModel | None = None,
                 risk_settings: RiskSettings | None = None):
        self.strategy = strategy
        self.cfg = config
        self.store = store
        self.notifier = notifier or TelegramNotifier()
        self.costs = costs or CostModel()
        self.risk_settings = risk_settings or RiskSettings()
        self.adapter: CcxtAdapter | None = None
        self.risk = RiskEngine(self.risk_settings, config.initial_equity,
                               state=store.get_kv(f"risk_state:{strategy.name}"))
        self._stop = False

    # ------------------------------------------------------------------

    async def _get_adapter(self) -> CcxtAdapter | None:
        if self.cfg.offline:
            return None
        if self.adapter is None:
            from .config import ExchangeSettings

            settings = ExchangeSettings(exchange_id=self.cfg.exchange)
            settings = ExchangeSettings(
                exchange_id=self.cfg.exchange,
                api_key="", api_secret="", testnet=False,
                market=settings.market, default_type=settings.default_type,
                recv_window_ms=settings.recv_window_ms,
            )
            self.adapter = CcxtAdapter(settings)
        return self.adapter

    async def fetch_frames(self) -> dict[str, pd.DataFrame]:
        """Her sembol icin kapanmis barlar (yerel onbellek + borsa).

        Onbellek BUYUTULUR: her turda gelen yeni barlar mevcut cache'e eklenir.
        Boylece motor her zaman bastan oynatilir ve equity serisi kesintisiz
        olur (kayan pencere kullanilsaydi eski pozisyonlar kaybolur, islem
        sayaci bozulurdu).
        """
        adapter = await self._get_adapter()
        frames: dict[str, pd.DataFrame] = {}
        for sym in self.cfg.symbols:
            cached = self._load_cache(sym)
            fresh = None
            if adapter is not None:
                try:
                    fresh = await adapter.fetch_ohlcv(
                        sym, self.cfg.timeframe, limit=self.cfg.history_bars
                    )
                except Exception as exc:  # borsa erisilemezse cache ile devam
                    self.store.log_event(
                        f"{sym} veri cekilemedi: {exc}", level="warn", source="paper"
                    )
            df = self._merge(cached, fresh)
            if df is None or len(df) == 0:
                continue
            # KAPANMIS bar: son bar hâlâ oluşuyor olabilir -> at
            df = self._drop_forming_bar(df)
            self._save_cache(sym, df)
            frames[sym] = df
        return frames

    async def fetch_funding(self) -> dict[str, pd.DataFrame]:
        """Funding oranlari (paper/backtest maliyet tutarliligi icin).

        Onbellek buyutulur; boylece motorun bastan oynatilmasi funding'i de
        tam olarak kapsar.
        """
        adapter = await self._get_adapter()
        out: dict[str, pd.DataFrame] = {}
        if adapter is None:
            return out
        for sym in self.cfg.symbols:
            cached = self._load_funding(sym)
            since = None
            if cached is not None and len(cached):
                since = int(cached.index[-1].timestamp() * 1000) + 1
            try:
                fresh = await adapter.fetch_funding_rates(sym, since_ms=since,
                                                          limit=1000)
            except Exception:
                fresh = None
            if fresh is None or len(fresh) == 0:
                if cached is not None and len(cached):
                    out[sym] = cached
                continue
            merged = fresh
            if cached is not None and len(cached):
                merged = pd.concat([cached, fresh])
                merged = merged[~merged.index.duplicated(keep="last")].sort_index()
            self._save_funding(sym, merged)
            out[sym] = merged
        return out

    @staticmethod
    def _merge(cached: pd.DataFrame | None, fresh: pd.DataFrame | None):
        """Cache + yeni barlar -> birlestirilmis, sirali, tekrarsiz frame."""
        if fresh is None or len(fresh) == 0:
            return cached
        if cached is None or len(cached) == 0:
            return fresh
        out = pd.concat([cached, fresh])
        out = out[~out.index.duplicated(keep="last")].sort_index()
        return out

    @staticmethod
    def _drop_forming_bar(df: pd.DataFrame) -> pd.DataFrame:
        """Son bar kapanmamis olabilir -> her zaman at (repaint imkânsiz)."""
        if len(df) == 0:
            return df
        # TF bilgisi yoksa son barı at (guvenli varsayilan)
        return df.iloc[:-1] if len(df) else df

    def _cache_path(self, symbol: str):
        from .config import DATA_DIR

        return DATA_DIR / f"paper_{self.cfg.exchange}_{symbol}_{self.cfg.timeframe}.csv"

    def _funding_cache_path(self, symbol: str):
        from .config import DATA_DIR

        return DATA_DIR / f"paper_{self.cfg.exchange}_{symbol}_{self.cfg.timeframe}_funding.csv"

    def _load_cache(self, symbol: str) -> pd.DataFrame | None:
        from .market import load_csv

        path = self._cache_path(symbol)
        if not path.exists():
            return None
        try:
            return load_csv(path)
        except Exception:
            return None

    def _save_cache(self, symbol: str, df: pd.DataFrame) -> None:
        from .market import save_csv

        try:
            save_csv(df, self._cache_path(symbol))
        except Exception:
            pass

    def _load_funding(self, symbol: str) -> pd.DataFrame | None:
        from .market import load_funding_csv

        path = self._funding_cache_path(symbol)
        if not path.exists():
            return None
        try:
            return load_funding_csv(path)
        except Exception:
            return None

    def _save_funding(self, symbol: str, df: pd.DataFrame) -> None:
        from .market import save_funding_csv

        try:
            save_funding_csv(df, self._funding_cache_path(symbol))
        except Exception:
            pass

    # ------------------------------------------------------------------

    async def run_once(self) -> dict:
        """Bir tur calistir: veri cek -> oynat -> yeni kayitlari journal'a yaz."""
        frames = await self.fetch_frames()
        if not frames:
            return {"status": "veri yok", "new_trades": 0}
        funding = await self.fetch_funding()

        bt = Backtester(
            costs=self.costs,
            risk=self.risk_settings,
            initial_equity=self.cfg.initial_equity,
            history_bars=self.cfg.history_bars,
        )
        result = bt.run(frames, self.strategy, funding=funding)

        # --- yeni islemler
        last_ts = self.store.get_kv(f"paper_last_trade_ts:{self.strategy.name}", "")
        new_trades = [t for t in result.trades
                      if str(t.exit_ts.isoformat()) > str(last_ts)]
        for t in new_trades:
            self.store.log_trade({
                "strategy": self.strategy.name,
                "symbol": t.symbol, "side": t.side,
                "entry": t.entry, "exit": t.exit, "qty": t.qty,
                "stop": t.stop, "target": t.target,
                "pnl_usd": t.pnl_usd, "pnl_r": t.pnl_r,
                "fees": t.fees, "funding": t.funding,
                "entry_ts": str(t.entry_ts.isoformat()),
                "exit_ts": str(t.exit_ts.isoformat()),
                "exit_reason": t.exit_reason,
                "mode": "paper",
                "meta": {**t.meta, "kind": "ALTYAPI_TESTI"}
                if not self.strategy.research_candidate else t.meta,
            })
            self.risk.record_result(t.pnl_r, t.risk_amount if hasattr(t, "risk_amount")
                                    else max(abs(t.entry) * t.qty * self.risk_settings.risk_per_trade, 1e-9))
            await self.notifier.send(fmt_trade_closed(
                t.symbol, t.side, t.pnl_r, t.pnl_usd, t.exit_reason
            ))
            self.store.log_event(
                f"ISLEM KAPANDI {t.symbol} {t.side} {t.pnl_r:+.2f}R",
                level="info", source="paper",
            )
        if new_trades:
            self.store.set_kv(f"paper_last_trade_ts:{self.strategy.name}",
                              str(new_trades[-1].exit_ts.isoformat()))

        # --- yeni sinyaller
        last_sig = self.store.get_kv(f"paper_last_signal_ts:{self.strategy.name}", "")
        for s in result.accepted_signals:
            ts = str(s.get("ts") or "")
            if ts and ts <= str(last_sig):
                continue
            self.store.log_signal(s, True)
        for s in result.rejected_signals:
            ts = str(s.get("ts") or "")
            if ts and ts <= str(last_sig):
                continue
            self.store.log_signal(s, False, s.get("reject_reason"))
        if result.accepted_signals:
            newest = max(str(s.get("ts") or "") for s in result.accepted_signals)
            self.store.set_kv(f"paper_last_signal_ts:{self.strategy.name}", newest)

        # --- equity
        if result.equity_curve is not None and len(result.equity_curve):
            ts = result.equity_curve.index[-1]
            equity = float(result.equity_curve.iloc[-1])
            self.store.record_equity(
                str(ts.isoformat()), equity, equity, 0.0, 0.0,
                mode="paper", strategy=self.strategy.name,
            )

        self.store.set_kv(f"risk_state:{self.strategy.name}", self.risk.state())
        self.store.set_kv(f"paper_last_run:{self.strategy.name}",
                          datetime.now(timezone.utc).isoformat())

        return {
            "status": "ok",
            "new_trades": len(new_trades),
            "total_trades": result.total_trades,
            "equity": float(result.equity_curve.iloc[-1])
            if result.equity_curve is not None and len(result.equity_curve) else 0.0,
            "drawdown": result.max_drawdown,
        }

    # ------------------------------------------------------------------

    async def run_forever(self) -> None:
        from .notify import fmt_start

        self.store.log_event(
            f"Paper motoru basladi: {self.strategy.name} "
            f"({self.cfg.exchange} {self.cfg.timeframe})", source="paper",
        )
        await self.notifier.send(fmt_start(
            "PAPER (gercek para yok)", self.strategy.name, list(self.cfg.symbols)
        ))
        try:
            while not self._stop:
                await self.run_once()
                await asyncio.sleep(self._seconds_until_next_bar())
        except asyncio.CancelledError:
            raise
        finally:
            await self.close()

    async def close(self) -> None:
        """Borsa oturumunu kapat.

        Kapatilmazsa ccxt/aiohttp 'Unclosed client session' uyarisi yazar ve
        program hata koduyla cikar. `--once` ve `run_forever` her ikisi de
        bunu cagirir.
        """
        if self.adapter is not None:
            try:
                await self.adapter.close()
            except Exception:
                pass
            self.adapter = None

    def _seconds_until_next_bar(self) -> float:
        tf = TF_SECONDS.get(self.cfg.timeframe, 86400)
        now = datetime.now(timezone.utc)
        epoch = int(now.timestamp())
        nxt = (epoch // tf + 1) * tf
        # bar kapanisindan 20 sn sonra tara (borsa mumu kesinlestirsin)
        wait = max((nxt - epoch) + 20, 20)
        return float(wait)

    def stop(self) -> None:
        self._stop = True
