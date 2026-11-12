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


# ------------------------------------------------- 2. denetim turu (12 Kas 2026)
def test_pencere_bloklu_hesap_ayni_sonuc(monkeypatch):
    x = np.cumsum(np.random.default_rng(3).normal(0, 1, 3000)) + 50
    tam = [g.median(x, 672), g.std(x, 96), g.highest(x, 20), g.sma(x, 7)]
    monkeypatch.setattr(g, "BLOK_ELEMAN", 700)       # cok kucuk bloklara zorla
    for a, b in zip(tam, [g.median(x, 672), g.std(x, 96), g.highest(x, 20), g.sma(x, 7)]):
        np.testing.assert_allclose(a, b, equal_nan=True)


def _sahte_binance(monkeypatch, sunucu_simdi):
    cagri = {"n": 0}

    def sahte(url, zaman_asimi=20.0):
        from urllib.parse import parse_qs, urlparse
        u = urlparse(url)
        if u.path.endswith("/time"):
            return {"serverTime": sunucu_simdi}
        q = parse_qs(u.query)
        bas, limit = int(q["startTime"][0]), int(q["limit"][0])
        ilk = -(-bas // ADIM) * ADIM
        cagri["n"] += 1
        out = []
        t = ilk
        while t <= sunucu_simdi and len(out) < limit:      # son satir: henuz KAPANMAMIS mum
            out.append([t, "100.0", "101.0", "99.0", "100.5", "12.5", t + ADIM - 1])
            t += ADIM
        return out

    monkeypatch.setattr(veri, "_http_json", sahte)
    monkeypatch.setattr(veri.time, "sleep", lambda s: None)
    return cagri


def test_binance_indirme_sayfalar_ve_kapanmamis_mumu_almaz(monkeypatch):
    sunucu_simdi = T0 + 2500 * ADIM + 400_000              # 2501. mumun ortasi
    cagri = _sahte_binance(monkeypatch, sunucu_simdi)
    monkeypatch.setattr(veri, "simdi_ms", lambda: sunucu_simdi)
    b = veri.binance_mumlar("BTCUSDT", "15m", T0)
    assert len(b) == 2500 and cagri["n"] == 3               # 1000 + 1000 + 501 (sonuncusu acik mum)
    assert int(b.ts[0]) == T0 and int(b.ts[-1]) == T0 + 2499 * ADIM
    assert np.all(np.diff(b.ts) == ADIM)


def test_bilgisayar_saati_ileriyse_acik_mum_kapandi_sayilmaz(monkeypatch):
    """Bilgisayar saati 2 dk ileride: yerel saate gore mum 'kapanmis' gorunur ama alinmamali."""
    sunucu_simdi = T0 + 10 * ADIM + 880_000                 # 11. mumun bitmesine 20 sn var
    _sahte_binance(monkeypatch, sunucu_simdi)
    monkeypatch.setattr(veri.time, "time", lambda: (sunucu_simdi + 120_000) / 1000.0)
    monkeypatch.setitem(veri._SAAT, "okundu", 0.0)
    monkeypatch.setitem(veri._SAAT, "fark", 0)
    assert abs(veri.sunucu_farki(yenile=True) + 120_000) < 50
    b = veri.binance_mumlar("BTCUSDT", "15m", T0)
    assert len(b) == 10 and int(b.ts[-1]) == T0 + 9 * ADIM


def test_guncelle_dosyanin_sonuna_ekler(tmp_path, monkeypatch):
    tam = veri.sentetik("X", 30)
    yol = veri.csv_yolu("X", "15m", str(tmp_path))
    veri.csv_yaz(yol, tam.kes(son_ts=int(tam.ts[19])))
    with open(yol, "rb+") as f:                              # son satir sonu eksik dosya
        f.seek(-1, 2)
        f.truncate()
    monkeypatch.setattr(veri, "simdi_ms", lambda: int(tam.ts[-1]) + ADIM)
    monkeypatch.setattr(veri, "binance_mumlar",
                        lambda s, ar, bas, ilerleme=None: tam.kes(bas_ts=int(tam.ts[18])))  # 2 mum cakisik
    boyut = len(open(yol, "rb").read())
    b = veri.guncelle("X", "15m", 10, str(tmp_path))
    okunan = veri.csv_oku(yol)
    assert len(b) == len(okunan) == 30 and len(open(yol, "rb").read()) > boyut
    np.testing.assert_array_equal(okunan.ts, tam.ts)
    np.testing.assert_array_equal(okunan.c, tam.c)
    assert open(yol, encoding="utf-8").read().count("timestamp") == 1


def _duz(fiyatlar):
    return _bars([(f, f, f, f) for f in fiyatlar])


def test_rotasyon_asil_botun_esik_mantigi(tmp_path):
    from fusion.stratejiler.rotasyon import OranRotasyon
    n = 12
    p = Piyasa({"AAA": _duz([100.0] * n), "BBB": _duz([100.0] * 5 + [94.0] * (n - 5)),
                "CCC": _duz([100.0] * n)}, "15m")
    s = OranRotasyon()
    h = Motor(p, [s], _ayar(tmp_path, komisyon_bps=5.0, kayma_bps=2.0)).kos(0).hesaplar["oran_rotasyon"]
    assert list(h.poz) == ["BBB"] and [t["sembol"] for t in h.islemler] == ["AAA"]
    assert s.esik[("AAA", "BBB")] == pytest.approx(100 / 94)   # BBB'ye GIDEN ciftler guncellendi
    assert s.esik[("CCC", "BBB")] == pytest.approx(100 / 94)
    assert s.esik[("BBB", "AAA")] == 1.0                        # BBB'den cikan ciftler ayni kaldi
    assert s.oy_verir is False


def test_kirilim_izleyen_stop_kapanisla_cikar(tmp_path):
    from fusion.stratejiler.kirilim import Kirilim
    c = [100 + 0.1 * i for i in range(75)]
    c += [c[-1] - 0.6, c[-1] - 0.6, c[-1] - 0.6]             # zirveden 3 ATR'den fazla dusus (kapanis)
    satirlar = [((c[i - 1] if i else c[0]), c[i] + 0.05, c[i] - 0.05, c[i]) for i in range(len(c))]
    p = Piyasa({"AAA": _bars(satirlar)}, "15m")
    h = Motor(p, [Kirilim()], _ayar(tmp_path)).kos(0).hesaplar["kirilim"]
    t = h.islemler[0]
    assert t["yon"] == 1 and t["cikis_neden"] == "izleyen stop (kapanış)"
    koruyucu = t["giris"] - 3 * 0.15
    assert t["cikis"] > koruyucu and t["cikis"] > t["giris"]   # bar-ici koruyucu stop degil, iz suren cikis


def test_toplam_kaldirac_tavani(tmp_path):
    b = _bars([(100, 101, 99, 100)] * 5)
    p = Piyasa({"AAA": b, "BBB": b}, "15m")
    plan = {0: [Emir("AAA", 1, agirlik=1.0), Emir("BBB", 1, agirlik=1.0)]}
    h = Motor(p, [Senaryo(plan)], _ayar(tmp_path, max_kaldirac=1.0)).kos(0).hesaplar["senaryo"]
    assert list(h.poz) == ["AAA"]
    h2 = Motor(p, [Senaryo(plan)], _ayar(tmp_path, max_kaldirac=1.6)).kos(0).hesaplar["senaryo"]
    brut = sum(abs(q.adet) * q.son_fiyat for q in h2.poz.values())
    assert len(h2.poz) == 2 and brut == pytest.approx(1600.0, rel=1e-6)


def test_bekleme_surerken_sinyal_tekrarlanmaz(tmp_path):
    satirlar = [(100, 101, 99, 100), (100, 100.5, 99.5, 100), (100, 100, 97, 97.5)] + [(97.5, 98, 97, 97.5)] * 6
    p = Piyasa({"AAA": _bars(satirlar)}, "15m")
    plan = {k: [Emir("AAA", 1, stop_mesafe=2.0)] for k in range(0, 8)}
    r = Motor(p, [Senaryo(plan)], _ayar(tmp_path, bekleme_bar=8)).kos(0)
    assert len(r.hesaplar["senaryo"].islemler) == 1
    assert sum(1 for o in r.olaylar if o["tur"] == "SINYAL") == 1


def test_fuzyon_rotasyonu_oy_saymaz(tmp_path):
    a, p = _arena(tmp_path, n=3000)
    r = Motor(p, stratejiler.hepsi(a), a).kos(2500)
    for o in r.olaylar:
        if o["strateji"] == "fuzyon" and o["tur"] == "SINYAL":
            assert "oran_rotasyon" not in o["neden"]


def test_kirpma_yeniden_oynatmayi_degistirmez(tmp_path, monkeypatch):
    """Sona yeni mum eklenince (kesim noktasi sabit) onceki sonuc aynen kalmali."""
    monkeypatch.setattr(veri, "ISINMA_BAR", 1500)
    a, p = _arena(tmp_path, n=5000)
    bas = int(p.T[4000])
    kisa = Piyasa({s: b.kes(son_ts=int(p.T[4499])) for s, b in p.barlar.items()}, "15m")
    sonuclar = []
    for piyasa in (p, kisa):
        k = veri.kirp(piyasa, bas)
        assert len(k.T) == len(piyasa.T) - 2500
        sonuclar.append(Motor(k, stratejiler.hepsi(a), a).kos(k.k_bul(bas)))
    for ad in sonuclar[0].hesaplar:
        assert sonuclar[0].hesaplar[ad].egri[:500] == sonuclar[1].hesaplar[ad].egri, ad


def test_panel_http(tmp_path):
    import threading
    import urllib.request
    from fusion import panel
    a = _ayar(tmp_path, panel_port=0)
    s = panel.sunucu(a)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        kok = f"http://127.0.0.1:{s.server_address[1]}"
        assert "Füzyon Arena" in urllib.request.urlopen(kok + "/").read().decode("utf-8")
        assert json.load(urllib.request.urlopen(kok + "/api/durum?mod=canli")) == {"yok": True}
        _, p = _arena(tmp_path, n=2500)
        durum.yaz(durum.olustur(Motor(p, stratejiler.hepsi(a), a).kos(2000), "backtest"), a, "backtest")
        d = json.load(urllib.request.urlopen(kok + "/api/durum?mod=backtest"))
        assert d["mod"] == "backtest" and "brut_pnl" in d["tablo"][0] and "maliyet" in d["tablo"][0]
        assert json.load(urllib.request.urlopen(kok + "/api/durum?mod=../../x")) == {"yok": True}
    finally:
        s.shutdown()
        s.server_close()


def test_rastgele_yuruyuste_sistematik_kazanc_yok(tmp_path):
    """Motorun dolum mantigi iyimser olsaydi, yonsuz rastgele yuruyuste ve sifir maliyetle
    ortalama kazanc sifirdan anlamli bicimde buyuk cikardi. 40 farkli tohumda cikmamali."""
    from fusion.stratejiler.kirilim import Kirilim
    from fusion.stratejiler.kurul import AjanKurulu
    a = _ayar(tmp_path, dd_siniri=0.99)
    sonuc = {"ajan_kurulu": [], "kirilim": []}
    for tohum in range(40):
        barlar = {s: veri.sentetik(s, 3000, tohum=300 + tohum, ara_adim=96) for s in ("AAA", "BBB", "CCC")}
        r = Motor(Piyasa(barlar, "15m"), [AjanKurulu(), Kirilim()], a).kos(800)
        for ad in sonuc:
            sonuc[ad].append(r.hesaplar[ad].son_oz - 1000.0)
    for ad, v in sonuc.items():
        v = np.array(v)
        t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
        assert abs(t) < 3.0, (ad, round(float(v.mean()), 2), round(float(t), 2))
