"""Komut satir arayuzu — `python -m trader <komut>`.

Komutlar:
    kurulum   Bagimlilik ve ortam kontrolu
    veri      Borsa verisi indir (OHLCV + funding)
    backtest  Backtest calistir, rapor yaz, kapilari degerlendir
    paper     Paper trading baslat (gercek para YOK)
    canli     Testnet/canli yurutucu (kapilar kontrol edilir)
    panel     Web panelini ac
    durum     Anlik durumu yazdir
    kapilar   Protokol kapilarini goster
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import __version__
from .config import DATA_DIR, OUT_DIR, load_settings

DEFAULT_POOL = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
    "AVAXUSDT", "LINKUSDT", "POLUSDT", "LTCUSDT", "BCHUSDT", "DOTUSDT",
    "ATOMUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "TRXUSDT", "ETCUSDT",
    "FILUSDT", "INJUSDT", "SUIUSDT", "TIAUSDT", "WIFUSDT",
)
# Not: MATICUSDT Binance USDT-M'de delist oldu (POLUSDT'ye gecildi) -> havuzdan cikarildi.
#      PEPEUSDT USDT-M futures listesinde yok -> havuzdan cikarildi.

# Protokol kapilari (AGENTS.md + docs/KARAR_NOTU_C_2026-11-02.md)
INSAMPLE_GATES = {"min_pf": 1.30, "min_trades": 150, "max_dd": 0.15}
HOLDOUT_GATES = {"min_pf": 1.15, "max_dd": 0.15}


def _print_header(title: str) -> None:
    print()
    print("=" * 68)
    print(f"  {title}")
    print("=" * 68)


# --------------------------------------------------------------------------
# kurulum
# --------------------------------------------------------------------------

def cmd_setup(args) -> int:
    _print_header("TradeBot — kurulum kontrolu")
    print(f"Surum          : {__version__}")
    print(f"Python         : {sys.version.split()[0]}")
    print(f"Veri klasoru   : {DATA_DIR}")
    print(f"Calisma klasoru: {OUT_DIR}")
    print()

    ok = True
    for module in ("pandas", "numpy", "requests", "httpx", "ccxt", "fastapi", "uvicorn"):
        try:
            mod = __import__(module)
            version = getattr(mod, "__version__", "?")
            print(f"  [OK]   {module:10s} {version}")
        except ImportError:
            print(f"  [EKSIK] {module:10s} -> pip install -r requirements.txt")
            ok = False
    print()
    settings = load_settings()
    print(f"Mod            : {settings.mode}")
    print(f"Borsa          : {settings.exchange.exchange_id} "
          f"({'testnet' if settings.exchange.testnet else 'CANLI'})")
    print(f"API anahtari   : {'var' if settings.exchange.api_key else 'YOK (sadece veri)'}")
    print(f"Telegram       : {'aktif' if settings.notify.telegram_token else 'kapali'}")
    print()
    if ok:
        print("Her sey hazir. Sonraki adim:  python -m trader veri")
    else:
        print("Eksik paket var. Proje klasorunde '1_kurulum.bat' dosyasini calistir.")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# veri
# --------------------------------------------------------------------------

def cmd_data(args) -> int:
    from .market import get_funding, get_ohlcv, validate_ohlcv

    symbols = tuple(args.symbols) if args.symbols else DEFAULT_POOL
    exchange = args.exchange
    _print_header(f"Veri indirme — {exchange} {args.timeframe}")
    print(f"Aralik : {args.start} → {args.end}")
    print(f"Sembol : {len(symbols)}")
    print()

    health = []
    for sym in symbols:
        try:
            df = get_ohlcv(exchange, sym, args.timeframe, args.start, args.end,
                           refresh=args.refresh)
            info = validate_ohlcv(df, args.timeframe)
            status = "OK" if not info["problems"] else "UYARI"
            print(f"  {sym:12s} {status:6s} bar={info['rows']:6d} "
                  f"bosluk={info['gaps']:3d} {str(info['start'])[:10]} → {str(info['end'])[:10]}")
            if info["problems"]:
                print(f"               {', '.join(info['problems'])}")
            health.append({"symbol": sym, **info})
        except Exception as exc:
            print(f"  {sym:12s} HATA    {exc}")
            health.append({"symbol": sym, "error": str(exc)})

    if args.funding:
        print()
        print("Funding oranlari indiriliyor...")
        for sym in symbols:
            try:
                df = get_funding(exchange, sym, args.start, args.end, refresh=args.refresh)
                print(f"  {sym:12s} {len(df):6d} funding kaydi")
            except Exception as exc:
                print(f"  {sym:12s} HATA    {exc}")

    out = OUT_DIR / "veri_sagligi.json"
    out.write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"Veri sagligi raporu: {out}")
    return 0


# --------------------------------------------------------------------------
# backtest
# --------------------------------------------------------------------------

def _load_panel(symbols, exchange, timeframe, start, end, with_funding=True):
    from .market import get_funding, get_ohlcv

    data: dict[str, pd.DataFrame] = {}
    funding: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            df = get_ohlcv(exchange, sym, timeframe, start, end)
        except Exception as exc:
            print(f"  ! {sym} veri okunamadi: {exc}")
            continue
        if len(df) == 0:
            print(f"  ! {sym} veri yok ({start}→{end})")
            continue
        data[sym] = df
        if with_funding:
            try:
                fdf = get_funding(exchange, sym, start, end)
                if len(fdf):
                    funding[sym] = fdf
            except Exception:
                pass
    return data, funding


def cmd_backtest(args) -> int:
    from .backtest import Backtester
    from .gates import load_gates, record_gate
    from .report import build_report, write_report
    from .strategies import build as build_strategy

    settings = load_settings()
    strategy = build_strategy(args.strategy)
    symbols = tuple(args.symbols) if args.symbols else DEFAULT_POOL
    exchange = args.exchange
    timeframe = getattr(strategy, "timeframe", args.timeframe)

    _print_header(f"Backtest — {strategy.name}")
    print(f"Borsa     : {exchange}   TF: {timeframe}")
    print(f"Donem     : {args.start} → {args.end}")
    print(f"Evren     : {len(symbols)} sembol")
    print(f"Equity    : {args.equity} USDT")
    print()

    data, funding = _load_panel(symbols, exchange, timeframe, args.start, args.end)
    if not data:
        print("VERI YOK. Once 'python -m trader veri' calistir.")
        return 2
    print(f"Yuklenen sembol: {len(data)}  |  funding: {len(funding)}")
    print("Backtest calisiyor...")

    bt = Backtester(
        costs=settings.costs,
        risk=settings.risk,
        initial_equity=args.equity,
    )
    result = bt.run(data, strategy, funding=funding,
                    apply_kill_switch=args.kill_switch)

    meta = {
        "start": args.start, "end": args.end, "exchange": exchange,
        "timeframe": timeframe, "universe": ",".join(sorted(data)),
        "initial_equity": args.equity,
        "maker_fee": settings.costs.maker_fee, "taker_fee": settings.costs.taker_fee,
        "slippage": settings.costs.slippage_rate,
        "periods_per_year": 365 if timeframe == "1d" else 365 * 96,
        "stage": args.stage,
        "kill_switch": bool(args.kill_switch),
        "universe_size": len(data),
    }
    report = build_report(result, strategy.name, meta)
    json_path, md_path = write_report(report, f"{strategy.name}_{args.stage}")

    s = report["summary"]
    print()
    print("-" * 68)
    print(f"  Islem sayisi      : {s['total_trades']}")
    print(f"  Kazanan oran      : {s['win_rate'] * 100:.2f}%")
    print(f"  Profit Factor     : {s['profit_factor']:.3f}")
    print(f"  Expectancy        : {s['expectancy_r']:+.4f} R")
    print(f"  Max Drawdown      : {s['max_drawdown'] * 100:.2f}%")
    print(f"  HAC t             : {s['hac_t']:.3f}")
    print(f"  Sharpe            : {s['sharpe']:.2f}")
    print(f"  Equity            : {report['initial_equity']:,.2f} → {report['final_equity']:,.2f}")
    print("-" * 68)
    print(f"Rapor: {md_path}")
    print(f"       {json_path}")

    # --- protokol kapisi
    if args.stage in ("insample", "holdout"):
        gates = INSAMPLE_GATES if args.stage == "insample" else HOLDOUT_GATES
        checks = {
            f"PF >= {gates['min_pf']}": s["profit_factor"] >= gates["min_pf"],
        }
        if "min_trades" in gates:
            checks[f"islem >= {gates['min_trades']}"] = s["total_trades"] >= gates["min_trades"]
        checks[f"DD <= {gates['max_dd'] * 100:.0f}%"] = s["max_drawdown"] <= gates["max_dd"]
        passed = all(checks.values())
        stage_key = "backtest" if args.stage == "insample" else "holdout"
        existing = load_gates().get(strategy.name, {}).get(stage_key)
        print()
        print(f"KAPI DEGERLENDIRMESI ({args.stage}):")
        for name, okv in checks.items():
            print(f"  [{'GECTI' if okv else 'KALDI'}] {name}")
        print(f"  SONUC: {'GECTI' if passed else 'KALDI (RED)'}")
        if existing:
            print()
            print("  ⚠ DIKKAT: Bu strateji icin bu asamaya ait ONCEKI bir kapı "
                  "kaydi var.")
            print("    Tek atış protokolü gereği aynı kuralda ikinci deneme YAPILMAZ; "
                  "bu kosu TEKRAR/kesif sayilir.")
        else:
            record_gate(strategy.name, stage_key, passed,
                        {"profit_factor": s["profit_factor"],
                         "trades": s["total_trades"],
                         "max_drawdown": s["max_drawdown"],
                         "report": str(json_path)},
                        note=f"{args.stage} tek atis")
            print(f"  Kaydedildi: out/gates.json ({stage_key})")
    return 0


# --------------------------------------------------------------------------
# paper
# --------------------------------------------------------------------------

def cmd_paper(args) -> int:
    from .notify import TelegramNotifier
    from .paper import PaperConfig, PaperEngine
    from .store import Store
    from .strategies import build as build_strategy

    settings = load_settings()
    strategy = build_strategy(args.strategy)
    symbols = tuple(args.symbols) if args.symbols else DEFAULT_POOL

    store = Store(settings.db_path)
    store.set_kv("mode", "paper")
    store.set_kv(f"initial_equity:{strategy.name}", args.equity)
    store.log_event(
        f"Paper basladi: {strategy.name} ({args.exchange} {strategy.timeframe})",
        source="cli",
    )
    if not strategy.research_candidate:
        store.log_event(
            "DIKKAT: Bu strateji bir arastirma adayi DEGILDIR — yalnizca altyapi "
            "testidir. Canli/testnet kapisi kapali.", level="warn", source="cli",
        )

    engine = PaperEngine(
        strategy=strategy,
        config=PaperConfig(
            exchange=args.exchange,
            timeframe=strategy.timeframe,
            symbols=symbols,
            initial_equity=args.equity,
            offline=args.offline,
        ),
        store=store,
        notifier=TelegramNotifier(),
        costs=settings.costs,
        risk_settings=settings.risk,
    )
    _print_header("Paper Trading — gercek para YOK")
    print(f"Strateji : {strategy.name}")
    print(f"Borsa    : {args.exchange}   TF: {strategy.timeframe}")
    print(f"Sembol   : {len(symbols)}")
    print(f"Panel    : http://{settings.dashboard_host}:{settings.dashboard_port}")
    print("Durdurmak: Ctrl+C")
    print()
    try:
        if args.once:
            result = asyncio.run(engine.run_once())
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            asyncio.run(engine.run_forever())
    except KeyboardInterrupt:
        print("\nDurduruldu.")
    finally:
        store.close()
    return 0


# --------------------------------------------------------------------------
# canli / testnet
# --------------------------------------------------------------------------

def cmd_live(args) -> int:
    from .exchange import CcxtAdapter
    from .gates import check as gate_check
    from .notify import TelegramNotifier
    from .live import LiveRunner
    from .store import Store
    from .strategies import build as build_strategy

    settings = load_settings()
    strategy = build_strategy(args.strategy)
    symbols = tuple(args.symbols) if args.symbols else DEFAULT_POOL
    mode = args.mode

    _print_header(f"{mode.upper()} yurutucu — {strategy.name}")
    decision = gate_check(strategy, mode)
    if not decision.allowed:
        print(f"  ⛔ KAPI KAPALI: {decision.reason}")
        return 3
    print(f"  Kapı: {decision.reason}")

    if mode != "paper" and not settings.exchange.api_key:
        print("  ⛔ API anahtari yok (.env dosyasina EXCHANGE_API_KEY/SECRET yaz)")
        return 3

    store = Store(settings.db_path)
    store.set_kv("mode", mode)
    store.set_kv(f"initial_equity:{strategy.name}", args.equity)

    adapter = CcxtAdapter(settings.exchange)
    runner = LiveRunner(
        strategy=strategy,
        symbols=list(symbols),
        adapter=adapter,
        store=store,
        settings=settings.exchange,
        risk_settings=settings.risk,
        costs=settings.costs,
        notifier=TelegramNotifier(),
        initial_equity=args.equity,
        mode=mode,
    )
    print(f"  Sembol : {len(symbols)}")
    print("  Durdurmak: Ctrl+C")
    print()
    try:
        asyncio.run(runner.run_forever())
    except KeyboardInterrupt:
        print("\nDurduruldu.")
    except PermissionError as exc:
        print(f"  ⛔ {exc}")
    finally:
        asyncio.run(adapter.close())
        store.close()
    return 0


# --------------------------------------------------------------------------
# panel / durum / kapilar
# --------------------------------------------------------------------------

def cmd_dashboard(args) -> int:
    from .dashboard import run_dashboard

    settings = load_settings()
    run_dashboard(settings, args.strategy)
    return 0


def cmd_status(args) -> int:
    from .store import Store

    settings = load_settings()
    store = Store(settings.db_path)
    _print_header("Durum")
    stats = store.stats(args.strategy or None)
    print(f"Mod            : {store.get_kv('mode', settings.mode)}")
    print(f"Kapanan islem  : {stats['closed_trades']}")
    print(f"Kazanan oran   : {stats['win_rate'] * 100:.2f}%")
    pf = stats['profit_factor']
    print(f"Profit Factor  : {'—' if pf is None else f'{pf:.3f}'}")
    print(f"Expectancy     : {stats['expectancy_r']:+.4f} R")
    print(f"Toplam P&L     : ${stats['total_pnl_usd']:+.2f}")
    equity = stats.get("equity")
    equity_txt = "—" if equity is None else f"{equity:,.2f}"
    print(f"Equity         : {equity_txt}")
    print(f"Max Drawdown   : {stats['max_drawdown'] * 100:.2f}%")
    print()
    events = store.recent_events(10)
    if events:
        print("Son olaylar:")
        for e in events:
            print(f"  [{e['level']:5s}] {e['source']:6s} {e['message'][:90]}")
    store.close()
    return 0


def cmd_gates(args) -> int:
    from .gates import load_gates

    _print_header("Protokol kapilari")
    gates = load_gates()
    if not gates:
        print("  Kayit yok. `python -m trader backtest --stage insample` ile olusur.")
        return 0
    for strategy, stages in gates.items():
        print(f"\n  {strategy}")
        for stage, info in stages.items():
            mark = "GECTI" if info.get("passed") else "KALDI"
            print(f"    {stage:10s} {mark:6s} {info.get('recorded_at', '')}")
            if info.get("note"):
                print(f"               {info['note']}")
    return 0


# --------------------------------------------------------------------------
# argparse
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trader",
        description="TradeBot — calisir durumdaki trading programi",
    )
    p.add_argument("--version", action="version", version=f"TradeBot {__version__}")
    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("kurulum", aliases=["setup"], help="Kurulum kontrolu")
    sp.set_defaults(func=cmd_setup)

    sp = sub.add_parser("veri", aliases=["data"], help="Borsa verisi indir")
    sp.add_argument("--exchange", default="binance", choices=["binance", "bybit"])
    sp.add_argument("--timeframe", default="1d")
    sp.add_argument("--start", default="2021-01-01")
    sp.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    sp.add_argument("--symbols", nargs="*")
    sp.add_argument("--funding", action="store_true", help="Funding oranlarini da indir")
    sp.add_argument("--refresh", action="store_true", help="Onbellegi yoksay, yeniden indir")
    sp.set_defaults(func=cmd_data)

    sp = sub.add_parser("backtest", help="Backtest calistir")
    sp.add_argument("--strategy", default="sepet_momentum")
    sp.add_argument("--exchange", default="binance", choices=["binance", "bybit"])
    sp.add_argument("--timeframe", default="1d")
    sp.add_argument("--start", default="2021-01-01")
    sp.add_argument("--end", default="2024-12-31")
    sp.add_argument("--symbols", nargs="*")
    sp.add_argument("--equity", type=float, default=10000.0)
    sp.add_argument("--stage", default="insample", choices=["insample", "holdout", "none"])
    sp.add_argument("--kill-switch", action="store_true",
                    help="Risk kill switch'i backtestte de uygula "
                         "(varsayilan KAPALI: DD kapisi stratejinin kendi "
                         "drawdown'unu olcmelidir)")
    sp.set_defaults(func=cmd_backtest)

    sp = sub.add_parser("paper", help="Paper trading (gercek para yok)")
    sp.add_argument("--strategy", default="sepet_momentum")
    sp.add_argument("--exchange", default="binance", choices=["binance", "bybit"])
    sp.add_argument("--symbols", nargs="*")
    sp.add_argument("--equity", type=float, default=1000.0)
    sp.add_argument("--once", action="store_true", help="Tek tur calistir ve cik")
    sp.add_argument("--offline", action="store_true", help="Borsaya gitme, yerel veriyi kullan")
    sp.set_defaults(func=cmd_paper)

    sp = sub.add_parser("canli", aliases=["live"], help="Testnet/canli yurutucu")
    sp.add_argument("--strategy", default="sepet_momentum")
    sp.add_argument("--mode", default="testnet", choices=["testnet", "live"])
    sp.add_argument("--symbols", nargs="*")
    sp.add_argument("--equity", type=float, default=1000.0)
    sp.set_defaults(func=cmd_live)

    sp = sub.add_parser("panel", aliases=["dashboard"], help="Web panelini ac")
    sp.add_argument("--strategy", default="")
    sp.set_defaults(func=cmd_dashboard)

    sp = sub.add_parser("durum", aliases=["status"], help="Anlik durum")
    sp.add_argument("--strategy", default="")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("kapilar", aliases=["gates"], help="Protokol kapilari")
    sp.set_defaults(func=cmd_gates)
    return p


def main(argv: list[str] | None = None) -> int:
    # Windows konsolunda Turkce karakterler bozulmasin diye stdout UTF-8'e alinir.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)
