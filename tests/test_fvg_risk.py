import pytest

from tests.conftest import make_df
from tradebot.fvg import fvg_at
from tradebot.risk import RiskEngine
from tradebot.config import RiskParams


# ---------- FVG ----------

def test_bullish_fvg_detected():
    bars = [
        (100, 101, 99, 100),    # mum1: high=101
        (100, 108, 100, 107),   # mum2: momentum
        (107, 109, 103, 108),   # mum3: low=103 > 101 → bullish FVG [101,103]
    ]
    df = make_df(bars)
    fvg = fvg_at(df, 2)
    assert fvg is not None and fvg.direction == 1
    assert fvg.bottom == 101 and fvg.top == 103
    # %50 doluluk üstten: 103 - 0.5*2 = 102
    assert fvg.fill_level(0.5) == pytest.approx(102)
    # %79 doluluk daha DERİN (daha düşük fiyat)
    assert fvg.fill_level(0.79) < fvg.fill_level(0.5)


def test_no_fvg_when_no_gap():
    bars = [(100, 101, 99, 100), (100, 102, 99.5, 101), (101, 103, 100.5, 102)]
    df = make_df(bars)
    assert fvg_at(df, 2) is None


def test_min_size_filter():
    bars = [
        (100, 100.01, 99, 100),
        (100, 100.05, 100, 100.04),
        (100.04, 100.06, 100.02, 100.05),  # gap 0.01 → %0.0001 < eşik
    ]
    df = make_df(bars)
    assert fvg_at(df, 2, min_size_pct=0.0005) is None


# ---------- Risk Engine ----------

def test_position_sizing():
    eng = RiskEngine(RiskParams(), account_balance=1000)
    s = eng.position_size(entry=50000, stop=49500)
    assert s.risk_amount == pytest.approx(5.0)          # %0.5
    assert s.position_size == pytest.approx(5.0 / 500)  # 0.01


def test_daily_kill_switch():
    eng = RiskEngine(RiskParams(), account_balance=1000)
    for _ in range(3):
        ok, _ = eng.can_trade()
        assert ok
        eng.record_result(-1.0, risk_amount=5.0)
    ok, msg = eng.can_trade()
    assert not ok
    assert eng.kill_switch_active


def test_r_locked_at_entry():
    """1R açılışta sabitlenir; bakiye değişse de aynı R ile kapanır."""
    eng = RiskEngine(RiskParams(), account_balance=1000)
    s = eng.position_size(50000, 49500)   # 1R = 5$
    eng.record_result(2.0, risk_amount=s.risk_amount)
    assert eng.current_balance == pytest.approx(1010.0)


def test_max_drawdown_kill():
    eng = RiskEngine(RiskParams(max_drawdown_pct=0.10), account_balance=1000)
    # 100$ kayıp = %10 DD
    eng.record_result(-20.0, risk_amount=5.0)
    assert eng.kill_switch_active
    assert eng.kill_switch_reason == "max_drawdown"


def test_rr_validation():
    eng = RiskEngine(RiskParams(min_rr=2.0), account_balance=1000)
    assert eng.validate_rr(100, 99, 102)       # RR=2 ✓
    assert not eng.validate_rr(100, 99, 101.5) # RR=1.5 ✗
