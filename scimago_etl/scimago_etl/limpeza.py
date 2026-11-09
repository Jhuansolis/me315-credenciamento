"""Limpeza e normalização das linhas lidas dos CSVs.

Casos tratados (todos observados nos dados reais):
  1. Decimal com vírgula ("8,997") e campos numéricos vazios.
  2. SJR vazio e "SJR Best Quartile" = "-" (periódico sem métrica no ano).
  3. Vários ISSN por célula ("15424863, 00079235"), dígito verificador "X",
     zeros à esquerda; ISSN ausente ("-" ou vazio).
  4. O mesmo periódico aparece em vários arquivos de área no mesmo ano
     (ex.: um periódico de CS e de Medicina) -> deduplicar por (sourceid, ano).
  5. Categorias com quartil por categoria "Nome (Q1)", categorias sem quartil
     quando não há SJR, e nomes que já têm parênteses: "Medicine (miscellaneous) (Q1)".
  6. Título com sufixo "(discontinued)".
  7. Cobertura com lacunas: "2014-2016, 2018-2026".
  8. Open Access "Yes"/"No".
  9. "SJR Best Quartile" e "Rank" são RELATIVOS À ÁREA DO ARQUIVO: o mesmo
     periódico aparece Q3 no arquivo de Bioquímica e Q2 no de Ciências
     Ambientais. O melhor quartil global é recalculado a partir de todas as
     categorias; o valor por área vai para periodico_area_ano.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .config import COLUNAS_DECIMAIS, COLUNAS_INTEIRAS

_RE_ISSN = re.compile(r"^[0-9]{7}[0-9X]$")
_RE_CATEGORIA = re.compile(r"^(?P<nome>.+?)\s*\((?P<q>Q[1-4])\)$")


# ---------------------------------------------------------------- valores simples
def para_decimal(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.replace(",", ".", regex=False).replace({"": None, "-": None}), errors="coerce")


def para_inteiro(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.replace({"": None, "-": None}), errors="coerce").astype("Int64")


def para_bool(s: pd.Series) -> pd.Series:
    return s.str.lower().map({"yes": 1, "no": 0}).astype("Int64")


def normalizar_issn(valor: str) -> list[str]:
    """'2157846x, 0007-9235' -> ['2157846X', '00079235']. Inválidos são descartados."""
    saida = []
    for parte in re.split(r"[,;\s]+", valor or ""):
        p = parte.replace("-", "").upper()
        if _RE_ISSN.match(p) and p not in saida:
            saida.append(p)
    return saida


def formatar_issn(issn8: str) -> str:
    return f"{issn8[:4]}-{issn8[4:]}"


def separar_categorias(texto: str) -> list[tuple[str, str | None]]:
    """'Medicine (miscellaneous) (Q1); Genetics' -> [('Medicine (miscellaneous)', 'Q1'), ('Genetics', None)]."""
    itens = []
    for parte in (texto or "").split(";"):
        parte = parte.strip()
        if not parte:
            continue
        m = _RE_CATEGORIA.match(parte)
        itens.append((m.group("nome").strip(), m.group("q")) if m else (parte, None))
    return itens


def separar_areas(texto: str) -> list[str]:
    return [a.strip() for a in (texto or "").split(";") if a.strip()]


def faixa_cobertura(texto: str) -> tuple[int | None, int | None]:
    anos = [int(a) for a in re.findall(r"\d{4}", texto or "")]
    return (min(anos), max(anos)) if anos else (None, None)


# ---------------------------------------------------------------- tabela inteira
def limpar(bruto: pd.DataFrame) -> pd.DataFrame:
    df = bruto.copy()
    for c in COLUNAS_DECIMAIS:
        df[c] = para_decimal(df[c])
    for c in COLUNAS_INTEIRAS:
        df[c] = para_inteiro(df[c])
    for c in ("open_access", "open_access_diamond"):
        df[c] = para_bool(df[c])

    df["quartil_melhor"] = df["quartil_melhor"].where(df["quartil_melhor"].str.match(r"^Q[1-4]$"), None)
    df["tipo"] = df["tipo"].str.lower()
    df["descontinuado"] = df["titulo"].str.contains(r"\(discontinued\)", case=False).astype(int)
    df["titulo_limpo"] = df["titulo"].str.replace(r"\s*\(discontinued\)\s*$", "", case=False, regex=True)
    cob = df["cobertura"].map(faixa_cobertura)
    df["cobertura_inicio"] = cob.map(lambda t: t[0]).astype("Int64")
    df["cobertura_fim"] = cob.map(lambda t: t[1]).astype("Int64")
    df["issns"] = df["issn_bruto"].map(normalizar_issn)
    return df


def deduplicar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Uma linha por (sourceid, ano). Devolve (tabela_unica, inconsistencias).

    O mesmo periódico em arquivos de áreas diferentes deveria ter valores
    idênticos; qualquer diferença é registrada para o relatório.
    """
    # quartil_melhor e rank_area NÃO entram: variam por área por definição (caso 9).
    campos = ["titulo", "sjr", "h_index", "total_docs_ano", "categorias_bruto", "issn_bruto", "areas_bruto"]
    g = df.groupby(["sourceid", "ano"])
    n_distintos = g[campos].nunique(dropna=False)
    inconsist = n_distintos[(n_distintos > 1).any(axis=1)].reset_index()
    unica = df.sort_values(["ano", "sourceid", "area_arquivo"]).drop_duplicates(["sourceid", "ano"], keep="first")
    unica = unica.copy()
    unica["quartil_melhor"] = unica["categorias_bruto"].map(melhor_quartil_global)
    return unica.reset_index(drop=True), inconsist


def melhor_quartil_global(texto: str) -> str | None:
    qs = [q for _, q in separar_categorias(texto) if q]
    return min(qs) if qs else None   # 'Q1' < 'Q2' < ... em ordem de texto


def explodir_categorias(unica: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for sid, ano, sjr, texto in unica[["sourceid", "ano", "sjr", "categorias_bruto"]].itertuples(index=False):
        for nome, q in separar_categorias(texto):
            linhas.append((sid, ano, nome, q, sjr))
    cat = pd.DataFrame(linhas, columns=["sourceid", "ano", "categoria", "quartil_scimago", "sjr"])
    # Uma categoria repetida para o mesmo periódico/ano (não observado, mas barato prevenir).
    return cat.drop_duplicates(["sourceid", "ano", "categoria"]).reset_index(drop=True)


def explodir_areas(unica: pd.DataFrame, bruto: pd.DataFrame) -> pd.DataFrame:
    """Áreas de cada periódico/ano, a partir da coluna "Areas" (inclui áreas cujos
    arquivos não foram carregados). O rank na área só existe se o arquivo dela foi lido."""
    linhas = [(sid, ano, a) for sid, ano, txt in unica[["sourceid", "ano", "areas_bruto"]].itertuples(index=False)
              for a in separar_areas(txt)]
    areas = pd.DataFrame(linhas, columns=["sourceid", "ano", "area"]).drop_duplicates()
    rank = bruto[["sourceid", "ano", "area_arquivo", "rank_area", "quartil_melhor"]].rename(
        columns={"area_arquivo": "area", "quartil_melhor": "quartil_melhor_na_area"})
    return areas.merge(rank, on=["sourceid", "ano", "area"], how="left")


def explodir_issn(unica: pd.DataFrame) -> pd.DataFrame:
    e = unica[["sourceid", "ano", "issns"]].explode("issns").dropna(subset=["issns"])
    return e.rename(columns={"issns": "issn"}).reset_index(drop=True)


def quartil_por_posicao(posicao: pd.Series, n: pd.Series) -> pd.Series:
    """Quartil recalculado só para checagem de qualidade (Q1 = primeiros 25%)."""
    q = np.ceil(4 * posicao / n).clip(1, 4)
    return ("Q" + q.astype("Int64").astype(str)).where(posicao.notna())
