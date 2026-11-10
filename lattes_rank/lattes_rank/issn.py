"""Normalização e validação de ISSN.

O Lattes e o SCImago trazem o ISSN sem hífen (ex.: 03777332). Aqui o formato
canônico é sempre 8 caracteres, maiúsculos, sem hífen.
"""

from __future__ import annotations

import re

_RE_ISSN = re.compile(r"^\d{7}[\dX]$")


def normalizar_issn(valor: object) -> str | None:
    """Remove hífen/espaços e põe em maiúsculas. Não tenta "consertar" o valor."""
    if valor is None:
        return None
    texto = re.sub(r"[^0-9Xx]", "", str(valor)).upper()
    return texto or None


def formato_valido(issn: str | None) -> bool:
    """True se tem 7 dígitos + (dígito ou X)."""
    return bool(issn) and _RE_ISSN.match(issn) is not None


def digito_verificador_ok(issn: str | None) -> bool:
    """Confere o dígito verificador (módulo 11, pesos 8 a 2)."""
    if not formato_valido(issn):
        return False
    soma = sum(int(c) * peso for c, peso in zip(issn[:7], range(8, 1, -1)))
    esperado = (11 - soma % 11) % 11
    esperado_char = "X" if esperado == 10 else str(esperado)
    return issn[7] == esperado_char
