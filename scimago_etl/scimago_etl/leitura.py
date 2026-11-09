"""Descoberta e leitura dos CSVs do SCImago."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import AREAS_SCIMAGO, COLUNAS


def _chave(texto: str) -> str:
    """Só letras minúsculas: 'Biochemistry, Genetics and...' == 'Biochemistry_Genetics_and...'."""
    return re.sub(r"[^a-z]", "", texto.lower())


_AREA_POR_CHAVE = {_chave(a): a for a in AREAS_SCIMAGO}

# Aceita "scimagojr 2022 Subject Area - Chemistry.csv" e variações com "_" no lugar
# de espaços ou prefixos antes de "scimagojr" (ex.: arquivos renomeados por upload).
_RE_NOME = re.compile(
    r"scimagojr\s+(?P<ano>\d{4})\s+subject\s+area\s*-\s*(?P<area>.+?)\s*\.csv$",
    re.IGNORECASE,
)


@dataclass
class ArquivoFonte:
    caminho: Path
    ano: int
    area: str          # nome canônico (como na coluna "Areas")
    area_reconhecida: bool


def identificar_arquivo(caminho: Path) -> ArquivoFonte | None:
    nome = caminho.name.replace("_", " ")
    m = _RE_NOME.search(nome)
    if not m:
        return None
    area_txt = m.group("area")
    canonica = _AREA_POR_CHAVE.get(_chave(area_txt))
    return ArquivoFonte(caminho, int(m.group("ano")), canonica or area_txt, canonica is not None)


def descobrir_arquivos(pasta: str | Path, anos: tuple[int, ...] | None = None) -> list[ArquivoFonte]:
    pasta = Path(pasta)
    arquivos, ignorados = [], []
    for p in sorted(pasta.rglob("*.csv")):
        a = identificar_arquivo(p)
        if a is None:
            ignorados.append(p.name)
            continue
        if anos and a.ano not in anos:
            continue
        arquivos.append(a)
    if ignorados:
        warnings.warn(f"{len(ignorados)} CSV(s) ignorados por nome fora do padrão: {ignorados[:5]}")

    # O mesmo (ano, área) duas vezes na pasta (ex.: cópia "(1)") gera duplicidade silenciosa.
    vistos: dict[tuple[int, str], Path] = {}
    for a in arquivos:
        k = (a.ano, a.area)
        if k in vistos:
            raise ValueError(f"Arquivo duplicado para {k}: {vistos[k].name} e {a.caminho.name}")
        vistos[k] = a.caminho
    return arquivos


def ler_csv(arq: ArquivoFonte) -> pd.DataFrame:
    """Lê um CSV como texto (sem conversões automáticas) e padroniza as colunas.

    Tudo é lido como str para não perder zeros à esquerda (ISSN, Sourceid) e
    porque o separador decimal é vírgula.
    """
    try:
        df = pd.read_csv(arq.caminho, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(arq.caminho, sep=";", dtype=str, keep_default_na=False, encoding="latin-1")

    df.columns = [c.strip() for c in df.columns]

    # "Total Docs. (AAAA)": nome muda por ano; confere se bate com o nome do arquivo.
    col_ano = [c for c in df.columns if re.fullmatch(r"Total Docs\. \(\d{4}\)", c)]
    if len(col_ano) != 1:
        raise ValueError(f"{arq.caminho.name}: coluna 'Total Docs. (AAAA)' não encontrada")
    ano_col = int(re.search(r"\d{4}", col_ano[0]).group())
    if ano_col != arq.ano:
        warnings.warn(f"{arq.caminho.name}: ano no nome ({arq.ano}) != ano na coluna ({ano_col})")
    df = df.rename(columns={col_ano[0]: "total_docs_ano"})

    # A coluna "Publisher" aparece duas vezes (pandas renomeia a 2ª para "Publisher.1").
    if "Publisher.1" in df.columns:
        difere = (df["Publisher"] != df["Publisher.1"]) & (df["Publisher"] == "")
        df.loc[difere, "Publisher"] = df.loc[difere, "Publisher.1"]
        df = df.drop(columns="Publisher.1")

    faltando = set(COLUNAS) - set(df.columns)
    if faltando:
        raise ValueError(f"{arq.caminho.name}: colunas ausentes {sorted(faltando)}")

    df = df.rename(columns=COLUNAS)
    df = df.apply(lambda s: s.str.strip())
    df["ano"] = arq.ano
    df["area_arquivo"] = arq.area
    df["arquivo"] = arq.caminho.name
    return df


def ler_todos(arquivos: list[ArquivoFonte]) -> pd.DataFrame:
    return pd.concat([ler_csv(a) for a in arquivos], ignore_index=True)
