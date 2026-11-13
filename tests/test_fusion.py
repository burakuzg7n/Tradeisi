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
    assert len(b) == len(okunan) == 30                         # bellekten: yeni mumlar gorunur
    assert len(open(yol, "rb").read()) == boyut                # kisa aralik: dosya hemen yazilmaz
    assert veri.bekleyenleri_yaz() == 10 and veri.bekleyenleri_yaz() == 0
    veri._ONBELLEK.clear()
    okunan = veri.csv_oku(yol)                                 # diskten yeniden
    assert len(okunan) == 30 and len(open(yol, "rb").read()) > boyut
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


# ----------------------------------------- uctan uca: sahte Binance ile canli dongu ve komutlar
def _sahte_borsa(monkeypatch, semboller, aralik, n, simdi_i):
    """Zamani ilerletilebilen sahte Binance: klines + time uclari. Bilgisayar saati de buna baglanir."""
    adim = veri.ARALIK_MS[aralik]
    kaynak = {s: veri.sentetik(s, n, aralik) for s in semboller}
    saat = {"ms": int(kaynak[semboller[0]].ts[simdi_i])}

    def sahte(url, zaman_asimi=20.0):
        from urllib.parse import parse_qs, urlparse
        u = urlparse(url)
        if u.path.endswith("/time"):
            return {"serverTime": saat["ms"]}
        q = parse_qs(u.query)
        b = kaynak[q["symbol"][0]]
        istenen = veri.ARALIK_MS[q["interval"][0]]
        if istenen != adim:                                    # baska aralik: taban mumlardan topla
            b = veri.topla(b.kes(son_ts=saat["ms"]), adim, istenen)
        bas = int(q["startTime"][0])
        m = (b.ts >= bas) & (b.ts <= saat["ms"])               # son satir kapanmamis mum olabilir
        i = np.flatnonzero(m)[: int(q["limit"][0])]
        return [[int(b.ts[j])] + [repr(float(x[j])) for x in (b.o, b.h, b.l, b.c, b.v)]
                + [int(b.ts[j]) + istenen - 1] for j in i]

    monkeypatch.setattr(veri, "_http_json", sahte)
    monkeypatch.setattr(veri.time, "sleep", lambda s: None)
    monkeypatch.setattr(veri.time, "time", lambda: saat["ms"] / 1000.0)
    monkeypatch.setitem(veri._SAAT, "okundu", 0.0)
    monkeypatch.setitem(veri._SAAT, "fark", 0)
    return kaynak, saat, adim


def test_uctan_uca_canli_dongu_sahte_binance(tmp_path, monkeypatch):
    semboller = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    a = _ayar(tmp_path, semboller=semboller, aralik="4h", gecmis_gun=400, canli_geri_gun=20,
              veri=str(tmp_path / "data"), komisyon_bps=5.0, kayma_bps=2.0)
    kaynak, saat, adim = _sahte_borsa(monkeypatch, semboller, "4h", 4000, 3000)
    saat["ms"] += 1000                                         # mumun 1. saniyesi: onceki mum yeni kapandi
    d1, _ = canli.tur(a, sessiz=True)
    b = veri.csv_oku(veri.csv_yolu("BTCUSDT", "4h", a["veri"]))
    assert len(b) == 400 * 6 and int(b.ts[-1]) + adim <= saat["ms"]     # kapanmamis mum yok
    assert d1["bar_sayisi"] == 20 * 6 + 1 and d1["not"] == ""
    toplam = 0
    for _ in range(40):                                        # 40 yeni mum = ~1 hafta
        saat["ms"] += adim
        d, n = canli.tur(a, sessiz=True)
        toplam += n
    b2 = veri.csv_oku(veri.csv_yolu("BTCUSDT", "4h", a["veri"]))
    assert len(b2) == len(b) + 40 and np.all(np.diff(b2.ts) == adim)
    np.testing.assert_array_equal(b2.c, kaynak["BTCUSDT"].kes(int(b2.ts[0]), int(b2.ts[-1])).c)
    assert d["bar_sayisi"] == d1["bar_sayisi"] + 40
    satirlar = [json.loads(x) for x in open(tmp_path / "out" / "4h" / "sinyaller.jsonl", encoding="utf-8")]
    assert toplam == len(satirlar) > 0
    anahtarlar = [(o["ts"], o["strateji"], o["sembol"], o["yon"]) for o in satirlar]
    assert len(anahtarlar) == len(set(anahtarlar))             # ayni sinyal iki kez iletilmedi
    # dongu basta bugune kadar tek seferde oynatilsaydi ayni sonuc cikardi (cokme/yeniden baslatma guvenli)
    k = canli.kayit_oku(a)
    p = veri.kirp(veri.piyasa_yukle(semboller, "4h", a["veri"]), k["baslangic_ts"])
    tek = Motor(p, stratejiler.hepsi(a), a).kos(p.k_bul(k["baslangic_ts"]))
    assert {r["ad"]: r["ozsermaye"] for r in d["tablo"]} == \
        pytest.approx({ad: h.son_oz for ad, h in tek.hesaplar.items()})


def test_komutlar_sahte_binance(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    from fusion import cli
    semboller = ["BTCUSDT", "ETHUSDT"]
    a = _ayar(tmp_path, semboller=semboller, aralik="1h", gecmis_gun=200, backtest_gun=60,
              veri=str(tmp_path / "data"))
    _sahte_borsa(monkeypatch, semboller, "1h", 8000, 6000)
    assert cli.k_veri(a, SimpleNamespace()) == 0
    assert cli.k_kontrol(a, SimpleNamespace()) == 0
    assert cli.k_backtest(a, SimpleNamespace(gun=0, panel=False)) == 0
    assert cli.k_durum(a, SimpleNamespace()) == 0
    cikti = capsys.readouterr().out
    assert "4800 mum" in cikti and "fuzyon" in cikti and "maliyet öncesi" in cikti
    d = json.load(open(tmp_path / "out" / "1h" / "durum_backtest.json", encoding="utf-8"))
    assert d["aralik"] == "1h" and d["bar_sayisi"] == 60 * 24 + 1 and len(d["tablo"]) == 9


# ----------------------------------------------------- kisa araliklar / scalp (12 Kas, 3. tur)
def test_10m_mumlar_5m_den_toplanir():
    b = veri.sentetik("X", 101, "5m")
    t = veri.topla(b, 300_000, 600_000)
    assert len(t) == 50 and np.all(t.ts % 600_000 == 0) and np.all(np.diff(t.ts) == 600_000)
    assert t.o[0] == b.o[0] and t.c[0] == b.c[1] and t.h[0] == max(b.h[0], b.h[1]) and t.l[0] == min(b.l[0], b.l[1])
    assert t.v.sum() == pytest.approx(b.v[:100].sum())
    yarim = veri.topla(b.kes(son_ts=int(b.ts[2])), 300_000, 600_000)     # 3 kucuk mum: 2. grup acik
    assert len(yarim) == 1


def test_araliga_gore_on_ayarlar(tmp_path, monkeypatch):
    monkeypatch.setattr(ayar_m, "ayar_yolu", lambda: str(tmp_path / "fuzyon_ayar.json"))
    a = ayar_m.yukle()
    assert a["aralik"] == "4h" and a["gecmis_gun"] == 1500
    ayar_m.aralik_uygula(a, "1m")
    assert (a["gecmis_gun"], a["backtest_gun"], a["canli_geri_gun"], a["dd_kilit_gun"]) == (30, 10, 1, 1)
    for ar, o in ayar_m.ON_AYAR.items():                       # indirme boyutu makul kalsin
        assert ar in veri.ARALIK_MS and o["gecmis_gun"] * 86_400_000 // veri.ARALIK_MS[ar] <= 90_000
        assert o["backtest_gun"] < o["gecmis_gun"]
    ayar_m.aralik_kaydet("5m")
    json.dump({"aralik": "5m", "backtest_gun": 7, "risk_yuzde": 0.5},
              open(tmp_path / "fuzyon_ayar.json", "w"))
    b = ayar_m.yukle()
    assert b["aralik"] == "5m" and b["gecmis_gun"] == 300 and b["backtest_gun"] == 7 and b["risk_yuzde"] == 0.5
    ayar_m.aralik_kaydet("15m")                                 # diger ayarlara dokunmaz
    c = ayar_m.yukle()
    assert c["aralik"] == "15m" and c["backtest_gun"] == 7 and c["risk_yuzde"] == 0.5 and c["gecmis_gun"] == 500
    with pytest.raises(ValueError):
        ayar_m.aralik_kaydet("7m")
    # eski surumun tam ornek dosyasi (gun ayarlari varsayilan degerde) on ayarlari kilitlememeli
    json.dump(dict(ayar_m.VARSAYILAN, aralik="1m"), open(tmp_path / "fuzyon_ayar.json", "w"))
    assert ayar_m.yukle()["gecmis_gun"] == 30


def test_aralik_komutu(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    from fusion import cli
    monkeypatch.setattr(ayar_m, "ayar_yolu", lambda: str(tmp_path / "fuzyon_ayar.json"))
    assert cli.k_aralik(ayar_m.yukle(), SimpleNamespace(deger="")) == 0
    assert cli.k_aralik(ayar_m.yukle(), SimpleNamespace(deger="10m")) == 0
    assert cli.k_aralik(ayar_m.yukle(), SimpleNamespace(deger="abc")) == 1
    cikti = capsys.readouterr().out
    assert "Mum aralığı: 4h" in cikti and "5m mumlardan toplanarak" in cikti and "Uyarı" in cikti
    assert ayar_m.yukle()["aralik"] == "10m"


def test_canli_1m_adim_adim_ilerler_ve_10m_calisir(tmp_path, monkeypatch):
    """Kisa aralikta her mumda bastan oynatma yok: ayni Motor nesnesi yalniz yeni mumu isler,
    sonuc tek seferde oynatmayla ayni kalir. 10m (5m'den turetilmis) canli dongusu de calisir."""
    semboller = ["BTCUSDT", "ETHUSDT"]
    for aralik, n, simdi_i, adim_carpan in (("1m", 9000, 8000, 1), ("10m", 9000, 8000, 2)):
        kok = tmp_path / aralik
        a = _ayar(kok, semboller=semboller, veri=str(kok / "data"), komisyon_bps=5.0, kayma_bps=2.0)
        ayar_m.aralik_uygula(a, aralik)
        a.update(gecmis_gun=5 if aralik == "1m" else 25, canli_geri_gun=1)
        taban = veri.TUREV.get(aralik, aralik)
        kaynak, saat, taban_adim = _sahte_borsa(monkeypatch, semboller, taban, n, simdi_i)
        saat["ms"] += 1000
        d1, _ = canli.tur(a, sessiz=True)
        motor = canli._OTURUM[canli._kayit_yolu(a)]["motor"]
        for _ in range(30):
            saat["ms"] += taban_adim * adim_carpan
            d, _ = canli.tur(a, sessiz=True)
            assert canli._OTURUM[canli._kayit_yolu(a)]["motor"] is motor      # yeniden kurulmadi
        assert d["bar_sayisi"] == d1["bar_sayisi"] + 30 and d["aralik"] == aralik
        assert d["maliyet_r"] is not None and d["maliyet_r"] > 0
        k = canli.kayit_oku(a)
        p = veri.kirp(veri.piyasa_yukle(semboller, aralik, a["veri"]), k["baslangic_ts"])
        assert np.all(np.diff(p.barlar["BTCUSDT"].ts) == veri.ARALIK_MS[aralik])
        tek = Motor(p, stratejiler.hepsi(a), a).kos(p.k_bul(k["baslangic_ts"]))
        assert {r["ad"]: r["ozsermaye"] for r in d["tablo"]} == \
            pytest.approx({ad: h.son_oz for ad, h in tek.hesaplar.items()})
        assert sum(r["islem"] for r in d["tablo"]) == sum(len(h.islemler) for h in tek.hesaplar.values())


def test_islenmis_gecmis_degisirse_bastan_oynatir(tmp_path):
    a, p = _arena(tmp_path, n=3000, canli_geri_gun=5)
    son = int(p.T[-1])
    p1 = Piyasa({s: b.kes(son_ts=son - 2 * ADIM) for s, b in p.barlar.items()}, "15m")
    canli.tur(a, simdi_ms=son, piyasa=p1, sessiz=True)
    motor = canli._OTURUM[canli._kayit_yolu(a)]["motor"]
    # islenmis bolgede bir sembolun mumu sonradan geliyor/eksiliyor -> prefix ayni degil
    eksik = dict(p.barlar)
    b = eksik["ETHUSDT"]
    m = np.ones(len(b), dtype=bool)
    m[-50] = False
    eksik["ETHUSDT"] = Bars(b.ts[m], b.o[m], b.h[m], b.l[m], b.c[m], b.v[m])
    d, _ = canli.tur(a, simdi_ms=son + ADIM, piyasa=Piyasa(eksik, "15m"), sessiz=True)
    assert canli._OTURUM[canli._kayit_yolu(a)]["motor"] is not motor
    assert d["bar_sayisi"] == 5 * 96 + 1 + 2          # baslangic sabit; 2 yeni mum


def test_sezon_siniri(tmp_path):
    a, p = _arena(tmp_path, n=3000, canli_geri_gun=2, canli_max_bar=200)
    son = int(p.T[-1])
    p1 = Piyasa({s: b.kes(son_ts=son - 20 * ADIM) for s, b in p.barlar.items()}, "15m")
    d1, _ = canli.tur(a, simdi_ms=son - 19 * ADIM, piyasa=p1, sessiz=True)
    assert d1["bar_sayisi"] == 2 * 96 + 1 and d1["sezon"] == 1
    d2, _ = canli.tur(a, simdi_ms=son + ADIM, piyasa=p, sessiz=True)       # 213 mum > 200
    assert d2["sezon"] == 2 and d2["bar_sayisi"] == 2 * 96 + 1
    assert (tmp_path / "out" / "4h" / "sezon_001.json").exists()
    assert all(r["islem"] <= d1["tablo"][0]["islem"] + 400 for r in d2["tablo"])


def test_csv_onbellegi_dosya_degisince_yenilenir(tmp_path):
    b = veri.sentetik("X", 40)
    yol = str(tmp_path / "X_15m.csv")
    veri.csv_yaz(yol, b.kes(son_ts=int(b.ts[19])))
    ilk = veri.csv_oku(yol)
    assert veri.csv_oku(yol) is ilk and len(ilk) == 20           # ayni nesne: yeniden okunmadi
    veri.csv_ekle(yol, b.kes(bas_ts=int(b.ts[20])))
    assert len(veri.csv_oku(yol)) == 40                          # dosya buyudu: yeniden okundu


# ------------------------------------------------ servis, panel v2, Telegram, bulut (12 Kas, 4. tur)
def _servis_kur(tmp_path, monkeypatch, semboller, araliklar, n=9000, simdi_i=8000, taban="1m"):
    """Sahte borsaya bagli, yalniz verilen araliklari acik bir Servis."""
    from fusion import servis as servis_m
    monkeypatch.setattr(iletim, "KOK", str(tmp_path))                 # .env gecici klasorde
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    a = _ayar(tmp_path, semboller=semboller, veri=str(tmp_path / "data"), komisyon_bps=5.0, kayma_bps=2.0)
    a["_sabit"] = ["gecmis_gun", "backtest_gun", "canli_geri_gun"]
    a.update(gecmis_gun=4, backtest_gun=1, canli_geri_gun=1)
    kaynak, saat, adim = _sahte_borsa(monkeypatch, semboller, taban, n, simdi_i)
    saat["ms"] += 1000
    s = servis_m.Servis(a)
    s.ayarlar.update(aktif=list(araliklar), bildirim=[araliklar[0]])
    return s, a, saat, adim


def _bosalt(s, en_fazla=400):
    n = 0
    while s.adim():
        n += 1
        assert n < en_fazla, "servis isi bitmiyor"
    return n


def test_servis_birden_cok_araligi_birlikte_calistirir(tmp_path, monkeypatch):
    semboller = ["BTCUSDT", "ETHUSDT"]
    s, a, saat, adim = _servis_kur(tmp_path, monkeypatch, semboller, ["1m", "5m"])
    _bosalt(s)
    o = {x["aralik"]: x for x in s.ozet()["araliklar"]}
    assert o["1m"]["asama"] == "calisiyor" and o["5m"]["asama"] == "calisiyor" and o["15m"]["asama"] == "kapali"
    assert o["1m"]["hazir"] and o["1m"]["mum"] == 1441 and o["5m"]["mum"] == 289
    for ar in ("1m", "5m"):                                    # araliklar ayri klasorlere yazar
        for dosya in ("canli.json", "durum_canli.json", "durum_backtest.json"):
            assert (tmp_path / "out" / ar / dosya).exists(), (ar, dosya)
        assert o[ar]["backtest"]["asama"] == "hazir"            # hazir olunca backtest kendiliginden
    assert not s.adim()                                        # yeni mum yokken is yok
    saat["ms"] += 60_000                                       # 1 dakika: yalniz 1m vadesi gelir
    assert _bosalt(s) == 1
    o2 = {x["aralik"]: x for x in s.ozet()["araliklar"]}
    assert o2["1m"]["mum"] == 1442 and o2["5m"]["mum"] == 289
    saat["ms"] += 4 * 60_000                                   # 5. dakika: ikisi de
    _bosalt(s)
    o3 = {x["aralik"]: x for x in s.ozet()["araliklar"]}
    assert o3["1m"]["mum"] == 1446 and o3["5m"]["mum"] == 290
    # panelden ac/kapa kalici
    s.aktif_yap("5m", False)
    s.aktif_yap("15m", True)
    from fusion import servis as servis_m
    assert set(servis_m.Servis(a).ayarlar["aktif"]) == {"1m", "15m"}
    saat["ms"] += 5 * 60_000
    _bosalt(s)
    o4 = {x["aralik"]: x for x in s.ozet()["araliklar"]}
    assert o4["5m"]["asama"] == "kapali" and o4["5m"]["mum"] == 290 and o4["15m"]["asama"] == "calisiyor"


def test_servis_veri_hatasinda_durmaz_ve_yeniden_dener(tmp_path, monkeypatch):
    s, a, saat, adim = _servis_kur(tmp_path, monkeypatch, ["BTCUSDT"], ["1m"])
    asil = veri._http_json

    def bozuk(url, zaman_asimi=20.0):
        raise OSError("internet yok")

    monkeypatch.setattr(veri, "_http_json", bozuk)
    assert s.adim() is True                                    # hazirlik denemesi: hata
    h = s.hal["1m"]
    assert h["asama"] == "hata" and "ulasilamadi" in h["hata"] and not h["hazir"]
    assert s.adim() is False                                   # bekleme suresi dolmadan yeniden denemez
    monkeypatch.setattr(veri, "_http_json", asil)
    saat["ms"] += 61_000
    _bosalt(s)
    assert s.hal["1m"]["hazir"] and s.hal["1m"]["asama"] == "calisiyor" and s.hal["1m"]["hata"] == ""


def test_eski_cikti_duzeni_tasinir(tmp_path):
    a = _ayar(tmp_path)
    kok = tmp_path / "out"
    kok.mkdir()
    (kok / "canli.json").write_text(json.dumps({"baslangic_ts": 1, "son_iletilen_ts": 2, "aralik": "4h",
                                                 "semboller": a["semboller"]}))
    (kok / "durum_canli.json").write_text(json.dumps({"aralik": "4h"}))
    (kok / "durum_backtest.json").write_text(json.dumps({"aralik": "15m"}))
    (kok / "islemler_backtest.csv").write_text("x")
    tasinan = ayar_m.eski_duzeni_tasi(a)
    assert len(tasinan) == 4
    assert json.loads((kok / "4h" / "canli.json").read_text())["baslangic_ts"] == 1
    assert (kok / "4h" / "durum_canli.json").exists() and (kok / "15m" / "durum_backtest.json").exists()
    assert (kok / "15m" / "islemler_backtest.csv").exists() and not (kok / "canli.json").exists()
    assert ayar_m.eski_duzeni_tasi(a) == []


def _sahte_telegram(monkeypatch):
    kayit = {"gonderilen": [], "guncellemeler": []}

    def tg(token, metod, zaman_asimi=15.0, **p):
        if token != "123:GECERLI":
            raise RuntimeError(f"Telegram {metod}: HTTP 401")
        if metod == "getMe":
            return {"username": "deneme_bot"}
        if metod == "sendMessage":
            kayit["gonderilen"].append((str(p["chat_id"]), p["text"]))
            return {}
        if metod == "getUpdates":
            ofset = p.get("offset") or 0
            return [g for g in kayit["guncellemeler"] if g["update_id"] >= ofset]
        raise AssertionError(metod)

    monkeypatch.setattr(iletim, "tg", tg)
    return kayit


def test_telegram_baglama_akisi_ve_komutlar(tmp_path, monkeypatch):
    s, a, saat, adim = _servis_kur(tmp_path, monkeypatch, ["BTCUSDT", "ETHUSDT"], ["1m"])
    tgk = _sahte_telegram(monkeypatch)
    (tmp_path / ".env").write_text("BASKA_AYAR=1\n")
    assert s.telegram_durumu()["durum"] == "yok"
    with pytest.raises(RuntimeError):
        s.telegram_token("999:YANLIS")
    with pytest.raises(ValueError):
        s.telegram_token("bosluklu token")
    assert s.telegram_token(" 123:GECERLI ")["durum"] == "mesaj_bekleniyor"
    with pytest.raises(ValueError):
        s.telegram_onayla()                                    # henuz mesaj yok
    s.telegram_guncelleme({"update_id": 1, "message": {"chat": {"id": 555, "type": "private", "first_name": "Burak"}, "text": "selam"}})
    d = s.telegram_durumu()
    assert d["durum"] == "aday" and d["aday"] == "Burak" and not tgk["gonderilen"]
    assert s.telegram_onayla()["durum"] == "bagli"
    env = (tmp_path / ".env").read_text()
    assert "BASKA_AYAR=1" in env and "TELEGRAM_BOT_TOKEN=123:GECERLI" in env and "TELEGRAM_CHAT_ID=555" in env
    assert tgk["gonderilen"][-1][0] == "555" and "bağlandı" in tgk["gonderilen"][-1][1]
    assert "GECERLI" not in json.dumps(s.ozet())                # token panele asla donmez
    # sinyal bildirimi: yalniz bildirimi acik aralik
    _bosalt(s)
    once = len(tgk["gonderilen"])
    for _ in range(40):
        saat["ms"] += 60_000
        _bosalt(s)
    sinyal = [m for c, m in tgk["gonderilen"][once:] if m.startswith("Füzyon 1m (kâğıt)")]
    assert len(sinyal) == sum(1 for _ in open(tmp_path / "out" / "1m" / "sinyaller.jsonl", encoding="utf-8")) > 0 \
        or len(sinyal) > 0
    s.bildirim_yap("1m", False)
    once = len(tgk["gonderilen"])
    for _ in range(20):
        saat["ms"] += 60_000
        _bosalt(s)
    assert len(tgk["gonderilen"]) == once                      # bildirim kapaliyken mesaj yok
    # komutlar: yalniz bagli sohbet yanit alir
    s.telegram_guncelleme({"update_id": 2, "message": {"chat": {"id": 999, "type": "private"}, "text": "/durum 1m"}})
    assert len(tgk["gonderilen"]) == once
    s.telegram_guncelleme({"update_id": 3, "message": {"chat": {"id": 555, "type": "private"}, "text": "/durum 1m"}})
    assert tgk["gonderilen"][-1][1].startswith("Füzyon 1m · kâğıt") and "1. " in tgk["gonderilen"][-1][1]
    assert "henüz sonuç yok" in s.komut_yaniti("/durum 4h") and "komutları" in s.komut_yaniti("merhaba")
    assert "1m: calisiyor" in s.komut_yaniti("/araliklar")
    assert s.telegram_kaldir()["durum"] == "yok" and "TELEGRAM" not in (tmp_path / ".env").read_text()


def test_panel_yonetim_api_guvenligi(tmp_path, monkeypatch):
    import threading
    import urllib.error
    import urllib.request
    from fusion import panel
    s, a, saat, adim = _servis_kur(tmp_path, monkeypatch, ["BTCUSDT"], ["1m"])
    a["panel_port"] = 0
    sunucu = panel.sunucu(a, s)
    threading.Thread(target=sunucu.serve_forever, daemon=True).start()
    kok = f"http://127.0.0.1:{sunucu.server_address[1]}"

    def post(yol, govde, basliklar=None):
        h = {"Content-Type": "application/json", "X-Fuzyon": "1"}
        h.update(basliklar or {})
        h = {k_: v for k_, v in h.items() if v is not None}
        istek = urllib.request.Request(kok + yol, data=json.dumps(govde).encode(), headers=h)
        try:
            with urllib.request.urlopen(istek) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    try:
        o = json.load(urllib.request.urlopen(kok + "/api/servis"))
        assert len(o["araliklar"]) == 10 and o["telegram"]["durum"] == "yok" and "salt" not in o
        assert post("/api/aralik", {"aralik": "5m", "aktif": True}) == (200, {"tamam": True})
        assert "5m" in s.ayarlar["aktif"]
        # ozel baslik yoksa (baska bir sitenin form gonderimi gibi) ya da Host farkliysa reddedilir
        assert post("/api/aralik", {"aralik": "5m", "aktif": False}, {"X-Fuzyon": None})[0] == 403
        assert post("/api/aralik", {"aralik": "5m", "aktif": False}, {"Host": "kotu.example"})[0] == 403
        assert "5m" in s.ayarlar["aktif"]
        assert post("/api/aralik", {"aralik": "7m", "aktif": True})[0] == 400
        assert post("/api/takip", {"takip": "olmayan"})[0] == 400
        assert post("/api/takip", {"takip": "fuzyon"})[0] == 200 and s.ayarlar["takip"] == "fuzyon"
        assert post("/api/telegram", {"islem": "token", "token": "x"})[0] == 400
        assert post("/api/backtest", {"aralik": "1m"})[0] == 200 and s.kuyruk.qsize() == 1
        istek = urllib.request.Request(kok + "/api/servis", headers={"Host": "kotu.example"})
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(istek)
        assert post("/api/durdur", {})[0] == 200 and s.dur.is_set()
    finally:
        sunucu.shutdown()
        sunucu.server_close()


def test_bulut_komutu_tek_tur_atar(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace
    from fusion import cli
    s, a, saat, adim = _servis_kur(tmp_path, monkeypatch, ["BTCUSDT", "ETHUSDT"], ["1m"])
    tgk = _sahte_telegram(monkeypatch)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:GECERLI")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "555")
    assert cli.k_bulut(a, SimpleNamespace(araliklar="1m,5m")) == 0
    assert (tmp_path / "out" / "1m" / "canli.json").exists() and (tmp_path / "out" / "5m" / "canli.json").exists()
    tgk["guncellemeler"].append({"update_id": 7, "message": {"chat": {"id": 555, "type": "private"}, "text": "/durum 5m"}})
    saat["ms"] += 5 * 60_000
    assert cli.k_bulut(a, SimpleNamespace(araliklar="1m,5m")) == 0
    assert tgk["gonderilen"][-1][1].startswith("Füzyon 5m · kâğıt")
    n = len(tgk["gonderilen"])
    assert cli.k_bulut(a, SimpleNamespace(araliklar="1m,5m")) == 0     # ayni komut ikinci kez yanitlanmaz
    assert len([m for c, m in tgk["gonderilen"][n:] if "· kâğıt ·" in m]) == 0
    cikti = capsys.readouterr().out
    assert "1m: 1441 mum" in cikti and "5m: 289 mum" in cikti
    assert cli.k_bulut(a, SimpleNamespace(araliklar="7m")) == 1


def test_kisa_aralikta_dosya_her_mumda_yazilmaz(tmp_path, monkeypatch):
    """1m canli dongude CSV her dakika degil, 60 mumda bir (ya da 30 dakikada bir) yazilir;
    bellekteki veri eksiksizdir ve surec kapanirken kalan mumlar yazilir."""
    semboller = ["BTCUSDT"]
    a = _ayar(tmp_path, semboller=semboller, veri=str(tmp_path / "data"))
    ayar_m.aralik_uygula(a, "1m")
    a.update(gecmis_gun=2, canli_geri_gun=1)
    kaynak, saat, adim = _sahte_borsa(monkeypatch, semboller, "1m", 6000, 4000)
    saat["ms"] += 1000
    veri._ONBELLEK.clear()
    canli.tur(a, sessiz=True)
    yol = veri.csv_yolu("BTCUSDT", "1m", a["veri"])
    yazim = []
    asil = veri.csv_ekle
    monkeypatch.setattr(veri, "csv_ekle", lambda y, b: (yazim.append(len(b)), asil(y, b))[1])
    for _ in range(100):
        saat["ms"] += 60_000
        d, _n = canli.tur(a, sessiz=True)
    assert len(veri.csv_oku(yol)) == 2880 + 100                # bellekte hepsi var
    yazilan = sum(yazim)
    assert 2 <= len(yazim) <= 5 and yazilan < 100              # 100 mumda birkac yazim; sonuncular bekliyor
    assert veri.bekleyenleri_yaz() == 100 - yazilan
    veri._ONBELLEK.clear()
    b = veri.csv_oku(yol)
    assert len(b) == 2980 and np.all(np.diff(b.ts) == 60_000)


def test_internet_yokken_saat_sorgusu_her_cagrida_tekrarlanmaz(monkeypatch):
    sayac = {"n": 0}

    def bozuk(url, zaman_asimi=20.0):
        sayac["n"] += 1
        raise OSError("yok")

    monkeypatch.setattr(veri, "_http_json", bozuk)
    monkeypatch.setitem(veri._SAAT, "okundu", 0.0)
    monkeypatch.setitem(veri._SAAT, "fark", 0)
    for _ in range(5):
        veri.simdi_ms()
    assert sayac["n"] == len(veri.SUNUCULAR)                   # yalniz ilk cagrida denendi
