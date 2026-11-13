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
        normalizado = " ".join(limpo.split())
        if normalizado:
            return ("titulo", normalizado, artigo.ano)
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


@dataclass(frozen=True)
class DeclaracaoArtigoY:
    n_licencas_parentais: int = 0
    pcd_docente: bool = False
    pcd_familiar: bool = False
    meses_licenca_medica: int = 0


@dataclass(frozen=True)
class JanelaArtigos:
    ano_min: int
    ano_max: int
    anos_extras: int
    memoria: tuple[str, ...]


def _meses_parentais(d: DeclaracaoArtigoY, params: ParametrosRegras) -> int:
    return d.n_licencas_parentais * params.meses_por_licenca_parental


def _meses_pcd(d: DeclaracaoArtigoY, params: ParametrosRegras) -> int:
    n = int(d.pcd_docente) + int(d.pcd_familiar)
    if params.pcd_conta_uma_vez:
        n = min(n, 1)
    return n * params.meses_pcd


def _validar(d: DeclaracaoArtigoY) -> None:
    if d.n_licencas_parentais < 0 or d.meses_licenca_medica < 0:
        raise ValueError("Número de licenças e meses de licença médica não podem ser negativos.")


def meses_de_ampliacao(
    declaracao: DeclaracaoArtigoY, params: ParametrosRegras = PARAMETROS_PADRAO
) -> int:
    _validar(declaracao)
    return (
        _meses_parentais(declaracao, params)
        + _meses_pcd(declaracao, params)
        + declaracao.meses_licenca_medica
    )


def anos_de_ampliacao(meses: int, params: ParametrosRegras = PARAMETROS_PADRAO) -> int:
    if params.arredondamento == "cima":
        return -(-meses // 12)
    if params.arredondamento == "baixo":
        return meses // 12
    return (meses + 6) // 12


_TEXTO_ARREDONDAMENTO = {
    "cima": "para cima",
    "baixo": "para baixo",
    "proximo": "para o mais próximo",
}


def janela_de_artigos(
    ano_base_min: int,
    ano_base_max: int,
    declaracao: DeclaracaoArtigoY,
    params: ParametrosRegras = PARAMETROS_PADRAO,
) -> JanelaArtigos:
    meses = meses_de_ampliacao(declaracao, params)
    anos = anos_de_ampliacao(meses, params)
    ano_min = ano_base_min - anos
    memoria = []
    m_parental = _meses_parentais(declaracao, params)
    if m_parental:
        memoria.append(
            f"{declaracao.n_licencas_parentais} licença(s) parental(is): +{m_parental} meses"
        )
    m_pcd = _meses_pcd(declaracao, params)
    if m_pcd:
        memoria.append(f"PcD: +{m_pcd} meses")
    if declaracao.meses_licenca_medica:
        memoria.append(f"Licença médica: +{declaracao.meses_licenca_medica} meses")
    memoria.append(
        f"Total: {meses} meses → {anos} ano(s) a mais "
        f"(arredondado {_TEXTO_ARREDONDAMENTO[params.arredondamento]})"
    )
    memoria.append(f"Janela de artigos: {ano_min}–{ano_base_max}")
    return JanelaArtigos(ano_min, ano_base_max, anos, tuple(memoria))
