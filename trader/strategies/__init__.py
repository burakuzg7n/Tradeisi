"""Strateji kayit defteri.

`sepet_momentum`  -> arastirma adayi (protokol kapilarina tabi)
`sistem_testi`    -> SADECE altyapi dogrulama; canli/testnet kapisi KAPALI
"""
from __future__ import annotations

from ..strategy import Strategy

_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    _REGISTRY[cls.name] = cls
    return cls


def build(name: str, **kwargs) -> Strategy:
    if name not in _REGISTRY:
        raise KeyError(f"Bilinmeyen strateji: {name}. Secenekler: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**kwargs)


def available() -> list[str]:
    return sorted(_REGISTRY)


from .basket_momentum import BasketMomentum  # noqa: E402
from .system_test import SystemTest  # noqa: E402

register(BasketMomentum)
register(SystemTest)
