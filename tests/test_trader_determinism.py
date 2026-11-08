"""Motor determinizmi — ayni veri, ayni kod, ayni sonuc.

NEDEN BU KONU ONEMLI?
  Python'da string hash'i her surecte rastgele baslar (`PYTHONHASHSEED`).
  `set` uzerinde gezmek bu yuzden her surecte FARKLI bir sira verir.
  Float toplami da siraya baglidir: `1e16 + 1.0 + 1.0` ile
  `1.0 + 1.0 + 1e16` ayni sonucu vermez.

  Motor eskiden brut pozisyon toplamini `set` uzerinde gezerek aliyordu.
  Sonuc 1 ULP (1e-16) oynuyor, `result_gross > cap` kontrolu kenar
  durumunda KARAR degistiriyor ve portfoy yorumu kausik sekilde
  ayrisiyordu (ayni veri -> 812 / 821 / 830 farkli islem sayisi).

  Duzeltme: `gross_exposure()` hem SABIT SIRADA geziyor (sorted) hem de
  `math.fsum` ile topluyor (tam yuvarlanmis, sira bagimsiz).

  Bu test, hatali surumu YAKALAMAK icin tasarlandi: `list(set(...))` +
  elle toplam surumunde farkli `PYTHONHASHSEED` farkli sonuc verir.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- Alt surec betigi -------------------------------------------------------
#  Strateji agirliginin |w| toplami TAM 2.0 (long bacak 1.0 + short bacak 1.0),
#  `max_gross_leverage` = 2.0. Yani brut pozisyon her zaman cap'in TAM
#  esiginde. Elle float toplami sira degistiginde 1 ULP oynar ve
#  `gross > cap` KARARI doner -> olceklenme acilip kapanir -> ayrisma.
#  Bu, gercek kosudaki hatanin birebir mekanizmasidir.

_SNIPPET = r"""
import json
import numpy as np
import pandas as pd

from trader.backtest import Backtester
from trader.config import CostModel, RiskSettings
from trader.strategy import Signal

SYMS = ["AAAUSDT", "BBBUSDT", "CCCUSDT", "DDDUSDT", "EEEUSDT", "FFFUSDT"]
WEIGHTS = [0.5, -0.5, 0.5, -0.5, 0.25, -0.25]   # |w| toplami = 2.0 (cap esigi)


def panel(seed=7, n=900):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="1D", tz="UTC")
    out = {}
    for i, sym in enumerate(SYMS):
        p = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.03, len(idx)) + i * 0.0005))
        out[sym] = pd.DataFrame({
            "open": p, "high": p * 1.02, "low": p * 0.98, "close": p,
            "volume": rng.uniform(1000, 5000, len(idx)),
        }, index=idx).astype(float)
    return out


class W:
    name = "w"
    research_candidate = False
    timeframe = "1d"

    def generate(self, panel, ts):
        syms = sorted(panel.symbols())
        n = len(panel.frame(syms[0])) - 1
        if n % 7 != 0 or n == 0:
            return []
        return [Signal(symbol=s, side="long" if w >= 0 else "short",
                       action="target_weight", weight=w,
                       ts=ts.isoformat(), meta={})
                for s, w in zip(syms, WEIGHTS)]


bt = Backtester(costs=CostModel(),
                risk=RiskSettings(max_positions=6, max_gross_leverage=2.0,
                                  max_drawdown_pct=0.99),
                initial_equity=10000.0)
res = bt.run(panel(), W())
pnls = np.array([t.pnl_usd for t in res.trades])
gp = float(pnls[pnls > 0].sum())
gl = float(abs(pnls[pnls <= 0].sum()))
print(json.dumps({
    "trades": len(res.trades),
    "pf": repr(gp / gl) if gl else None,
    "final_equity": repr(float(res.final_equity)),
    "dd": repr(float(res.max_drawdown)),
}))
"""


def _run_snippet(seed: str) -> str:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, "-c", _SNIPPET],
        cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


# --- Testler ----------------------------------------------------------------

def test_backtest_is_deterministic_across_hash_seeds():
    """Ayni veri, farkli PYTHONHASHSEED -> BIREBIR ayni sonuc.

    Bu test `list(set(...))` + elle toplam surumunde BASARISIZ olur:
    seed=0 ile seed=1 farkli PF/equity verir.
    """
    outs = {seed: _run_snippet(seed) for seed in ("0", "1", "2", "424242")}
    unique = set(outs.values())
    assert len(unique) == 1, (
        "backtest deterministik degil — hash seed sonucu degistiriyor:\n"
        + "\n".join(f"  seed={k}: {v}" for k, v in outs.items())
    )


def test_gross_exposure_is_order_independent():
    """`gross_exposure` sira bagimsiz olmali (ve `math.fsum` kullanmali).

    Bu degerlerde elle float toplami HIC BIR sirada `math.fsum` ile ayni
    sonucu vermiyor; yani test gercekten bazi bir sirada kirmizi olur.
    """
    from trader.backtest import gross_exposure

    class P:
        def __init__(self, sign, qty, entry):
            self.sign = sign
            self.qty = qty
            self.entry_price = entry

    positions = {
        "AAAUSDT": P(1, 29463058.567562524, 1.0),
        "BBBUSDT": P(-1, 7571281.7751702955, 1.0),
        "CCCUSDT": P(1, 4.0334267118053116e-07, 1.0),
        "DDDUSDT": P(-1, 9.66240599677118e-18, 1.0),
        "EEEUSDT": P(1, 7.776244033209122e-18, 1.0),
        "FFFUSDT": P(-1, 2.6936224495141268e-21, 1.0),
    }
    prices = {s: 1.0 for s in positions}
    expected = 37034340.34273323          # math.fsum(parts)

    got = gross_exposure(positions, {}, prices)
    assert got == expected, (
        f"brut pozisyon toplami fsum ile hesaplanmali: {got!r} != {expected!r}"
    )

    # sembol sirasi degisse de sonuc ayni kalmali
    for sym in list(positions)[::-1]:
        assert gross_exposure({sym: positions[sym] for sym in reversed(list(positions))},
                              {}, prices) == expected


def test_gross_exposure_uses_targets_over_positions():
    """Ayni sembol icin hedef (target) notionali pozisyonu gecersiz kilar."""
    from trader.backtest import gross_exposure

    class P:
        sign, qty, entry_price = 1, 100.0, 2.0

    positions = {"XUSDT": P()}
    prices = {"XUSDT": 2.0}
    # target 50 -> hedef 50 kullanilir (pozisyonun 200'u degil)
    assert gross_exposure(positions, {"XUSDT": 50.0}, prices) == 50.0
    # target yoksa pozisyonun piyasa degeri
    assert gross_exposure(positions, {}, prices) == 200.0


def test_backtest_is_deterministic_within_process():
    """Ayni surecte iki kez calistirmak da ayni sonucu vermeli."""
    import numpy as np
    import pandas as pd

    from trader.backtest import Backtester
    from trader.config import CostModel, RiskSettings
    from trader.strategy import Signal

    def panel():
        rng = np.random.default_rng(7)
        idx = pd.date_range("2023-01-01", periods=120, freq="1D", tz="UTC")
        out = {}
        for i, sym in enumerate(["AAAUSDT", "BBBUSDT", "CCCUSDT"]):
            p = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.03, len(idx)) + i * 0.0005))
            out[sym] = pd.DataFrame({
                "open": p, "high": p * 1.02, "low": p * 0.98, "close": p,
                "volume": rng.uniform(1000, 5000, len(idx)),
            }, index=idx).astype(float)
        return out

    class W:
        name = "w"
        research_candidate = False
        timeframe = "1d"

        def generate(self, panel, ts):
            syms = sorted(panel.symbols())
            n = len(panel.frame(syms[0])) - 1
            if n % 7 != 0 or n == 0:
                return []
            return [Signal(symbol=s, side="long", action="target_weight",
                           weight=[0.5, -0.4, 0.3][i], ts=ts.isoformat(), meta={})
                    for i, s in enumerate(syms)]

    def run():
        bt = Backtester(costs=CostModel(),
                        risk=RiskSettings(max_positions=6, max_gross_leverage=2.0,
                                          max_drawdown_pct=0.99),
                        initial_equity=10000.0)
        res = bt.run(panel(), W())
        return (len(res.trades), repr(float(res.final_equity)),
                repr(float(res.max_drawdown)))

    assert run() == run()
