"""Rapor uretimi — backtest sonuclari (JSON + Markdown).

Raporlar `out/reports/` altina yazilir. `reports/` (muhurlu arsiv) DEGISTIRILMEZ.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .backtest import BacktestResult
from .config import REPORT_DIR
from .metrics import summarize, yearly_breakdown


def build_report(result: BacktestResult, strategy: str, meta: dict | None = None) -> dict:
    periods_per_year = float((meta or {}).get("periods_per_year", 365))
    summary = summarize(result.trades, result.equity_curve, periods_per_year)
    years = yearly_breakdown(result.trades)
    report = {
        "strategy": strategy,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta or {},
        "summary": summary,
        "yearly": years.to_dict(orient="records") if len(years) else [],
        "kill_switch": {
            "triggered": result.kill_switch_triggered,
            "reason": result.kill_switch_reason,
        },
        "costs": {
            "fees_paid": round(result.fees_paid, 4),
            "funding_paid": round(result.funding_paid, 4),
        },
        "accepted_signals": len(result.accepted_signals),
        "rejected_signals": len(result.rejected_signals),
        "initial_equity": result.initial_equity,
        "final_equity": result.final_equity,
    }
    if result.equity_curve is not None and len(result.equity_curve):
        report["equity"] = {
            "start": str(result.equity_curve.index[0]),
            "end": str(result.equity_curve.index[-1]),
            "points": len(result.equity_curve),
        }
    return report


def _fmt_pct(x: float) -> str:
    return f"%{x * 100:.2f}"


def render_markdown(report: dict) -> str:
    s = report["summary"]
    meta = report.get("meta", {})
    lines = [
        f"# Backtest Raporu — {report['strategy']}",
        "",
        f"**Uretim:** {report['generated_at']}",
        f"**Donem:** {meta.get('start', '?')} → {meta.get('end', '?')}",
        f"**Evren:** {meta.get('universe', '-')}",
        f"**Borsa/veri:** {meta.get('source', '-')}",
        f"**Ucret modeli:** maker {meta.get('maker_fee', '-')} / taker "
        f"{meta.get('taker_fee', '-')} / slippage {meta.get('slippage', '-')}",
        "",
        "## Ozet",
        "",
        "| Metrik | Deger |",
        "|---|---|",
        f"| Toplam islem | {s['total_trades']} |",
        f"| Kazanan oran | {_fmt_pct(s['win_rate'])} |",
        f"| Profit Factor | {s['profit_factor']:.3f} |",
        f"| Expectancy (R/islem) | {s['expectancy_r']:+.4f} |",
        f"| Expectancy ($/islem) | {s['expectancy_usd']:+.2f} |",
        f"| Toplam P&L | ${s['total_pnl_usd']:+.2f} |",
        f"| Ort. kazanc (R) | {s['avg_win_r']:+.3f} |",
        f"| Ort. kayip (R) | {s['avg_loss_r']:+.3f} |",
        f"| Max Drawdown | {_fmt_pct(s['max_drawdown'])} |",
        f"| Sharpe | {s['sharpe']:.2f} |",
        f"| Sortino | {s['sortino']:.2f} |",
        f"| Calmar | {s['calmar']:.2f} |",
        f"| HAC t (islem ort.) | {s['hac_t']:.3f} |",
        f"| Baslangic equity | ${report['initial_equity']:,.2f} |",
        f"| Bitis equity | ${report['final_equity']:,.2f} |",
        "",
    ]

    if "expectancy_ci" in s:
        ci = s["expectancy_ci"]
        lines += [
            "## Istatistiksel belirsizlik",
            "",
            f"- Expectancy %95 bootstrap guven araligi: "
            f"[{ci['lo']:+.4f}, {ci['hi']:+.4f}] R",
        ]
        if "pf_ci" in s:
            pci = s["pf_ci"]
            lines.append(
                f"- PF %95 bootstrap guven araligi: [{pci['lo']:.3f}, {pci['hi']:.3f}]"
            )
        eff = s.get("effective_sample", {})
        if eff:
            lines.append(
                f"- Ham islem: {eff.get('raw')} | Etkin orneklem: "
                f"{eff.get('effective')} (bagimlilik orani {eff.get('dependence_ratio')})"
            )
        lines.append("")

    if report.get("yearly"):
        lines += [
            "## Yillik kirilim",
            "",
            "| Yil | Islem | Kazanan | PF | P&L | Ort R |",
            "|---|---|---|---|---|---|",
        ]
        for row in report["yearly"]:
            lines.append(
                f"| {row['year']} | {row['trades']} | {_fmt_pct(row['win_rate'])} | "
                f"{row['profit_factor']:.3f} | ${row['pnl_usd']:+.2f} | "
                f"{row['pnl_r']:+.3f} |"
            )
        lines.append("")

    ks = report.get("kill_switch", {})
    if ks.get("triggered"):
        lines += ["## Kill switch", "", f"- TETIKLENDI: {ks.get('reason')}", ""]

    costs = report.get("costs", {})
    lines += [
        "## Maliyetler",
        "",
        f"- Toplam ucret: ${costs.get('fees_paid', 0):.2f}",
        f"- Toplam funding (net): ${costs.get('funding_paid', 0):.2f}",
        "",
        "---",
        "",
        "> Bu rapor bir **kazanc garantisi degildir**. Gecmis veri performansi "
        " gelecekteki sonucu garanti etmez. Canliya gecis kapilari `AGENTS.md` "
        " ve `docs/KARAR_NOTU_C_2026-11-02.md` dosyalarinda tanimlidir.",
    ]
    return "\n".join(lines)


def write_report(report: dict, name: str, directory: Path | None = None) -> tuple[Path, Path]:
    directory = directory or REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base = f"{name}_{stamp}"
    json_path = directory / f"{base}.json"
    md_path = directory / f"{base}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def equity_to_csv(equity_curve: pd.Series, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = equity_curve.rename("equity").to_frame()
    out.index.name = "timestamp"
    out.to_csv(path, index=True)
    return path
