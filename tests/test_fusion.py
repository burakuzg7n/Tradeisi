"""Fuzyon paketi testleri (yalniz numpy; internet gerekmez)."""
import json

import numpy as np
import pytest

from fusion import ayar as ayar_m
from fusion import canli, durum, gostergeler as g, iletim, stratejiler, veri
from fusion.kural import Degerlendirici, KuralHatasi, kural_kaydet, kurallari_yukle
from fusion.motor import Emir, Motor
from fusion.strateji import Strateji
from fusion.veri import Bars, Piyasa

T0 = 1_699_999_200_000
ADIM = 900_000


def _bars(satirlar):
    return Bars.satirlardan([[T0 + i * ADIM, *s, 100.0] for i, s in enumerate(satirlar)])


def _ayar(tmp_path, **ek):
    a = dict(ayar_m.VARSAYILAN)
    a.update({"cikti": str(tmp_path / "out"), "komisyon_bps": 0.0, "kayma_bps": 0.0})
    a.update(ek)
    return a


class Senaryo(Strateji):
    """k -> emir listesi sozlugunden okuyan test stratejisi."""
    ad = "senaryo"

    def __init__(self, plan):
        self.plan = plan

    def bar(self, k, hesap, b):
        return self.plan.get(k, [])


# ---------------------------------------------------------------- gostergeler
def test_gostergeler_nedensel():
    x = np.cumsum(np.random.default_rng(1).normal(0, 1, 400)) + 100
    for fn in (lambda v: g.ema(v, 20), lambda v: g.rsi(v, 14), lambda v: g.sma(v, 10),
               lambda v: g.highest(v, 15), lambda v: g.zscore(v, 30)):
        tam, kisa = fn(x), fn(x[:300])
        np.testing.assert_allclose(tam[:300], kisa, equal_nan=True)


def test_sma_rsi_degerleri():
    assert g.sma(np.arange(1.0, 6.0), 2).tolist()[1:] == [1.5, 2.5, 3.5, 4.5]
    assert g.rsi(np.arange(1.0, 40.0), 14)[-1] == 100.0
    assert np.isnan(g.shift(np.arange(3.0), 1)[0])


# ----------------------------------------------------------------- kural dili
def test_kural_guvenli_ve_dogru():
    d = Degerlendirici(veri.sentetik("X", 500))
    b = d.bars
    np.testing.assert_array_equal(d.hesapla("close > open"), b.c > b.o)
    np.testing.assert_array_equal(d.hesapla("close[1] > 0")[1:], np.ones(499, dtype=bool))
    assert d.hesapla("").sum() == 0
    for kotu in ("__import__('os').system('x')", "close.real", "open('a')", "lambda: 1", "'metin'",
                 "ema(close)", "ema(99999)", "bilinmeyen > 1", "[1, 2]", "close if 1 else 2"):
        with pytest.raises(KuralHatasi):
            d.hesapla(kotu)


def test_kural_kaydet_ve_yukle(tmp_path):
    yol = kural_kaydet("Deneme 1", "rsi(14) < 30", "rsi(14) > 50", klasor=str(tmp_path))
    assert json.load(open(yol, encoding="utf-8"))["long_giris"] == "rsi(14) < 30"
    assert [s.ad for s in kurallari_yukle(str(tmp_path))] == ["kural_deneme_1"]
    with pytest.raises(KuralHatasi):
        kural_kaydet("kotu", "import os", klasor=str(tmp_path))


# ---------------------------------------------------------------------- motor
def test_dolum_sonraki_acilista_ve_stop(tmp_path):
    # bar0 sinyal, bar1 acilis 100'de dolum, bar2 stop 98'e degiyor
    b = _bars([(100, 101, 99, 100), (100, 102, 99.5, 101), (101, 101.5, 97, 97.5), (97.5, 98, 97, 97.5)])
    p = Piyasa({"AAA": b}, "15m")
    plan = {0: [Emir("AAA", 1, stop_mesafe=2.0, neden="test")]}
    r = Motor(p, [Senaryo(plan)], _ayar(tmp_path)).kos(0)
    h = r.hesaplar["senaryo"]
    t = h.islemler[0]
    assert t["giris"] == 100.0 and t["cikis"] == 98.0 and t["cikis_neden"] == "stop"
    assert t["adet"] == pytest.approx(1000 * 0.01 / 2.0)           # %1 risk / stop mesafesi
    assert t["pnl"] == pytest.approx(-10.0) and t["r"] == pytest.approx(-1.0)
    assert h.egri[0] == 1000.0 and h.egri[-1] == pytest.approx(990.0)


def test_bosluklu_stop_ve_ayni_barda_stop_oncelikli(tmp_path):
    # bar2 stopun altinda aciliyor -> acilistan dolar; kar-al ayni barda olsa bile stop sayilir
    b = _bars([(100, 101, 99, 100), (100, 100.5, 99.5, 100), (95, 110, 94, 96), (96, 97, 95, 96)])
    p = Piyasa({"AAA": b}, "15m")
    plan = {0: [Emir("AAA", 1, stop_mesafe=2.0, kar_mesafe=3.0)]}
    t = Motor(p, [Senaryo(plan)], _ayar(tmp_path)).kos(0).hesaplar["senaryo"].islemler[0]
    assert t["cikis"] == 95.0 and t["cikis_neden"] == "stop"


def test_short_kar_al_ve_maliyet(tmp_path):
    b = _bars([(100, 101, 99, 100), (100, 100.5, 99.5, 100), (100, 100.2, 96, 97), (97, 98, 96, 97)])
    p = Piyasa({"AAA": b}, "15m")
    plan = {0: [Emir("AAA", -1, stop_mesafe=2.0, kar_mesafe=3.0)]}
    a = _ayar(tmp_path, komisyon_bps=10.0)
    t = Motor(p, [Senaryo(plan)], a).kos(0).hesaplar["senaryo"].islemler[0]
    assert t["yon"] == -1 and t["cikis"] == 97.0 and t["cikis_neden"] == "kar al"
    assert t["pnl"] == pytest.approx(5 * 3.0 - 5 * 100 * 0.001 - 5 * 97 * 0.001)


def test_short_kapaliyken_short_acilmaz(tmp_path):
    b = _bars([(100, 101, 99, 100)] * 4)
    p = Piyasa({"AAA": b}, "15m")
    r = Motor(p, [Senaryo({0: [Emir("AAA", -1, stop_mesafe=2.0)]})], _ayar(tmp_path, short_acik=False)).kos(0)
    assert not r.hesaplar["senaryo"].poz and not r.hesaplar["senaryo"].islemler


def test_dd_kilidi_yeni_girisi_engeller(tmp_path):
    satirlar = [(100, 101, 99, 100), (100, 100, 60, 60)] + [(60, 61, 59, 60)] * 6
    p = Piyasa({"AAA": _bars(satirlar)}, "15m")
    plan = {0: [Emir("AAA", 1, agirlik=1.0)], 4: [Emir("AAA", 1, agirlik=1.0)]}
    r = Motor(p, [Senaryo(plan)], _ayar(tmp_path, dd_kilit_bar=100)).kos(0)
    h = r.hesaplar["senaryo"]
    assert any(o["tur"] == "KILIT" for o in r.olaylar)
    assert len(h.islemler) == 1 and not h.poz and h.islemler[0]["cikis_neden"] == "DD kilidi"


def _arena(tmp_path, n=5000, **ek):
    a = _ayar(tmp_path, komisyon_bps=5.0, kayma_bps=2.0, **ek)
    p = veri.piyasa_yukle(a["semboller"], "15m", sentetik_mi=True, sentetik_n=n)
    return a, p


def test_arena_calisir_deterministik_ve_fuzyon_sonda(tmp_path):
    a, p = _arena(tmp_path)
    liste = stratejiler.hepsi(a)
    assert liste[-1].ad == "fuzyon" and len({s.ad for s in liste}) == len(liste) >= 8
    r1 = Motor(p, liste, a).kos(3000)
    r2 = Motor(p, stratejiler.hepsi(a), a).kos(3000)
    for ad in r1.hesaplar:
        assert r1.hesaplar[ad].egri == r2.hesaplar[ad].egri
        assert len(r1.hesaplar[ad].egri) == 2000
    assert sum(len(h.islemler) for h in r1.hesaplar.values()) > 50
    assert r1.olaylar == r2.olaylar


def test_lookahead_yok_gelecek_degisince_gecmis_degismez(tmp_path):
    """Son 500 bari kesmek, kesim oncesindeki ozsermaye egrisini degistirmemeli."""
    a, p = _arena(tmp_path)
    tam = Motor(p, stratejiler.hepsi(a), a).kos(3000)
    kisa_p = Piyasa({s: b.kes(son_ts=int(p.T[4499])) for s, b in p.barlar.items()}, "15m")
    kisa = Motor(kisa_p, stratejiler.hepsi(a), a).kos(3000)
    for ad in tam.hesaplar:
        assert tam.hesaplar[ad].egri[:1500] == kisa.hesaplar[ad].egri, ad


def test_q_ajan_yalniz_gecmisle_egitilir(tmp_path):
    a, p = _arena(tmp_path)
    from fusion.stratejiler.qajan import QAjan
    q1, q2 = QAjan(), QAjan()
    q1.hazirla(p, 3000, a)
    bozuk = {s: Bars(b.ts, b.o, b.h, b.l, np.where(np.arange(len(b)) >= 3000, b.c * 2, b.c), b.v)
             for s, b in p.barlar.items()}
    q2.hazirla(Piyasa(bozuk, "15m"), 3000, a)
    assert q1.q == q2.q and q1.egitildi > 0


def test_rotasyon_tek_coin_tutar(tmp_path):
    a, p = _arena(tmp_path, stratejiler=["oran_rotasyon"])
    r = Motor(p, stratejiler.hepsi(a), a).kos(1000)
    h = r.hesaplar["oran_rotasyon"]
    assert len(h.poz) <= 1 and len(h.islemler) > 0


# ------------------------------------------------------------- durum / canli
def test_durum_json_gecerli(tmp_path):
    a, p = _arena(tmp_path, n=3000)
    r = Motor(p, stratejiler.hepsi(a), a).kos(2000)
    d = durum.olustur(r, "backtest")
    metin = json.dumps(d, allow_nan=False)            # nan/inf sizmamali
    assert json.loads(metin)["tablo"][0]["ozsermaye"] >= d["tablo"][-1]["ozsermaye"]
    assert len(d["egri_ts"]) == len(d["egriler"]["fuzyon"]) <= 302
    durum.islemleri_yaz(r, a, "t")
    durum.egrileri_yaz(r, a, "t")


def test_canli_yeniden_oynatma_ve_iletim(tmp_path, capsys):
    a, p = _arena(tmp_path, n=4000, canli_geri_gun=5)
    son = int(p.T[-1])
    # 1. tur: son 3 bar henuz yok
    p1 = Piyasa({s: b.kes(son_ts=son - 3 * ADIM) for s, b in p.barlar.items()}, "15m")
    d1, n1 = canli.tur(a, simdi_ms=son - 2 * ADIM, piyasa=p1, sessiz=True)
    assert n1 == 0 and d1["mod"] == "canli"
    k = canli.kayit_oku(a)
    # 2. tur: 3 yeni bar geldi; baslangic sabit, yalniz yeni olaylar iletilir
    d2, n2 = canli.tur(a, simdi_ms=son + ADIM, piyasa=p, sessiz=True)
    k2 = canli.kayit_oku(a)
    assert k2["baslangic_ts"] == k["baslangic_ts"] and d2["bar_sayisi"] == d1["bar_sayisi"] + 3
    assert k2["son_iletilen_ts"] >= k["son_iletilen_ts"]
    # ayni veride tekrar: yeni sinyal yok (cift iletim olmaz)
    _, n3 = canli.tur(a, simdi_ms=son + ADIM, piyasa=p, sessiz=True)
    assert n3 == 0


def test_iletim_secimi():
    olaylar = [{"tur": "SINYAL", "strateji": "a", "ts": 1}, {"tur": "GIRIS", "strateji": "a", "ts": 1},
               {"tur": "SINYAL", "strateji": "b", "ts": 1}]
    assert len(iletim.sec(olaylar, "hepsi", "b")) == 2
    assert [o["strateji"] for o in iletim.sec(olaylar, "lider", "b")] == ["b"]
    assert [o["strateji"] for o in iletim.sec(olaylar, "a", "b")] == ["a"]
    assert "LONG BTCUSDT" in iletim.metin({"tur": "SINYAL", "strateji": "a", "ts": 0, "yon": 1,
                                             "sembol": "BTCUSDT", "fiyat": 100.0, "neden": "x",
                                             "stop_mesafe": 2.0, "kar_mesafe": None})


def test_csv_gidis_donus(tmp_path):
    b = veri.sentetik("X", 50)
    yol = str(tmp_path / "X_15m.csv")
    veri.csv_yaz(yol, b)
    c = veri.csv_oku(yol)
    np.testing.assert_array_equal(b.ts, c.ts)
    np.testing.assert_array_equal(b.c, c.c)
