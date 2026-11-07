"""Performans olcumu.

Olcumler:
  * Ozet: PF, win rate, expectancy, DD, Sharpe, Sortino, Calmar
  * Yillik kirilim
  * HAC (Newey-West) t-statistik — islem getirilerinin otokorelasyonunu duzeltir
  * Bootstrap guven araligi (PF ve expectancy)
  * Etkin orneklem buyuklugu — korelasyon nedeniyle ham islem sayisi yaniltir
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def profit_factor(pnls: np.ndarray) -> float:
    if pnls.size == 0:
        return 0.0
    gp = float(pnls[pnls > 0].sum())
    gl = float(abs(pnls[pnls <= 0].sum()))
    if gl == 0:
        return float("inf") if gp > 0 else 0.0
    return gp / gl


def drawdown_series(equity: pd.Series) -> pd.Series:
    if equity is None or len(equity) == 0:
        return pd.Series(dtype=float)
    peak = equity.cummax()
    return (peak - equity) / peak.replace(0.0, np.nan)


def max_drawdown(equity: pd.Series) -> float:
    dd = drawdown_series(equity)
    return float(dd.max()) if len(dd) else 0.0


def sharpe_ratio(equity: pd.Series, periods_per_year: float) -> float:
    if equity is None or len(equity) < 3:
        return 0.0
    rets = equity.pct_change().dropna()
    sd = rets.std(ddof=1)
    if not np.isfinite(sd) or sd == 0:
        return 0.0
    return float(rets.mean() / sd * np.sqrt(periods_per_year))


def sortino_ratio(equity: pd.Series, periods_per_year: float) -> float:
    if equity is None or len(equity) < 3:
        return 0.0
    rets = equity.pct_change().dropna()
    downside = rets[rets < 0]
    dd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    if not np.isfinite(dd) or dd == 0:
        return 0.0
    return float(rets.mean() / dd * np.sqrt(periods_per_year))


def calmar_ratio(equity: pd.Series, periods_per_year: float) -> float:
    mdd = max_drawdown(equity)
    if mdd <= 0:
        return 0.0
    if equity is None or len(equity) < 2:
        return 0.0
    years = max(len(equity) / periods_per_year, 1e-9)
    cagr = (float(equity.iloc[-1]) / float(equity.iloc[0])) ** (1 / years) - 1
    return float(cagr / mdd)


def hac_tstat(values: np.ndarray, max_lag: int = 10) -> float:
    """Newey-West (HAC) t-statistik — ortalama getirinin anlamliligi.

    Islem getirileri zaman serisidir; otokorelasyon varsa naif t-stat
    yanlis guven verir. HAC bunu duzeltir.
    """
    x = np.asarray(values, dtype=float)
    n = x.size
    if n < 3:
        return 0.0
    x = x - x.mean()
    gamma0 = float(np.dot(x, x) / n)
    s = gamma0
    for lag in range(1, min(max_lag, n - 1) + 1):
        gamma = float(np.dot(x[lag:], x[:-lag]) / n)
        w = 1.0 - lag / (min(max_lag, n - 1) + 1)
        s += 2.0 * w * gamma
    if s <= 0:
        return 0.0
    se = float(np.sqrt(s / n))
    if se == 0:
        return 0.0
    return float(x.mean() / se)


def bootstrap_ci(values: np.ndarray, iterations: int = 2000, seed: int = 7,
                 stat: str = "expectancy") -> dict:
    """Bootstrap guven araligi (varsayilan %95)."""
    x = np.asarray(values, dtype=float)
    if x.size < 5:
        return {"lo": 0.0, "hi": 0.0, "point": float(x.mean()) if x.size else 0.0}
    rng = np.random.default_rng(seed)
    n = x.size
    stats = np.empty(iterations, dtype=float)
    for i in range(iterations):
        sample = rng.choice(x, size=n, replace=True)
        if stat == "pf":
            stats[i] = profit_factor(sample)
        else:
            stats[i] = sample.mean()
    return {
        "lo": float(np.percentile(stats, 2.5)),
        "hi": float(np.percentile(stats, 97.5)),
        "point": float(np.percentile(stats, 50)),
    }


def effective_sample_size(values: np.ndarray, threshold: float = 0.10) -> dict:
    """Korelasyon nedeniyle etkin orneklem buyuklugu.

    Ayni piyasa hareketinden etkilenen islemler bagimsiz gozum sayilmaz.
    |rho| > esik olan ardışık islem çiftleri "bagimli" sayilir ve etkin
    orneklem kuculur.
    """
    x = np.asarray(values, dtype=float)
    n = x.size
    if n < 3:
        return {"raw": int(n), "effective": int(n), "dependence_ratio": 0.0}
    dep = 0
    for i in range(n - 1):
        a, b = x[i], x[i + 1]
        denom = np.sqrt((a * a + 1e-12) * (b * b + 1e-12))
        rho = float(a * b / denom) if denom else 0.0
        if abs(rho) > threshold:
            dep += 1
    pairs = n - 1
    ratio = 1.0 - (dep / pairs) if pairs else 1.0
    return {
        "raw": int(n),
        "effective": int(round(n * max(ratio, 0.0))),
        "dependence_ratio": round(1.0 - max(ratio, 0.0), 4),
    }


def yearly_breakdown(trades: list) -> pd.DataFrame:
    """Yillik kirilim — kapanis yilina gore."""
    if not trades:
        return pd.DataFrame()
    rows = []
    df = pd.DataFrame([
        {
            "year": t.exit_ts.year,
            "symbol": t.symbol,
            "side": t.side,
            "pnl_usd": t.pnl_usd,
            "pnl_r": t.pnl_r,
        }
        for t in trades
    ])
    for year, grp in df.groupby("year"):
        pnls = grp["pnl_usd"].to_numpy(dtype=float)
        rows.append({
            "year": int(year),
            "trades": len(pnls),
            "win_rate": float((pnls > 0).mean()),
            "profit_factor": profit_factor(pnls),
            "pnl_usd": float(pnls.sum()),
            "pnl_r": float(grp["pnl_r"].mean()),
        })
    return pd.DataFrame(rows).sort_values("year")


def summarize(trades: list, equity: pd.Series | None,
              periods_per_year: float = 365.0) -> dict:
    """Backtest sonucu ozeti."""
    if not trades:
        return {
            "total_trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "expectancy_r": 0.0, "expectancy_usd": 0.0, "total_pnl_usd": 0.0,
            "avg_win_r": 0.0, "avg_loss_r": 0.0, "max_drawdown": 0.0,
            "sharpe": 0.0, "sortino": 0.0, "calmar": 0.0, "hac_t": 0.0,
            "final_equity": float(equity.iloc[-1]) if equity is not None and len(equity) else 0.0,
        }
    pnls = np.array([t.pnl_usd for t in trades], dtype=float)
    rs = np.array([t.pnl_r for t in trades], dtype=float)
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    out = {
        "total_trades": len(trades),
        "win_rate": float((pnls > 0).mean()),
        "profit_factor": profit_factor(pnls),
        "expectancy_r": float(rs.mean()),
        "expectancy_usd": float(pnls.mean()),
        "total_pnl_usd": float(pnls.sum()),
        "avg_win_r": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss_r": float(losses.mean()) if len(losses) else 0.0,
        "max_drawdown": max_drawdown(equity) if equity is not None else 0.0,
        "sharpe": sharpe_ratio(equity, periods_per_year) if equity is not None else 0.0,
        "sortino": sortino_ratio(equity, periods_per_year) if equity is not None else 0.0,
        "calmar": calmar_ratio(equity, periods_per_year) if equity is not None else 0.0,
        "hac_t": hac_tstat(rs),
    }
    out["expectancy_ci"] = bootstrap_ci(rs, stat="expectancy")
    out["pf_ci"] = bootstrap_ci(pnls, stat="pf")
    out["effective_sample"] = effective_sample_size(rs)
    return out
