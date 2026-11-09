"""Percentil do periódico dentro de cada categoria SCImago, por ano.

Universo de comparação: todos os periódicos com SJR no ano que pertencem à
categoria, juntando os 27 arquivos de área. Só entram fontes do tipo presente
nos CSVs (periódicos); o SCImago ranqueia também anais e séries de livros em
algumas categorias, por isso nossos quartis podem diferir dos oficiais
(ver DECISOES.md, decisão D3).

Posição: ordem decrescente de SJR. Empates (ver DECISOES.md, decisão D2):
  - "melhor" (padrão): todos os empatados recebem a melhor posição do bloco
                       (benefício da dúvida ao docente).
  - "media":           posição média do bloco (padrão estatístico). Útil para
                       análise de sensibilidade no relatório.

Métodos de percentil:
  - "topo_100" (padrão): 100 * (n - posicao + 1) / n   -> 1º lugar = 100, último = 100/n
  - "linear_0_100":      100 * (n - posicao) / (n - 1) -> 1º lugar = 100, último = 0
"""

from __future__ import annotations

import pandas as pd

METODOS = ("topo_100", "linear_0_100")
EMPATES = {"melhor": "min", "media": "average"}


def calcular(cat: pd.DataFrame, metodo: str = "topo_100", empates: str = "melhor") -> pd.DataFrame:
    """Recebe linhas (sourceid, ano, categoria, sjr, ...) e acrescenta
    posicao, n_categoria, n_empatados e percentil. Periódicos sem SJR ficam com NULL."""
    if metodo not in METODOS:
        raise ValueError(f"metodo deve ser um de {METODOS}")
    if empates not in EMPATES:
        raise ValueError(f"empates deve ser um de {tuple(EMPATES)}")

    out = cat.copy()
    com_sjr = out["sjr"].notna()
    base = out[com_sjr]
    grupo = base.groupby(["ano", "categoria"])["sjr"]

    for c in ("posicao", "n_categoria", "n_empatados"):
        out[c] = pd.Series(pd.NA, index=out.index, dtype="Float64")
    out.loc[com_sjr, "posicao"] = grupo.rank(ascending=False, method=EMPATES[empates])
    out.loc[com_sjr, "n_categoria"] = grupo.transform("size")
    # Quantos periódicos dividem exatamente esse SJR na categoria/ano (1 = sem empate).
    out.loc[com_sjr, "n_empatados"] = base.groupby(["ano", "categoria", "sjr"])["sjr"].transform("size")

    pos, n = out["posicao"], out["n_categoria"]
    if metodo == "topo_100":
        pct = 100 * (n - pos + 1) / n
    else:
        pct = (100 * (n - pos) / (n - 1)).where(n > 1, 100.0)
    out["percentil"] = pct.round(2)
    if empates == "melhor":
        out["posicao"] = out["posicao"].astype("Int64")
    out["n_categoria"] = out["n_categoria"].astype("Int64")
    out["n_empatados"] = out["n_empatados"].astype("Int64")
    return out
