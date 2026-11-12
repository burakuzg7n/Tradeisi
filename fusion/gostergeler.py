"""Teknik gostergeler (yalniz numpy). Hepsi nedenseldir: i. deger yalniz 0..i barlarini kullanir."""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def _bos(n: int) -> np.ndarray:
    return np.full(n, np.nan)


BLOK_ELEMAN = 4_000_000   # gecici dizi ust siniri (~32 MB); uzun pencerelerde bellek patlamasin


def _pencere(x, n: int, fn) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    out = _bos(len(x))
    n = int(n)
    if n >= 1 and len(x) >= n:
        gorunum = sliding_window_view(x, n)
        blok = max(1, BLOK_ELEMAN // n)
        for bas in range(0, len(gorunum), blok):
            out[n - 1 + bas: n - 1 + bas + blok] = fn(gorunum[bas: bas + blok], axis=1)
    return out


def sma(x, n):
    return _pencere(x, n, np.mean)


def std(x, n):
    return _pencere(x, n, np.std)


def highest(x, n):
    return _pencere(x, n, np.max)


def lowest(x, n):
    return _pencere(x, n, np.min)


def median(x, n):
    return _pencere(x, n, np.median)


def _ustel(x, alfa: float, isinma: int) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    out = _bos(len(x))
    gecerli = np.flatnonzero(~np.isnan(x))
    if len(gecerli) == 0:
        return out
    s = int(gecerli[0])
    onceki = float(x[s])
    out[s] = onceki
    xs = x.tolist()
    for i in range(s + 1, len(xs)):
        v = xs[i]
        if v == v:
            onceki += alfa * (v - onceki)
        out[i] = onceki
    out[: min(len(x), s + isinma - 1)] = np.nan
    return out


def ema(x, n):
    n = int(n)
    return _ustel(x, 2.0 / (n + 1.0), n)


def wilder(x, n):
    n = int(n)
    return _ustel(x, 1.0 / n, n)


def shift(x, n=1):
    x = np.asarray(x, dtype=float)
    n = int(n)
    out = _bos(len(x))
    if n == 0:
        return x.copy()
    if 0 < n < len(x):
        out[n:] = x[:-n]
    return out


def roc(x, n):
    x = np.asarray(x, dtype=float)
    onceki = shift(x, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        return x / onceki - 1.0


def rsi(x, n=14):
    x = np.asarray(x, dtype=float)
    d = np.diff(x, prepend=np.nan)
    kazanc = np.where(d > 0, d, 0.0)
    kayip = np.where(d < 0, -d, 0.0)
    kazanc[np.isnan(d)] = np.nan
    kayip[np.isnan(d)] = np.nan
    ak, ay = wilder(kazanc, n), wilder(kayip, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100.0 - 100.0 / (1.0 + ak / ay)
    out[(ay == 0) & ~np.isnan(ak)] = 100.0
    return out


def true_range(h, l, c):
    h, l, c = (np.asarray(a, dtype=float) for a in (h, l, c))
    oc = shift(c, 1)
    tr = np.fmax(h - l, np.fmax(np.abs(h - oc), np.abs(l - oc)))
    tr[0] = h[0] - l[0] if len(h) else np.nan
    return tr


def atr(h, l, c, n=14):
    return wilder(true_range(h, l, c), n)


def zscore(x, n):
    x = np.asarray(x, dtype=float)
    s = std(x, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (x - sma(x, n)) / s
    z[s == 0] = 0.0
    return z


def cross_up(a, b):
    a, b = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float))
    with np.errstate(invalid="ignore"):
        return (a > b) & (shift(a, 1) <= shift(b, 1))


def cross_down(a, b):
    a, b = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float))
    with np.errstate(invalid="ignore"):
        return (a < b) & (shift(a, 1) >= shift(b, 1))
