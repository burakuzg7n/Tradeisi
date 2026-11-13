"""Strateji kaydi. Fuzyon oylamasi her zaman en sonda calisir."""
from ..kural import kurallari_yukle
from .donus import OrtalamayaDonus
from .kirilim import Kirilim
from .kurul import AjanKurulu
from .oylama import FuzyonOylama
from .qajan import QAjan
from .rotasyon import OranRotasyon
from .twin_range import TwinRange


def hepsi(ayar: dict, kural_klasoru: str | None = None) -> list:
    liste = [Kirilim(), OrtalamayaDonus(), OranRotasyon(), AjanKurulu(), QAjan(), TwinRange()]
    liste += kurallari_yukle(kural_klasoru)
    secim = ayar.get("stratejiler", "hepsi")
    if isinstance(secim, list) and secim:
        liste = [s for s in liste if s.ad in secim]
    liste.append(FuzyonOylama())
    return liste
