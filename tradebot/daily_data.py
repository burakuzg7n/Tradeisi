"""Plan B günlük veri: Binance USDⓈ-M Futures PERPETUAL 1d mumları + E14 sağlık kontrolü.

Bu modül YALNIZ veri indirir ve denetler. Strateji, sinyal veya performans hesabı
yapmaz (SPEC_EKLERI: "geliştirme sırasında gerçek veride performans koşusu yapılmaz").

Kurallar: docs/SPEC_EKLERI.md E5b, E13, E14.
- Kaynak: fapi.binance.com, contractType=PERPETUAL, son işlem fiyatı OHLC, interval=1d.
- Yalnız KAPANMIŞ günlük mumlar kaydedilir (açılış + 1 gün <= şimdi).
- Listeleme öncesi günler eksik sayılmaz; "listeleme" = verideki ilk mum.
- Koşu engelleri (E14): dönem içi eksik gün > %1, bozuk bar, in-sample'da 2024-12-31
  barı yok (sembol bu tarihten önce listelenmişse).
"""
from __future__ import annotations

import hashlib
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

FAPI_BASE = "https://fapi.binance.com"
KLINES_PATH = "/fapi/v1/klines"
EXCHANGE_INFO_PATH = "/fapi/v1/exchangeInfo"
KLINES_LIMIT = 1500

DAY_MS = 86_400_000
EPOCH = date(1970, 1, 1)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")
INSAMPLE_START = date(2020, 1, 1)
INSAMPLE_END = date(2024, 12, 31)  # dahil
HOLDOUT_START = date(2025, 1, 1)
MAX_MISSING_RATIO = 0.01  # E14/1: %1'den FAZLASI engel
WARMUP_BARS = 55  # E5: yalnız bilgi amaçlı raporlanır

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]
PRICE_COLS = ["open", "high", "low", "close"]


class DataError(Exception):
    """Veri indirilemedi veya beklenen biçimde değil."""


# ---------------------------------------------------------------- tarih yardımcıları
def day_index(d: date) -> int:
    return (d - EPOCH).days


def day_date(i: int) -> date:
    return EPOCH + timedelta(days=int(i))


# ---------------------------------------------------------------- indirme
def _get(session, path: str, params: dict):
    resp = session.get(FAPI_BASE + path, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_contracts(session, symbols=SYMBOLS) -> dict:
    """exchangeInfo'dan sözleşme bilgisi. PERPETUAL değilse veya yoksa hata."""
    info = _get(session, EXCHANGE_INFO_PATH, {})
    by_symbol = {s.get("symbol"): s for s in info.get("symbols", [])}
    out = {}
    for sym in symbols:
        s = by_symbol.get(sym)
        if s is None:
            raise DataError(f"{sym}: exchangeInfo'da bulunamadı")
        if s.get("contractType") != "PERPETUAL":
            raise DataError(f"{sym}: sözleşme tipi PERPETUAL değil ({s.get('contractType')})")
        out[sym] = {
            "symbol": sym,
            "contractType": s.get("contractType"),
            "onboardDate": s.get("onboardDate"),
            "status": s.get("status"),
        }
    return out


def download_daily_rows(symbol: str, session, now_ms: int, start_ms: int = 0,
                        pause: float = 0.25, sleep=time.sleep) -> list:
    """Tüm 1d mumları sayfalayarak indirir; yalnız kapanmış mumları döndürür.

    Tekrar veya sıra bozukluğu SİLİNMEZ: sağlık kontrolü ham veriyi görmelidir.
    """
    rows: list = []
    cursor = int(start_ms)
    while True:
        batch = _get(session, KLINES_PATH, {
            "symbol": symbol, "interval": "1d",
            "startTime": cursor, "limit": KLINES_LIMIT,
        })
        if not batch:
            break
        rows.extend(batch)
        nxt = int(batch[-1][0]) + DAY_MS
        if nxt <= cursor:
            raise DataError(f"{symbol}: sayfalama ilerlemiyor (cursor={cursor})")
        cursor = nxt
        if len(batch) < KLINES_LIMIT or cursor + DAY_MS > now_ms:
            break
        sleep(pause)
    return [r for r in rows if int(r[0]) + DAY_MS <= now_ms]


def rows_to_frame(rows: list) -> pd.DataFrame:
    df = pd.DataFrame([[r[0], r[1], r[2], r[3], r[4], r[5]] for r in rows], columns=COLUMNS)
    df["timestamp"] = df["timestamp"].astype("int64")
    for c in COLUMNS[1:]:
        df[c] = df[c].astype(float)
    return df


def save_daily(df: pd.DataFrame, path: Path) -> None:
    df[COLUMNS].to_csv(path, index=False)


def load_daily_raw(path: Path) -> pd.DataFrame:
    """Ham okuma: tekrarlar silinmez, sıralanmaz (sağlık kontrolü için)."""
    df = pd.read_csv(path)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise DataError(f"{path.name}: eksik sütun {missing}")
    df = df[COLUMNS].copy()
    df["timestamp"] = df["timestamp"].astype("int64")
    for c in COLUMNS[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- sağlık kontrolü
def _iso(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _ranges(days: list) -> list:
    """Ardışık gün indekslerini [başlangıç, bitiş, adet] aralıklarına çevirir."""
    out = []
    for d in days:
        if out and d == out[-1][1] + 1:
            out[-1][1] = d
        else:
            out.append([d, d])
    return [{"from": str(day_date(a)), "to": str(day_date(b)), "days": b - a + 1} for a, b in out]


def bad_bars(df: pd.DataFrame) -> list:
    """E14/2 bozuk bar listesi (açıklamalı)."""
    out = []
    ts = df["timestamp"]
    dups = sorted(set(ts[ts.duplicated(keep=False)].tolist()))
    for t in dups:
        out.append(f"tekrarlanan zaman damgası: {_iso(t)}")
    p = df[PRICE_COLS]
    nan = p.isna().any(axis=1)
    nonpos = (p <= 0).any(axis=1)
    hl = df["high"] < df["low"]
    o_out = (df["open"] < df["low"]) | (df["open"] > df["high"])
    c_out = (df["close"] < df["low"]) | (df["close"] > df["high"])
    checks = [
        (nan, "sayısal olmayan/eksik fiyat"),
        (nonpos, "sıfır/negatif fiyat"),
        (hl, "high < low"),
        (o_out, "open [low, high] dışında"),
        (c_out, "close [low, high] dışında"),
    ]
    for mask, label in checks:
        for t in ts[mask.fillna(False)].tolist():
            out.append(f"{label}: {_iso(t)}")
    return out


def _period_stats(day_set: set, first: int, start: date, end: date) -> dict:
    s = max(day_index(start), first)
    e = day_index(end)
    if s > e:
        return {"from": None, "to": str(end), "expected_days": 0,
                "missing_days": 0, "missing_ratio": 0.0, "missing_ranges": []}
    missing = [d for d in range(s, e + 1) if d not in day_set]
    expected = e - s + 1
    return {
        "from": str(day_date(s)), "to": str(end),
        "expected_days": expected, "missing_days": len(missing),
        "missing_ratio": len(missing) / expected,
        "missing_ranges": _ranges(missing),
    }


def symbol_health(df: pd.DataFrame) -> dict:
    """Tek sembolün dönemden bağımsız sağlık bilgisi."""
    if len(df) == 0:
        raise DataError("boş veri")
    ts = df["timestamp"]
    warnings = []
    if not ts.is_monotonic_increasing:
        warnings.append("zaman damgaları sıralı değil")
    misaligned = ts[ts % DAY_MS != 0].tolist()
    for t in misaligned:
        warnings.append(f"00:00 UTC'ye hizalı olmayan mum: {_iso(t)}")
    days = sorted(set((ts // DAY_MS).tolist()))
    day_set = set(days)
    first, last = days[0], days[-1]
    missing_all = [d for d in range(first, last + 1) if d not in day_set]
    warmup_done = str(day_date(days[WARMUP_BARS - 1])) if len(days) >= WARMUP_BARS else None
    return {
        "rows": int(len(df)),
        "first_day": str(day_date(first)),
        "last_day": str(day_date(last)),
        "_first": first, "_last": last, "_days": day_set,
        "missing_after_listing": len(missing_all),
        "gaps_after_listing": _ranges(missing_all),
        "bad_bars": bad_bars(df),
        "warnings": warnings,
        "warmup_55_bar_done": warmup_done,
    }


def build_report(frames: dict, contracts: dict | None = None,
                 file_hashes: dict | None = None) -> dict:
    """E13/E14 veri sağlık raporu. frames: {sembol: ham DataFrame}."""
    contracts = contracts or {}
    file_hashes = file_hashes or {}
    per = {sym: symbol_health(df) for sym, df in frames.items()}
    common_end = day_date(min(h["_last"] for h in per.values()))
    blockers = []
    symbols = {}
    for sym, h in per.items():
        ins = _period_stats(h["_days"], h["_first"], INSAMPLE_START, INSAMPLE_END)
        hold = _period_stats(h["_days"], h["_first"], HOLDOUT_START, common_end)
        listed_before_end = h["_first"] <= day_index(INSAMPLE_END)
        has_end_bar = day_index(INSAMPLE_END) in h["_days"]
        if h["bad_bars"]:
            blockers.append(f"{sym}: {len(h['bad_bars'])} bozuk bar (E14/2)")
        if ins["missing_ratio"] > MAX_MISSING_RATIO:
            blockers.append(f"{sym}: in-sample eksik gün oranı %{ins['missing_ratio']*100:.2f} > %1 (E14/1)")
        if hold["missing_ratio"] > MAX_MISSING_RATIO:
            blockers.append(f"{sym}: hold-out eksik gün oranı %{hold['missing_ratio']*100:.2f} > %1 (E14/1)")
        if listed_before_end and not has_end_bar:
            blockers.append(f"{sym}: 2024-12-31 günlük barı yok (E14/3)")
        symbols[sym] = {
            "contract": contracts.get(sym),
            "file_sha256": file_hashes.get(sym),
            **{k: v for k, v in h.items() if not k.startswith("_")},
            "insample": ins,
            "insample_end_bar_present": has_end_bar,
            "holdout_end_bar_present": day_index(common_end) in h["_days"],
            "holdout": hold,
        }
    return {
        "kind": "PLANB_DATA_HEALTH",
        "note": "Yalnız veri sağlığı. Strateji/performans hesabı içermez.",
        "source": "Binance USDⓈ-M Futures, PERPETUAL, 1d, son işlem fiyatı OHLC",
        "insample": [str(INSAMPLE_START), str(INSAMPLE_END)],
        "holdout": [str(HOLDOUT_START), str(common_end)],
        "common_holdout_end": str(common_end),
        "max_missing_ratio": MAX_MISSING_RATIO,
        "symbols": symbols,
        "blockers": blockers,
        "verdict": "VERİ UYGUN" if not blockers else "VERİ ENGELLİ",
    }


def render_markdown(rep: dict) -> str:
    L = [f"# Plan B veri sağlık raporu — {rep['verdict']}", "",
         f"_{rep['note']}_", "",
         f"- Kaynak: {rep['source']}",
         f"- In-sample: {rep['insample'][0]} → {rep['insample'][1]}",
         f"- Hold-out (ortak bitiş, E13): {rep['holdout'][0]} → {rep['holdout'][1]}",
         f"- Eksik gün engel eşiği (E14/1): > %{rep['max_missing_ratio']*100:.0f}", ""]
    L += ["## Engeller", ""]
    L += [f"- {b}" for b in rep["blockers"]] or ["- Yok"]
    L += ["", "## Semboller", "",
          "| Sembol | İlk gün | Son gün | 55. bar | Eksik (listeleme sonrası) | In-sample eksik | 2024-12-31 | Hold-out eksik | Bozuk bar |",
          "|---|---|---|---|---|---|---|---|---|"]
    for sym, s in rep["symbols"].items():
        ins, hold = s["insample"], s["holdout"]
        L.append(
            f"| {sym} | {s['first_day']} | {s['last_day']} | {s['warmup_55_bar_done']} | "
            f"{s['missing_after_listing']} | {ins['missing_days']}/{ins['expected_days']} "
            f"(%{ins['missing_ratio']*100:.2f}) | {'var' if s['insample_end_bar_present'] else 'YOK'} | "
            f"{hold['missing_days']}/{hold['expected_days']} (%{hold['missing_ratio']*100:.2f}) | "
            f"{len(s['bad_bars'])} |")
    L += ["", "## Ayrıntılar", ""]
    for sym, s in rep["symbols"].items():
        c = s.get("contract") or {}
        L.append(f"### {sym}")
        L.append(f"- Sözleşme: {c.get('contractType')} · onboardDate: {c.get('onboardDate')} · durum: {c.get('status')}")
        L.append(f"- Dosya sha256: `{s.get('file_sha256')}` · satır: {s['rows']}")
        gaps = s["gaps_after_listing"]
        L.append("- Listeleme sonrası boşluklar: " +
                 (", ".join(f"{g['from']}→{g['to']} ({g['days']} gün)" for g in gaps) if gaps else "yok"))
        for w in s["warnings"]:
            L.append(f"- Uyarı: {w}")
        for b in s["bad_bars"][:20]:
            L.append(f"- Bozuk: {b}")
        L.append("")
    return "\n".join(L)
