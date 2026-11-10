"""Política de anos, classificação dos artigos e ranking de periódicos.

Regras (decididas em 10/11/2026):
- A nota de um periódico é o MAIOR percentil dele entre os anos da base
  (janela de nota, hoje 2022-2025), na melhor categoria de cada ano. Ela não
  depende do ano do artigo. Empate de nota entre anos: vale o ano mais recente.
- O ano do artigo só decide se o artigo ENTRA na análise (política de anos).
  Modo padrão: artigos de 2022 a 2025. Modo estendido (condição especial do
  docente): artigos de anos anteriores também entram. Artigos posteriores ao
  último ano da base (ex.: 2026) nunca entram.
- Casamento por ISSN, agrupando por sourceid (impresso e online contam como um
  só periódico). ISSN que aponta para mais de um sourceid = ambíguo.
- Ranking: periódicos distintos, por nota; desempate pelo maior número de
  artigos elegíveis do docente no periódico, depois pelo ano mais recente e,
  por fim, pelo título (só para a ordem ser estável).

Pendências (NÃO decididas; ver README):
- Quantos anos para trás vai a condição especial -> ``politica_estendida``
  recebe ``anos_retroativos`` (None = sem limite) e não está na linha de comando.
- Periódico sem SJR no ano de publicação: como a nota é o máximo da janela,
  isso só tira o artigo do ranking quando o periódico não tem SJR em NENHUM ano
  (status ``sem_percentil``).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .banco import Banco, Nota
from .issn import digito_verificador_ok, formato_valido
from .parser import Artigo, Curriculo

# Status de cada artigo
PONTUADO = "pontuado"
FORA_DA_JANELA = "fora_da_janela"
NAO_LOCALIZADO = "nao_localizado"
SEM_PERCENTIL = "sem_percentil"
STATUS = (PONTUADO, FORA_DA_JANELA, NAO_LOCALIZADO, SEM_PERCENTIL)

# Códigos de motivo (estáveis, para o JSON); o texto do motivo é para leitura humana.
SEM_ANO = "sem_ano"
FORA_DA_POLITICA = "fora_da_politica"
SEM_ISSN = "sem_issn"
FORMATO_INVALIDO = "formato_invalido"
DIGITO_VERIFICADOR = "digito_verificador"
AUSENTE_NO_BANCO = "ausente_no_banco"
AMBIGUO = "ambiguo"
SEM_SJR_NA_JANELA = "sem_sjr_na_janela"


@dataclass(frozen=True)
class PoliticaElegibilidade:
    """Quais anos de publicação entram na análise. ano_min=None = sem limite inferior."""

    ano_min: int | None
    ano_max: int
    descricao: str

    def aceita(self, ano: int | None) -> bool:
        if ano is None:
            return False
        if ano > self.ano_max:
            return False
        return self.ano_min is None or ano >= self.ano_min


def politica_padrao(base_min: int, base_max: int) -> PoliticaElegibilidade:
    return PoliticaElegibilidade(base_min, base_max, f"artigos de {base_min} a {base_max}")


def politica_estendida(base_min: int, base_max: int, anos_retroativos: int | None = None) -> PoliticaElegibilidade:
    """Condição especial do docente: também entram artigos de anos anteriores.

    ``anos_retroativos`` = quantos anos antes de ``base_min`` entram; None = sem limite
    (quanto isso vale ainda será decidido). Não está ligada à linha de comando.
    O limite superior continua sendo ``base_max``: artigos posteriores nunca entram.
    """
    if anos_retroativos is not None and anos_retroativos < 0:
        raise ValueError("anos_retroativos não pode ser negativo")
    if anos_retroativos is None:
        return PoliticaElegibilidade(None, base_max, f"artigos até {base_max} (condição especial, sem limite inferior)")
    ano_min = base_min - anos_retroativos
    return PoliticaElegibilidade(
        ano_min, base_max, f"artigos de {ano_min} a {base_max} (condição especial, {anos_retroativos} ano(s) a mais)"
    )


@dataclass(frozen=True)
class ArtigoAvaliado:
    artigo: Artigo
    status: str
    motivo: str | None = None  # texto para o relatório
    codigo_motivo: str | None = None  # uma das constantes acima
    sourceid: int | None = None
    periodico_base: str | None = None  # título do periódico na base SCImago
    nota: Nota | None = None


@dataclass(frozen=True)
class LinhaRanking:
    posicao: int
    sourceid: int
    periodico: str
    percentil: float
    ano_do_percentil: int
    categoria: str
    n_artigos: int
    anos_artigos: tuple[int, ...]
    ano_mais_recente: int
    issns: tuple[str, ...]
    empatado_na_nota: bool  # mesma nota que um vizinho: a posição saiu dos desempates
    nota: Nota

    @property
    def empate_sjr(self) -> bool:
        """O percentil saiu de um bloco de SJR empatado (D2 da etapa 1)."""
        return self.nota.empate_sjr


@dataclass
class Resultado:
    curriculo: Curriculo
    politica: PoliticaElegibilidade
    janela_nota: tuple[int, int]
    avaliados: list[ArtigoAvaliado]
    ranking: list[LinhaRanking]
    top: list[LinhaRanking]
    contagens: dict[str, int] = field(default_factory=dict)

    def por_status(self, status: str) -> list[ArtigoAvaliado]:
        return [a for a in self.avaliados if a.status == status]

    @property
    def n_elegiveis(self) -> int:
        """Artigos aceitos pela regra de anos (pontuados ou não)."""
        return len(self.avaliados) - self.contagens.get(FORA_DA_JANELA, 0)


def _motivo_issn(issn_bruto: str | None, issn: str | None) -> tuple[str, str]:
    if not issn:
        return SEM_ISSN, "sem ISSN no currículo"
    if not formato_valido(issn):
        return FORMATO_INVALIDO, f"ISSN com formato inválido ({issn_bruto})"
    if not digito_verificador_ok(issn):
        return DIGITO_VERIFICADOR, f"ISSN com dígito verificador inválido ({issn}); não está na base"
    return AUSENTE_NO_BANCO, f"ISSN não está na base SCImago ({issn})"


def classificar_artigos(
    artigos: list[Artigo],
    banco: Banco,
    politica: PoliticaElegibilidade,
    janela_nota: tuple[int, int],
) -> list[ArtigoAvaliado]:
    """Dá um status a cada artigo, nesta ordem: anos -> ISSN -> nota.

    Ponto de extensão (futuro, NÃO implementado): uma ferramenta de normalização
    de nomes de periódico poderia ser tentada aqui para os artigos que caem em
    ``nao_localizado``, usando ``artigo.periodico_nome`` contra ``periodico.titulo``.
    Por ora o casamento é só por ISSN, para não arriscar casar errado.
    """
    indice = banco.indice_issn()
    cache_notas: dict[int, Nota | None] = {}
    avaliados: list[ArtigoAvaliado] = []

    for artigo in artigos:
        if artigo.ano is None:
            avaliados.append(ArtigoAvaliado(artigo, FORA_DA_JANELA, "sem ano", SEM_ANO))
            continue
        if not politica.aceita(artigo.ano):
            avaliados.append(
                ArtigoAvaliado(
                    artigo, FORA_DA_JANELA, f"ano {artigo.ano} fora da regra ({politica.descricao})", FORA_DA_POLITICA
                )
            )
            continue

        candidatos = indice.get(artigo.issn or "")
        if not candidatos:
            codigo, texto = _motivo_issn(artigo.issn_bruto, artigo.issn)
            avaliados.append(ArtigoAvaliado(artigo, NAO_LOCALIZADO, texto, codigo))
            continue
        if len(candidatos) > 1:
            ids = ", ".join(str(c) for c in sorted(candidatos))
            avaliados.append(
                ArtigoAvaliado(
                    artigo, NAO_LOCALIZADO, f"ISSN {artigo.issn} ambíguo: aparece em mais de um periódico ({ids})", AMBIGUO
                )
            )
            continue

        sourceid = next(iter(candidatos))
        if sourceid not in cache_notas:
            cache_notas[sourceid] = banco.nota(sourceid, *janela_nota)
        nota = cache_notas[sourceid]
        titulo_base = banco.titulo(sourceid)
        if nota is None:
            avaliados.append(
                ArtigoAvaliado(
                    artigo, SEM_PERCENTIL, f"periódico sem SJR/percentil em {janela_nota[0]}-{janela_nota[1]}",
                    SEM_SJR_NA_JANELA, sourceid=sourceid, periodico_base=titulo_base,
                )
            )
            continue
        avaliados.append(ArtigoAvaliado(artigo, PONTUADO, sourceid=sourceid, periodico_base=titulo_base, nota=nota))
    return avaliados


def montar_ranking(avaliados: list[ArtigoAvaliado]) -> list[LinhaRanking]:
    """Agrupa os artigos pontuados por periódico (sourceid) e ordena (lista completa)."""
    grupos: dict[int, list[ArtigoAvaliado]] = defaultdict(list)
    for item in avaliados:
        if item.status == PONTUADO:
            grupos[item.sourceid].append(item)

    brutos = []
    for sourceid, itens in grupos.items():
        anos = sorted((i.artigo.ano for i in itens), reverse=True)
        brutos.append(
            {
                "sourceid": sourceid,
                "titulo": itens[0].periodico_base or itens[0].artigo.periodico_nome or str(sourceid),
                "nota": itens[0].nota,  # a nota é do periódico, igual para todos os itens
                "n": len(itens),
                "anos": tuple(anos),
                "recente": anos[0],
                "issns": tuple(sorted({i.artigo.issn for i in itens if i.artigo.issn})),
            }
        )

    # Nota desc, nº de artigos desc, ano mais recente desc; título e id só para estabilidade.
    brutos.sort(key=lambda g: (-g["nota"].percentil, -g["n"], -g["recente"], g["titulo"].lower(), g["sourceid"]))

    linhas: list[LinhaRanking] = []
    for i, g in enumerate(brutos):
        nota = g["nota"]
        vizinhos = [brutos[j]["nota"].percentil for j in (i - 1, i + 1) if 0 <= j < len(brutos)]
        linhas.append(
            LinhaRanking(
                posicao=i + 1,
                sourceid=g["sourceid"],
                periodico=g["titulo"],
                percentil=nota.percentil,
                ano_do_percentil=nota.ano,
                categoria=nota.categoria,
                n_artigos=g["n"],
                anos_artigos=g["anos"],
                ano_mais_recente=g["recente"],
                issns=g["issns"],
                empatado_na_nota=nota.percentil in vizinhos,
                nota=nota,
            )
        )
    return linhas


def avaliar_curriculo(
    curriculo: Curriculo,
    banco: Banco,
    politica: PoliticaElegibilidade | None = None,
    janela_nota: tuple[int, int] | None = None,
    top_n: int = 4,
) -> Resultado:
    """Pipeline completo para um currículo já lido."""
    if janela_nota is None:
        janela_nota = banco.anos_com_percentil()
    if politica is None:
        politica = politica_padrao(*janela_nota)
    avaliados = classificar_artigos(curriculo.artigos, banco, politica, janela_nota)
    ranking = montar_ranking(avaliados)
    contagens = {status: n for status, n in Counter(a.status for a in avaliados).items()}
    return Resultado(
        curriculo=curriculo,
        politica=politica,
        janela_nota=janela_nota,
        avaliados=avaliados,
        ranking=ranking,
        top=ranking[:top_n],
        contagens=contagens,
    )
