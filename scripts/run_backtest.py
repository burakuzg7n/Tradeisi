"""Backtest çalıştırıcı.

Kullanım:
    python scripts/run_backtest.py                       # data/ altındaki tüm semboller
    python scripts/run_backtest.py BTCUSDT               # tek sembol
    python scripts/run_backtest.py BTCUSDT --no-session  # session filtresiz
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradebot.backtest import Backtester, monte_carlo_dd
from tradebot.config import BacktestParams, StrategyParams
from tradebot.data import load_csv
from tradebot.strategy import generate_orders

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_DIR.mkdir(exist_ok=True)


def run_symbol(symbol: str, params: StrategyParams) -> dict | None:
    ltf_path = DATA_DIR / f"{symbol}_15m.csv"
    htf_path = DATA_DIR / f"{symbol}_4h.csv"
    if not ltf_path.exists() or not htf_path.exists():
        print(f"[{symbol}] veri yok: {ltf_path.name} / {htf_path.name}")
        return None

    ltf = load_csv(ltf_path)
    htf = load_csv(htf_path)

    # Veri sağlık kontrolü: tarihler mantıklı mı? (1970 çökmesi vb.)
    if ltf.index[0].year < 2015:
        print(f"[{symbol}] UYARI: veri tarihleri bozuk görünüyor "
              f"({ltf.index[0]}) — dosyayı silip yeniden indir.")
        return None

    orders = generate_orders(ltf, htf, params)
    result = Backtester(BacktestParams()).run(ltf, orders)

    summary = result.summary(bars_per_year=365 * 96)  # 15m: 96 bar/gün
    summary["symbol"] = symbol
    summary["orders_generated"] = len(orders)
    summary["session_filter"] = params.use_session_filter
    summary["monte_carlo"] = monte_carlo_dd([t.pnl_r for t in result.trades])

    # Volume filtreli varyant (Strategy Bible §7b)
    vf_params = replace(params, use_volume_filter=True)
    vf_orders = generate_orders(ltf, htf, vf_params)
    vf_result = Backtester(BacktestParams()).run(ltf, vf_orders)
    vf = vf_result.summary(bars_per_year=365 * 96)
    summary["volume_filter_variant"] = {
        "total_trades": vf["total_trades"],
        "win_rate": vf["win_rate"],
        "profit_factor": vf["profit_factor"],
        "expectancy_r": vf["expectancy_r"],
        "max_drawdown": vf["max_drawdown"],
    }

    print(f"\n=== {symbol} (session_filter={params.use_session_filter}) ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    # Kabul kriterleri (roadmap)
    ok = (
        summary["profit_factor"] is not None
        and summary["profit_factor"] > 1.3
        and summary["max_drawdown"] < 0.15
        and summary["expectancy_r"] > 0
    )
    trades_note = (
        "yeterli örnek" if summary["total_trades"] >= 300
        else f"UYARI: {summary['total_trades']} işlem < 300 — daha uzun veri gerekli"
    )
    print(f"  → Kriterler: {'GEÇTİ' if ok else 'KALDI'} ({trades_note})")
    return summary


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_session = "--no-session" not in sys.argv

    symbols = args or sorted(
        {p.name.split("_")[0] for p in DATA_DIR.glob("*_15m.csv")}
    )
    if not symbols:
        print("data/ klasöründe veri yok. Önce: python scripts/download_data.py")
        return

    params = replace(StrategyParams(), use_session_filter=use_session)
    all_results = [r for s in symbols if (r := run_symbol(s, params))]

    out = REPORT_DIR / "backtest_report.json"
    out.write_text(json.dumps(all_results, indent=2, ensure_ascii=False))
    print(f"\nRapor: {out}")


if __name__ == "__main__":
    main()
