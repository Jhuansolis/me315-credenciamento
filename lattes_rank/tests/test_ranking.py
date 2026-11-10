import sqlite3

import pytest

from lattes_rank.banco import Banco, Nota
from lattes_rank.parser import Artigo, Curriculo
from lattes_rank.ranking import (
    AMBIGUO,
    AUSENTE_NO_BANCO,
    DIGITO_VERIFICADOR,
    FORA_DA_JANELA,
    FORMATO_INVALIDO,
    NAO_LOCALIZADO,
    PONTUADO,
    SEM_ANO,
    SEM_ISSN,
    SEM_PERCENTIL,
    SEM_SJR_NA_JANELA,
    ArtigoAvaliado,
    avaliar_curriculo,
    montar_ranking,
    politica_estendida,
    politica_padrao,
)


def nomes(linhas):
    return [l.periodico for l in linhas]


def artigo(ano=2023, issn_bruto="00000000", issn="00000000", nome="Revista"):
    return Artigo(1, ano, "t", nome, issn_bruto, issn, None)


# ---- política de anos ----------------------------------------------------
def test_politicas():
    padrao = politica_padrao(2022, 2025)
    assert [padrao.aceita(a) for a in (2021, 2022, 2025, 2026, None)] == [False, True, True, False, False]
    sem_limite = politica_estendida(2022, 2025)
    assert [sem_limite.aceita(a) for a in (1999, 2021, 2025, 2026)] == [True, True, True, False]
    limitada = politica_estendida(2022, 2025, anos_retroativos=2)
    assert limitada.ano_min == 2020
    assert [limitada.aceita(a) for a in (2019, 2020, 2026)] == [False, True, False]


def test_politica_estendida_com_zero_anos_equivale_a_padrao_e_negativo_e_erro():
    zero = politica_estendida(2022, 2025, anos_retroativos=0)
    assert (zero.ano_min, zero.ano_max) == (2022, 2025)
    with pytest.raises(ValueError):
        politica_estendida(2022, 2025, anos_retroativos=-1)


# ---- pipeline completo com o currículo de exemplo -------------------------
def test_modo_padrao_ranking_e_desempate_alfabetico(curriculo, banco):
    r = avaliar_curriculo(curriculo, banco)
    assert r.janela_nota == (2022, 2025)
    assert nomes(r.top) == [
        "Journal of Business and Economic Statistics",  # nota 97 (2022), embora o artigo seja de 2023
        "Econometrics and Statistics",  # 88 = Journal of Forecasting; desempate final por título
        "Journal of Forecasting",
        "Revista Brasileira de Financas",  # 61.5, com 3 artigos nos dois ISSNs
    ]
    assert [l.percentil for l in r.top] == [97.0, 88.0, 88.0, 61.5]
    assert [l.empatado_na_nota for l in r.top] == [False, True, True, False]
    assert [l.empate_sjr for l in r.top] == [True, False, False, False]  # só JBES 2022 tem n_empatados = 3
    rbf = r.top[3]
    assert rbf.n_artigos == 3 and rbf.anos_artigos == (2025, 2024, 2023) and rbf.issns == ("16790731", "19845146")
    assert r.top[0].nota.n_empatados == 3
    assert r.contagens == {PONTUADO: 6, FORA_DA_JANELA: 11}
    assert r.n_elegiveis == 6


def test_2026_nunca_pontua_nem_na_condicao_especial(curriculo, banco):
    for politica in (politica_padrao(2022, 2025), politica_estendida(2022, 2025)):
        r = avaliar_curriculo(curriculo, banco, politica)
        fora_2026 = [a for a in r.por_status(FORA_DA_JANELA) if a.artigo.ano == 2026]
        assert len(fora_2026) == 2
        assert "Empirical Economics" not in nomes(r.ranking)


def test_condicao_especial_sem_limite(curriculo, banco):
    r = avaliar_curriculo(curriculo, banco, politica_estendida(2022, 2025))
    assert nomes(r.top) == [
        "International Journal of Forecasting",  # 99, 2 artigos antigos (2021, 2019)
        "Journal of Business and Economic Statistics",
        "Journal of Empirical Finance",  # 90 por um artigo de 2019: a nota vem da janela 2022-2025
        "Econometrics and Statistics",
    ]
    assert r.top[0].anos_artigos == (2021, 2019) and r.top[0].ano_do_percentil == 2025
    assert nomes(r.ranking)[4] == "Journal of Forecasting"
    assert r.contagens == {PONTUADO: 12, SEM_PERCENTIL: 2, NAO_LOCALIZADO: 1, FORA_DA_JANELA: 2}
    assert sum(r.contagens.values()) == 17


def test_condicao_especial_com_limite_retroativo(curriculo, banco):
    r = avaliar_curriculo(curriculo, banco, politica_estendida(2022, 2025, anos_retroativos=2))  # a partir de 2020
    assert nomes(r.top) == [
        "International Journal of Forecasting",  # só o artigo de 2021 entra
        "Journal of Business and Economic Statistics",
        "Econometrics and Statistics",
        "Journal of Forecasting",
    ]
    assert r.top[0].n_artigos == 1
    assert "Journal of Empirical Finance" not in nomes(r.ranking)  # artigo de 2019 fica de fora


def test_listas_auxiliares(curriculo, banco):
    r = avaliar_curriculo(curriculo, banco, politica_estendida(2022, 2025))
    (nao_loc,) = r.por_status(NAO_LOCALIZADO)
    assert nao_loc.artigo.periodico_nome == "ECIPERU" and "18130194" in nao_loc.motivo
    assert nao_loc.codigo_motivo == AUSENTE_NO_BANCO
    sem_perc = r.por_status(SEM_PERCENTIL)
    assert {a.periodico_base for a in sem_perc} == {"Journal of Statistical Computation and Simulation"}
    assert {a.codigo_motivo for a in sem_perc} == {SEM_SJR_NA_JANELA}


def test_motivos_de_nao_localizado(banco):
    cv = Curriculo(
        "x", None, None, None,
        [artigo(issn_bruto=None, issn=None), artigo(issn_bruto="12-3", issn="123"),
         artigo(issn_bruto="03777333", issn="03777333"), artigo(issn_bruto="0000-0019", issn="00000019")],
    )
    r = avaliar_curriculo(cv, banco)
    avaliados = r.por_status(NAO_LOCALIZADO)
    assert [a.codigo_motivo for a in avaliados] == [SEM_ISSN, FORMATO_INVALIDO, DIGITO_VERIFICADOR, AUSENTE_NO_BANCO]
    assert avaliados[0].motivo == "sem ISSN no currículo"
    assert "formato inválido" in avaliados[1].motivo
    assert "dígito verificador" in avaliados[2].motivo


def test_ordem_de_avaliacao_ano_vem_antes_do_issn(banco):
    # Sem ano e ISSN inválido: o motivo é o ano (fora_da_janela), não o ISSN.
    cv = Curriculo("x", None, None, None, [artigo(ano=None, issn=None), artigo(ano=2026, issn=None)])
    r = avaliar_curriculo(cv, banco)
    assert [a.status for a in r.avaliados] == [FORA_DA_JANELA, FORA_DA_JANELA]
    assert r.avaliados[0].codigo_motivo == SEM_ANO


def test_issn_ambiguo_nao_e_resolvido(caminho_banco):
    con = sqlite3.connect(caminho_banco)
    con.execute("INSERT INTO periodico_issn VALUES ('15372707', '1537-2707', 3)")  # mesmo ISSN em outro periódico
    con.commit()
    con.close()
    cv = Curriculo("x", None, None, None, [artigo(issn_bruto="15372707", issn="15372707", nome="JBES")])
    with Banco(caminho_banco) as b:
        (a,) = avaliar_curriculo(cv, b).avaliados
    assert a.status == NAO_LOCALIZADO and a.codigo_motivo == AMBIGUO and "ambíguo" in a.motivo


# ---- ranking: critérios de desempate ---------------------------------------
def _pontuado(sourceid, titulo, percentil, ano):
    nota = Nota(percentil, 2025, "Cat", 1.0, 10, "Q1", 1)
    return ArtigoAvaliado(artigo(ano=ano, nome=titulo), PONTUADO, sourceid=sourceid, periodico_base=titulo, nota=nota)


def test_desempate_por_numero_de_artigos_e_depois_por_ano_mais_recente():
    itens = [
        _pontuado(1, "A", 90.0, 2025),
        _pontuado(2, "B", 90.0, 2023), _pontuado(2, "B", 90.0, 2022),  # 2 artigos
        _pontuado(3, "C", 90.0, 2024),  # 1 artigo, mais recente que D
        _pontuado(4, "D", 90.0, 2023),
        _pontuado(5, "E", 95.0, 2022),
    ]
    linhas = montar_ranking(itens)
    assert nomes(linhas) == ["E", "B", "A", "C", "D"]
    assert [l.empatado_na_nota for l in linhas] == [False, True, True, True, True]


def test_desempate_final_por_titulo_e_estavel():
    itens = [_pontuado(2, "beta", 80.0, 2024), _pontuado(1, "Alfa", 80.0, 2024)]
    assert nomes(montar_ranking(itens)) == ["Alfa", "beta"]
    assert nomes(montar_ranking(list(reversed(itens)))) == ["Alfa", "beta"]


def test_periodico_aparece_uma_vez_so():
    itens = [_pontuado(1, "A", 90.0, 2025), _pontuado(1, "A", 90.0, 2024), _pontuado(2, "B", 80.0, 2025)]
    linhas = montar_ranking(itens)
    assert nomes(linhas) == ["A", "B"] and linhas[0].n_artigos == 2


def test_ranking_vazio():
    assert montar_ranking([]) == []
