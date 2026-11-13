import pytest

from src.regras import (
    ArtigoPontuavel,
    calcular_nota,
    preselecionar,
    remover_duplicatas,
)


def art(id, p, ano=2024, doi=None, titulo="T"):
    return ArtigoPontuavel(id, titulo, "Revista", ano, p, doi)


def test_soma_os_artigos_que_passam_do_corte():
    r = calcular_nota([art(0, 0.9), art(1, 0.8), art(2, 0.2)])
    assert r.total == pytest.approx(1.7)
    assert [i.conta for i in r.itens] == [True, True, False]
    assert r.itens[2].contribuicao == 0
    assert r.apto


def test_fronteira_conta_e_aprova():  # Review Focus 1
    r = calcular_nota([art(0, 50.0 / 100), art(1, 50.0 / 100), art(2, 25.0 / 100)])
    assert r.itens[2].conta
    assert r.apto


def test_fronteira_com_ruido_de_ponto_flutuante():
    # percentis reais do banco (0–100) divididos por 100: a soma dá 1.2499999999999998
    r = calcular_nota([art(0, 25.02 / 100), art(1, 25.49 / 100), art(2, 74.49 / 100)])
    assert r.apto  # 1,25 com ruído de ponto flutuante ainda é ≥ 1,25 (tolerância 1e-9)


def test_lista_vazia_da_zero_e_nao_apto():  # Review Focus 3
    r = calcular_nota([])
    assert r.total == 0 and not r.apto and r.itens == ()


def test_mais_de_quatro_artigos_e_erro():
    with pytest.raises(ValueError):
        calcular_nota([art(i, 0.5) for i in range(5)])


def test_mesma_revista_pode_entrar_quatro_vezes():
    artigos = [art(i, 0.9) for i in range(4)]  # todos "Revista"
    assert calcular_nota(artigos).total == pytest.approx(3.6)


def test_preselecao_pega_os_quatro_maiores_com_desempate():
    artigos = [art(0, 0.5, 2022), art(1, 0.9), art(2, 0.5, 2025), art(3, 0.7), art(4, 0.5, 2025), art(5, 0.1)]
    assert preselecionar(artigos) == [1, 3, 2, 4]  # empate 0.5: ano mais recente, depois id


def test_preselecao_devolve_subconjunto_dos_ids():  # Review Focus 4
    assert preselecionar([art(7, 0.3)]) == [7]
    assert preselecionar([]) == []


def test_duplicata_por_doi_normalizado():  # Review Focus 5
    a = art(0, 0.9, doi="https://doi.org/10.1/ABC")
    b = art(1, 0.9, doi="10.1/abc")
    assert remover_duplicatas([a, b]) == ([a], [b])


def test_duplicata_sem_doi_por_titulo_e_ano():
    a = art(0, 0.9, titulo="Um Título, com Acentuação!")
    b = art(1, 0.9, titulo="um titulo com acentuacao")
    c = art(2, 0.9, ano=2023, titulo="um titulo com acentuacao")
    assert remover_duplicatas([a, b, c]) == ([a, c], [b])


def test_sem_doi_e_sem_titulo_nunca_e_duplicata():  # Review Focus 5
    a, b = art(0, 0.9, titulo=None), art(1, 0.9, titulo=None)
    assert remover_duplicatas([a, b]) == ([a, b], [])
