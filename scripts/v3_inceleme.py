"""V3 in-sample sonuç incelemesi — YALNIZ mevcut arşivlerden (yeniden backtest YOK).

Girdi: reports/V3_INSAMPLE.json + _islemler.csv + _gunluk.csv + _equity.csv
Çıktı: reports/V3_INSAMPLE_INCELEME.md, reports/V3_INSAMPLE_INCELEME_dd_islemleri.csv
Strateji, motor veya veri dosyası çalıştırılmaz/okunmaz. HAC burada motordan
BAĞIMSIZ yazılmıştır (protokoldeki fonksiyon çağrılmaz).
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
SLIP = 0.0003            # spec §5 model slippage (motorun uyguladığı sabit oran)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def sha_variants(p: Path) -> dict:
    b = p.read_bytes()
    return {"as_is": hashlib.sha256(b).hexdigest(),
            "crlf": hashlib.sha256(b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest(),
            "lf": hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()}


def canon_seal_ok(r: dict) -> bool:
    body = {k: v for k, v in r.items() if k != "integrity"}
    s = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest() == r.get("integrity")


def hac(x: np.ndarray):
    T = len(x)
    L = int(math.floor(4 * (T / 100) ** (2 / 9)))
    m = float(np.mean(x))
    e = x - m
    gam = [float(np.dot(e[k:], e[:T - k]) / T) for k in range(L + 1)]
    var = gam[0] + 2 * sum((1 - k / (L + 1)) * gam[k] for k in range(1, L + 1))
    se = math.sqrt(var / T) if var > 0 else 0.0
    return m, se, L, (m / se if se > 0 else float("nan"))


def iso(ms) -> str:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def main() -> int:
    r = json.loads((REP / "V3_INSAMPLE.json").read_text(encoding="utf-8"))
    m = r["metrics"]
    arch = r["archive"]
    L = ["# V3 in-sample — sonuç incelemesi (yalnız arşivden)", "",
         "**Kapsam:** Bu inceleme yeni backtest yapmaz; yalnız mühürlü rapor ve üç ham arşiv",
         "CSV'si okunur. Amaç teşhistir; stratejiyi kurtarma, parametre önerme veya yeni strateji",
         "önerme içermez. Neden ilanı bağımsız denetimden sonra yapılır.", ""]

    # 1. Mühür ve hash'ler
    L += ["## 1. Mühür, hash ve yeniden hesap", ""]
    L.append(f"- Rapor mührü (kanonik JSON sha256): **{'geçerli' if canon_seal_ok(r) else 'GEÇERSİZ'}**")
    for k, a in arch.items():
        v = sha_variants(REP / a["file"])
        match = [n for n, h in v.items() if h == a["sha256"]]
        L.append(f"- `{a['file']}`: mühürlü sha256 ile eşleşen biçim: "
                 f"**{', '.join(match) if match else 'YOK'}** "
                 "(dosyalar Windows'ta CRLF yazıldı; git deposunda LF saklanır)")
    tr = pd.read_csv(REP / arch["trades"]["file"])
    daily = pd.read_csv(REP / arch["daily"]["file"])
    eq = pd.read_csv(REP / arch["equity"]["file"])
    gp = tr.loc[tr.pnl > 0, "pnl"].sum()
    gl = -tr.loc[tr.pnl <= 0, "pnl"].sum()
    pf = gp / gl
    e = eq["equity"].to_numpy()
    peak = np.maximum.accumulate(e)
    ddv = (peak - e) / peak
    dd = float(ddv.max())
    mean, se, lag, t = hac(daily["r_d"].to_numpy())
    rows = [("PF", pf, float(m["profit_factor"])), ("Max DD", dd, float(m["max_drawdown"])),
            ("Günlük ortalama", mean, float(m["daily"]["mean"])),
            ("HAC SE", se, float(m["daily"]["hac_se"])), ("HAC t", t, float(m["daily"]["hac_t"])),
            ("İşlem sayısı", len(tr), m["total_trades"]),
            ("Net PnL (işlemler)", tr.pnl.sum(), float(m["net_pnl"])),
            ("Σ r_d × 10.000", daily.r_d.sum() * 10_000, float(m["net_pnl"]))]
    L += ["", "| Ölçü | Arşivden yeniden hesap | Raporda | Eşleşme |", "|---|---:|---:|---|"]
    for name, a, b in rows:
        ok = math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-6)
        L.append(f"| {name} | {float(a):.6g} | {float(b):.6g} | {'✓' if ok else '✗'} |")
    L.append(f"\nHAC: Bartlett, L = {lag}, T = {len(daily)} gün (işlemsiz günler 0 dahil).")

    # 2. Equity ve en büyük düşüş
    i_tr = int(np.argmax(ddv))
    i_pk = int(np.argmax(e[:i_tr + 1]))
    pk_ts, tr_ts = int(eq.ts.iloc[i_pk]), int(eq.ts.iloc[i_tr])
    L += ["", "## 2. Equity ve en büyük düşüş", "",
          f"- Başlangıç equity: {e[0]:,.2f} $ · son equity: {e[-1]:,.2f} $ · en yüksek: {e.max():,.2f} $ "
          f"({iso(eq.ts.iloc[int(np.argmax(e))])})",
          f"- En büyük düşüş: **%{dd*100:.2f}** — zirve {e[i_pk]:,.2f} $ ({iso(pk_ts)} UTC) → dip "
          f"{e[i_tr]:,.2f} $ ({iso(tr_ts)} UTC)"]
    in_dd = tr[(tr.fill_ts >= pk_ts) & (tr.exit_ts <= tr_ts + 900_000)]
    in_dd.to_csv(REP / "V3_INSAMPLE_INCELEME_dd_islemleri.csv", index=False)
    L += [f"- Bu aralıkta açılıp kapanan işlem: **{len(in_dd)}** (tam liste: "
          f"`V3_INSAMPLE_INCELEME_dd_islemleri.csv`), net {in_dd.pnl.sum():,.2f} $, "
          f"kazanma %{(in_dd.pnl > 0).mean()*100:.1f}, ortalama R {in_dd.r.mean():.3f}",
          f"- Çıkış sebepleri (aralık): {in_dd.reason.value_counts().to_dict()}"]
    # yıllık equity (bilgi)
    eq["date"] = pd.to_datetime(eq.ts, unit="ms", utc=True)
    ye = eq.groupby(eq.date.dt.year)["equity"].agg(["first", "last", "min", "max"])
    L += ["", "| Yıl | equity başı | sonu | min | max |", "|---|---:|---:|---:|---:|"]
    for y, row in ye.iterrows():
        L.append(f"| {y} | {row['first']:,.0f} | {row['last']:,.0f} | {row['min']:,.0f} | {row['max']:,.0f} |")

    # 3. Brüt / ücret / funding / model slippage
    sign = np.where(tr.side == "long", 1.0, -1.0)
    gross_after_slip = sign * (tr.exit - tr.entry) * tr.qty
    fees = tr.entry_fee + tr.exit_fee
    # Model slippage'ı arşivdeki fiyatlardan geri hesaplamak: giriş F = açılış×(1±s) → açılış = F/(1±s).
    raw_entry = np.where(tr.side == "long", tr.entry / (1 + SLIP), tr.entry / (1 - SLIP))
    slip_entry = np.abs(tr.entry - raw_entry) * tr.qty
    slipped_exit = tr.reason.isin(["stop", "time_exit", "time_exit_deferred", "gap_stop", "gap_through_stop"])
    raw_exit = np.where(tr.side == "long", tr.exit / (1 - SLIP), tr.exit / (1 + SLIP))
    slip_exit = np.where(slipped_exit, np.abs(raw_exit - tr.exit) * tr.qty, 0.0)
    slip = slip_entry + slip_exit
    gross_raw = gross_after_slip + slip
    tot = {"Brüt (slippage öncesi, model)": gross_raw.sum(),
           "− Model slippage (motorun uyguladığı %0,03)": -slip.sum(),
           "− Ücretler (taker/maker)": -fees.sum(),
           "− Funding": -tr.funding.sum(),
           "= Net": tr.pnl.sum()}
    risk = tr.risk_usd
    L += ["", "## 3. Brüt sonuç ve maliyetlerin ayrıştırılması", "",
          "| Kalem | USD | İşlem başına R (ortalama) |", "|---|---:|---:|"]
    per_r = {"Brüt (slippage öncesi, model)": (gross_raw / risk).mean(),
             "− Model slippage (motorun uyguladığı %0,03)": -(slip / risk).mean(),
             "− Ücretler (taker/maker)": -(fees / risk).mean(),
             "− Funding": -(tr.funding / risk).mean(),
             "= Net": tr.r.mean()}
    for k, v in tot.items():
        L.append(f"| {k} | {v:,.2f} | {per_r[k]:.4f} |")
    chk = gross_raw.sum() - slip.sum() - fees.sum() - tr.funding.sum()
    L += ["", f"Kontrol: brüt − slippage − ücret − funding = {chk:,.2f} $ (net {tr.pnl.sum():,.2f} $).",
          "**Sınırlama:** slippage, arşivdeki dolum fiyatlarından **modelin sabit formülü** tersine",
          "çevrilerek bulundu; bu, motorun uyguladığı model slippage'ıdır, gerçek piyasa",
          "slippage'ı değildir. Arşivde ham açılış/kapanış fiyatları ayrıca yok.",
          "**Not:** USD toplamları bakiyeye bağlı değişen işlem boyutundan etkilenir (bakiye",
          "düştükçe aynı R daha küçük USD'dir); R sütunu boyuttan bağımsız karşılaştırma içindir."]
    # brüt R dağılımı
    gr = gross_raw / risk
    L += ["", f"Brüt R (maliyet öncesi) dağılımı: ortalama {gr.mean():.4f}, medyan {gr.median():.4f}, "
          f"std {gr.std():.4f}; kazanma oranı (brüt) %{(gross_raw > 0).mean()*100:.1f}, "
          f"(net) %{(tr.pnl > 0).mean()*100:.1f}."]

    # 4. Teşhis: long/short, sembol, çıkış sebebi
    def tab(group, title):
        g = tr.assign(gross_r=gr, cost_r=(slip + fees + tr.funding) / risk).groupby(group)
        out = ["", f"### {title}", "", "| Grup | İşlem | Brüt R ort. | Maliyet R ort. | Net R ort. | Net $ |",
               "|---|---:|---:|---:|---:|---:|"]
        for k, x in g:
            out.append(f"| {k} | {len(x)} | {x.gross_r.mean():.4f} | {x.cost_r.mean():.4f} | "
                       f"{x.r.mean():.4f} | {x.pnl.sum():,.2f} |")
        return out
    L += ["", "## 4. Dağılım (yalnız teşhis; kötü grupları çıkararak strateji kurtarılmaz)"]
    L += tab("side", "Yön")
    L += tab("symbol", "Sembol")
    L += tab("reason", "Çıkış sebebi")

    # 5. Önceki reddedilenlerle ortaklık (kanıt düzeyiyle)
    v2 = json.loads((REP / "V2_INSAMPLE.json").read_text(encoding="utf-8"))["combined"]
    pb = json.loads((REP / "PLANB_INSAMPLE.json").read_text(encoding="utf-8"))["metrics"]
    L += ["", "## 5. Önceki reddedilen stratejilerle karşılaştırma (kanıt düzeyi belirtilerek)", "",
          "| Strateji | TF | İşlem | PF (net) | Beklenti R (net) | DD | Maliyet ayrıştırması |",
          "|---|---|---:|---:|---:|---:|---|",
          "| V1 | 15m/4h | ~800 | 0,78–0,82 | — | — | Yok (YILLIK_ANALIZ: \"maliyet sürtünmesi + gürültü profiline uyuyor\" — yorum, ölçüm değil) |",
          f"| V2 | 15m/4h | {v2['total_trades']} | {float(v2['profit_factor']):.3f} | {float(v2['expectancy_r']):.3f} | "
          f"%{float(v2['max_drawdown'])*100:.1f} | Yok (arşiv tutulmadı) |",
          f"| Plan B v1 | 1g | {pb['total_trades']} | {float(pb['profit_factor']):.3f} | {float(pb['expectancy_r']):.3f} | "
          f"%{float(pb['max_drawdown'])*100:.1f} | Ücret {float(pb['total_fees']):.0f} $, funding {float(pb['total_funding']):.0f} $ (toplamlar; işlem bazında arşiv yok) |",
          f"| V3 | 15m | {len(tr)} | {pf:.3f} | {tr.r.mean():.3f} | %{dd*100:.1f} | Var (bu belge §3) |", "",
          "**Kanıtlanabilir ortaklıklar:**",
          "- Gün içi (15m) üç stratejinin (V1, V2, V3) üçü de maliyetler dahil PF < 1 verdi (ölçüm).",
          "- Maliyetin brüt sonuca oranı yalnız V3 için ölçülebiliyor (§3); V1/V2 için işlem bazında",
          "  arşiv olmadığından aynı ayrıştırma **yapılamaz**. \"Ortak sebep maliyet\" iddiası bu",
          "  nedenle V3 dışına genellenemez.",
          "- Plan B v1 (günlük) farklı biçimde kaldı: net PF > 1 ama işlem sayısı ve DD kapıları.",
          "",
          "**Bu belgede yapılmayanlar:** neden ilanı, yeni strateji/parametre önerisi, hold-out,",
          "yeniden backtest. Sonraki adım bağımsız denetimdir."]
    out = REP / "V3_INSAMPLE_INCELEME.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
