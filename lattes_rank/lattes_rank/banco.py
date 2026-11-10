"""Acesso somente leitura ao SQLite gerado pelo ETL do SCImago (etapa 1).

Usa: ``periodico_issn`` (ISSN -> sourceid), ``periodico`` (título) e a visão
``v_melhor_percentil`` (melhor categoria do periódico em cada ano). A coluna
``n_empatados`` de ``periodico_categoria_ano`` é opcional: no esquema da etapa 1
ela vale 1 quando o periódico NÃO divide o SJR com ninguém (ver
``scimago_etl/DECISOES.md``, D2).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .issn import normalizar_issn

# Objeto -> colunas que esta ferramenta lê. Conferido ao abrir o banco.
_ESQUEMA_ESPERADO: dict[str, tuple[str, ...]] = {
    "periodico_issn": ("issn", "sourceid"),
    "periodico": ("sourceid", "titulo"),
    "v_melhor_percentil": (
        "sourceid", "ano", "categoria_id", "categoria", "percentil", "posicao", "n_categoria", "quartil_scimago",
    ),
}


@dataclass(frozen=True)
class Nota:
    """Melhor percentil de um periódico dentro da janela de anos."""

    percentil: float
    ano: int
    categoria: str
    posicao: float | None  # REAL no banco: inteira com empates="melhor", pode ser x,5 com "media"
    n_categoria: int | None
    quartil_scimago: str | None
    n_empatados: int | None  # quantos dividem o mesmo SJR na categoria/ano (1 = sem empate); None = coluna ausente

    @property
    def empate_sjr(self) -> bool:
        """True se a posição veio de um bloco de SJR empatado (regra D2 da etapa 1)."""
        return self.n_empatados is not None and self.n_empatados > 1


class Banco:
    def __init__(self, caminho: str | Path):
        caminho = Path(caminho)
        if not caminho.is_file():
            raise FileNotFoundError(f"Banco não encontrado: {caminho}")
        # mode=ro: esta ferramenta nunca altera o banco do projeto.
        self._con = sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)
        self._con.row_factory = sqlite3.Row
        try:
            self._conferir_esquema()
            self._tem_empatados = self._colunas("periodico_categoria_ano") >= {
                "sourceid", "ano", "categoria_id", "n_empatados",
            }
        except sqlite3.DatabaseError as erro:
            self._con.close()
            raise ValueError(f"{caminho} não é um banco SQLite válido ({erro}).") from erro
        except ValueError:
            self._con.close()
            raise
        self._indice: dict[str, set[int]] | None = None

    def fechar(self) -> None:
        self._con.close()

    def __enter__(self) -> "Banco":
        return self

    def __exit__(self, *exc) -> None:
        self.fechar()

    # -- verificações ----------------------------------------------------
    def _colunas(self, objeto: str) -> set[str]:
        # PRAGMA table_info funciona para tabelas e visões; objeto inexistente -> vazio.
        return {linha["name"] for linha in self._con.execute(f"PRAGMA table_info({objeto})")}

    def _conferir_esquema(self) -> None:
        problemas = []
        for objeto, colunas in _ESQUEMA_ESPERADO.items():
            existentes = self._colunas(objeto)
            if not existentes:
                problemas.append(f"{objeto} (ausente)")
                continue
            faltando = [c for c in colunas if c not in existentes]
            if faltando:
                problemas.append(f"{objeto} (sem {', '.join(faltando)})")
        if problemas:
            raise ValueError(
                "O banco não tem os objetos esperados: " + "; ".join(problemas)
                + ". Confira se é o banco gerado pelo ETL do SCImago (scimago_etl)."
            )

    # -- consultas -------------------------------------------------------
    def anos_com_percentil(self) -> tuple[int, int]:
        """Menor e maior ano com percentil na base (ex.: 2022 e 2025)."""
        linha = self._con.execute("SELECT MIN(ano) AS a, MAX(ano) AS b FROM v_melhor_percentil").fetchone()
        if linha["a"] is None:
            raise ValueError("v_melhor_percentil está vazia: o banco não tem nenhum percentil.")
        return int(linha["a"]), int(linha["b"])

    def indice_issn(self) -> dict[str, set[int]]:
        """ISSN normalizado -> conjunto de sourceid (carregado uma vez)."""
        if self._indice is None:
            indice: dict[str, set[int]] = {}
            for linha in self._con.execute("SELECT issn, sourceid FROM periodico_issn"):
                chave = normalizar_issn(linha["issn"])
                if chave:
                    indice.setdefault(chave, set()).add(linha["sourceid"])
            self._indice = indice
        return self._indice

    def titulo(self, sourceid: int) -> str | None:
        linha = self._con.execute("SELECT titulo FROM periodico WHERE sourceid = ?", (sourceid,)).fetchone()
        return linha["titulo"] if linha else None

    def nota(self, sourceid: int, ano_min: int, ano_max: int) -> Nota | None:
        """Maior percentil do periódico entre ano_min e ano_max (melhor categoria de cada ano).

        Em caso de empate entre anos, vale o mais recente. None = sem percentil
        (sem SJR) em nenhum ano da janela.
        """
        extra_select = ", p.n_empatados AS n_empatados" if self._tem_empatados else ""
        extra_join = (
            " LEFT JOIN periodico_categoria_ano p ON p.sourceid = v.sourceid"
            " AND p.ano = v.ano AND p.categoria_id = v.categoria_id"
            if self._tem_empatados
            else ""
        )
        sql = (
            "SELECT v.ano, v.percentil, v.categoria, v.posicao, v.n_categoria, v.quartil_scimago"
            f"{extra_select} FROM v_melhor_percentil v{extra_join} "
            "WHERE v.sourceid = ? AND v.ano BETWEEN ? AND ? "
            "ORDER BY v.percentil DESC, v.ano DESC LIMIT 1"
        )
        linha = self._con.execute(sql, (sourceid, ano_min, ano_max)).fetchone()
        if linha is None:
            return None
        return Nota(
            percentil=float(linha["percentil"]),
            ano=int(linha["ano"]),
            categoria=linha["categoria"],
            posicao=float(linha["posicao"]) if linha["posicao"] is not None else None,
            n_categoria=linha["n_categoria"],
            quartil_scimago=linha["quartil_scimago"],
            n_empatados=linha["n_empatados"] if self._tem_empatados else None,
        )
