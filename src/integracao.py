"""Ponte entre a etapa 2 (lattes_rank: leitura do Lattes + banco SCImago) e o motor de regras.

Converte os artigos do currículo em ``ArtigoPontuavel`` (percentil 0–1) e explica
por que cada artigo que não entrou ficou de fora.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_BANCO = RAIZ / "scimago_etl" / "scimago.db"

# Antes de importar lattes_rank: na raiz, a pasta lattes_rank/ viraria um pacote vazio.
_SUBPROJETO = str(RAIZ / "lattes_rank")
if _SUBPROJETO not in sys.path:
    sys.path.insert(0, _SUBPROJETO)

from lattes_rank.banco import Banco  # noqa: E402
from lattes_rank.entrada import ArquivoInvalido, ler_bytes  # noqa: E402
from lattes_rank.parser import Curriculo  # noqa: E402
from lattes_rank.ranking import (  # noqa: E402
    PONTUADO,
    classificar_artigos,
    politica_estendida,
    politica_padrao,
)

from src.regras import (  # noqa: E402
    PARAMETROS_PADRAO,
    ArtigoPontuavel,
    DeclaracaoArtigoY,
    JanelaArtigos,
    ParametrosRegras,
    janela_de_artigos,
    remover_duplicatas,
)


@dataclass(frozen=True)
class ArtigoNaoEntrou:
    id: int
    titulo: str | None
    periodico: str | None
    ano: int | None
    status: str
    motivo: str


@dataclass
class AvaliacaoCurriculo:
    curriculo: Curriculo
    janela: JanelaArtigos
    janela_nota: tuple[int, int]
    pontuaveis: list[ArtigoPontuavel]
    nao_entraram: list[ArtigoNaoEntrou]


def abrir_banco(caminho: Path = CAMINHO_BANCO) -> Banco:
    return Banco(caminho, multithread=True)


__all__ = ["ArquivoInvalido", "abrir_banco", "avaliar", "lembrete_artigo_y", "ler_arquivo"]


def ler_arquivo(dados: bytes, nome_arquivo: str) -> Curriculo:
    """Currículo Lattes em HTML, XML ou ZIP; levanta ArquivoInvalido se não der para ler."""
    return ler_bytes(dados, arquivo=nome_arquivo)


def lembrete_artigo_y(curriculo: Curriculo) -> str | None:
    """Texto do lembrete com as licenças e o PcD registrados no XML (None se não há nada)."""
    pcd = curriculo.pcd if curriculo.pcd and curriculo.pcd.upper() not in ("NAO", "NÃO") else None
    if not curriculo.licencas and pcd is None:
        return None
    partes = []
    if curriculo.licencas:
        n = len(curriculo.licencas)
        lista = "; ".join(f"{l.tipo} de {l.inicio or '?'} a {l.fim or '?'}" for l in curriculo.licencas)
        partes.append(f"{n} licença{'s' if n > 1 else ''} ({lista})")
    if pcd is not None:
        partes.append(f"PcD: {pcd}")
    return (
        "O XML do Lattes registra: " + ". ".join(partes) + ".\n\n"
        "Confira e preencha os campos abaixo; o sistema não decide se cada licença conta."
    )


def avaliar(
    curriculo: Curriculo,
    banco: Banco,
    declaracao: DeclaracaoArtigoY,
    params: ParametrosRegras = PARAMETROS_PADRAO,
) -> AvaliacaoCurriculo:
    janela_nota = banco.anos_com_percentil()
    janela = janela_de_artigos(*janela_nota, declaracao, params)
    if janela.anos_extras == 0:
        politica = politica_padrao(*janela_nota)
    else:
        politica = politica_estendida(*janela_nota, janela.anos_extras)

    pontuaveis: list[ArtigoPontuavel] = []
    nao_entraram: list[ArtigoNaoEntrou] = []
    avaliados = classificar_artigos(curriculo.artigos, banco, politica, janela_nota)
    for indice, av in enumerate(avaliados):
        artigo = av.artigo
        periodico = av.periodico_base or artigo.periodico_nome or "(sem nome)"
        if av.status == PONTUADO:
            pontuaveis.append(
                ArtigoPontuavel(
                    id=indice,
                    titulo=artigo.titulo,
                    periodico=periodico,
                    ano=artigo.ano,
                    percentil=av.nota.percentil / 100,
                    doi=artigo.doi,
                    empate_sjr=av.nota.empate_sjr,
                )
            )
        else:
            nao_entraram.append(
                ArtigoNaoEntrou(
                    id=indice,
                    titulo=artigo.titulo,
                    periodico=av.periodico_base or artigo.periodico_nome,
                    ano=artigo.ano,
                    status=av.status,
                    motivo=av.motivo or "",
                )
            )

    mantidos, duplicados = remover_duplicatas(pontuaveis)
    for d in duplicados:
        nao_entraram.append(
            ArtigoNaoEntrou(
                id=d.id,
                titulo=d.titulo,
                periodico=d.periodico,
                ano=d.ano,
                status="duplicado",
                motivo="mesmo artigo já listado no currículo",
            )
        )
    nao_entraram.sort(key=lambda n: n.id)
    return AvaliacaoCurriculo(curriculo, janela, janela_nota, mantidos, nao_entraram)
