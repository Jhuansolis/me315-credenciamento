"""Motor de regras do credenciamento (funções puras, sem I/O).

Artigo X: o candidato escolhe até 4 artigos; cada artigo vale o percentil do
periódico (0–1) se esse percentil for >= corte individual (0,25), senão vale 0.
A nota é a soma das contribuições e o candidato é apto com nota >= 1,25.
Comparações usam tolerância de 1e-9 por causa de ruído de ponto flutuante
(percentis do banco, 0–100, são divididos por 100 antes de chegar aqui).

Também oferece a pré-seleção dos melhores artigos e a remoção de duplicatas
(mesmo DOI, ou mesmo título normalizado e ano).

Spec: docs/superpowers/specs/2026-11-13-motor-regras-streamlit-design.md (seção 2).
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Arredondamento = Literal["cima", "baixo", "proximo"]

_TOLERANCIA = 1e-9


@dataclass(frozen=True)
class ParametrosRegras:
    meses_por_licenca_parental: int = 24
    meses_pcd: int = 24
    pcd_conta_uma_vez: bool = True
    arredondamento: Arredondamento = "cima"
    max_artigos: int = 4
    corte_individual: float = 0.25
    nota_minima: float = 1.25


PARAMETROS_PADRAO = ParametrosRegras()


@dataclass(frozen=True)
class ArtigoPontuavel:
    id: int  # posição no currículo (0-based)
    titulo: str | None
    periodico: str
    ano: int
    percentil: float  # 0–1
    doi: str | None = None
    empate_sjr: bool = False


@dataclass(frozen=True)
class ContribuicaoArtigo:
    artigo: ArtigoPontuavel
    conta: bool
    contribuicao: float


@dataclass(frozen=True)
class ResultadoNota:
    itens: tuple[ContribuicaoArtigo, ...]
    total: float
    apto: bool


def calcular_nota(
    escolhidos: list[ArtigoPontuavel], params: ParametrosRegras = PARAMETROS_PADRAO
) -> ResultadoNota:
    if len(escolhidos) > params.max_artigos:
        raise ValueError(
            f"No máximo {params.max_artigos} artigos podem ser escolhidos "
            f"(recebidos: {len(escolhidos)})."
        )
    itens = []
    for artigo in escolhidos:
        conta = artigo.percentil >= params.corte_individual - _TOLERANCIA
        itens.append(ContribuicaoArtigo(artigo, conta, artigo.percentil if conta else 0))
    total = sum(i.contribuicao for i in itens)
    return ResultadoNota(tuple(itens), total, total >= params.nota_minima - _TOLERANCIA)


def preselecionar(
    artigos: list[ArtigoPontuavel], params: ParametrosRegras = PARAMETROS_PADRAO
) -> list[int]:
    """Ids dos melhores artigos: maior percentil, depois ano mais recente, depois id."""
    ordenados = sorted(artigos, key=lambda a: (-a.percentil, -a.ano, a.id))
    return [a.id for a in ordenados[: params.max_artigos]]


def _chave_duplicata(artigo: ArtigoPontuavel) -> tuple | None:
    if artigo.doi and artigo.doi.strip():
        doi = artigo.doi.strip().lower()
        for prefixo in ("https://doi.org/", "http://doi.org/", "doi:"):
            if doi.startswith(prefixo):
                doi = doi[len(prefixo):]
                break
        return ("doi", "".join(doi.split()))
    if artigo.titulo and artigo.titulo.strip():
        sem_acentos = unicodedata.normalize("NFKD", artigo.titulo)
        sem_acentos = "".join(c for c in sem_acentos if not unicodedata.combining(c))
        limpo = re.sub(r"[^a-z0-9\s]", "", sem_acentos.lower())
        return ("titulo", " ".join(limpo.split()), artigo.ano)
    return None


def remover_duplicatas(
    artigos: list[ArtigoPontuavel],
) -> tuple[list[ArtigoPontuavel], list[ArtigoPontuavel]]:
    """Devolve (mantidos, duplicados), ambos na ordem de entrada; mantém a primeira ocorrência."""
    vistas: set[tuple] = set()
    mantidos: list[ArtigoPontuavel] = []
    duplicados: list[ArtigoPontuavel] = []
    for artigo in artigos:
        chave = _chave_duplicata(artigo)
        if chave is not None and chave in vistas:
            duplicados.append(artigo)
            continue
        if chave is not None:
            vistas.add(chave)
        mantidos.append(artigo)
    return mantidos, duplicados
