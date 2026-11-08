"""Performans olcumleri — regresyon testleri."""
from __future__ import annotations

import numpy as np
import pytest

from trader.metrics import (
    bootstrap_ci,
    effective_sample_size,
    hac_tstat,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
)


def test_profit_factor_basic():
    x = np.array([100.0, -50.0, 25.0, -25.0])
    assert profit_factor(x) == pytest.approx(125.0 / 75.0)


def test_hac_tstat_is_not_always_zero():
    """REGRESYON: ortalama demean SONRASI alinca t-statistik daima 0 cikiyordu."""
    rng = np.random.default_rng(3)
    x = rng.normal(loc=0.5, scale=1.0, size=400)
    t = hac_tstat(x)
    assert t > 2.0
    assert t != 0.0


def test_hac_tstat_zero_for_constant_series():
    assert hac_tstat(np.ones(50)) == 0.0


def test_hac_tstat_too_short():
    assert hac_tstat(np.array([1.0])) == 0.0


def test_effective_sample_size_is_sane():
    """REGRESYON: onceki surum kosinus benzerligi kullaniyordu; getiri
    serilerinde etkin orneklem 0'a duserdi."""
    rng = np.random.default_rng(11)
    x = rng.normal(size=500)
    out = effective_sample_size(x)
    assert out["raw"] == 500
    assert 0 < out["effective"] <= 500
    assert 0.0 <= out["dependence_ratio"] < 1.0


def test_effective_sample_size_detects_strong_autocorrelation():
    """Seri kendi kendine cok bagimliysa etkin orneklem kuculur."""
    rng = np.random.default_rng(5)
    noise = rng.normal(size=1000)
    x = np.empty(1000)
    x[0] = noise[0]
    for i in range(1, 1000):
        x[i] = 0.9 * x[i - 1] + noise[i]   # lag-1 korelasyon ~0.9
    out = effective_sample_size(x)
    assert out["effective"] < out["raw"] / 2


def test_effective_sample_size_short_series():
    out = effective_sample_size(np.array([1.0, 2.0]))
    assert out["effective"] == 2


def test_bootstrap_ci_contains_point():
    rng = np.random.default_rng(1)
    x = rng.normal(loc=0.2, size=200)
    out = bootstrap_ci(x)
    assert out["lo"] < out["point"] < out["hi"]


def test_max_drawdown_and_sharpe():
    import pandas as pd

    eq = pd.Series([100.0, 120.0, 90.0, 150.0])
    assert max_drawdown(eq) == pytest.approx(0.25)
    assert sharpe_ratio(eq, 365.0) != 0.0
