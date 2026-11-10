import sqlite3

import pytest

from banco_ficticio import criar_banco
from lattes_rank.banco import Banco, Nota


def test_anos_da_base(banco):
    assert banco.anos_com_percentil() == (2022, 2025)


def test_nota_e_o_maior_percentil_entre_os_anos_na_melhor_categoria(banco):
    nota = banco.nota(1, 2022, 2025)  # RBFin: 2022 tem 40 (Stats) e 55 (Finance); o melhor ano é 2024
    assert (nota.percentil, nota.ano, nota.categoria) == (61.5, 2024, "Finance")
    assert banco.nota(1, 2022, 2022).percentil == 55.0  # melhor categoria do ano, não a primeira


def test_empate_de_nota_entre_anos_fica_com_o_mais_recente(banco):
    assert banco.nota(5, 2022, 2025).ano == 2025  # 99 em 2024 e 2025


def test_posicao_e_real(banco):
    nota = banco.nota(2, 2022, 2025)
    assert isinstance(nota.posicao, float) and nota.posicao == 4.0 and nota.n_categoria == 100


def test_n_empatados_e_semantica_de_empate(banco):
    com_empate = banco.nota(2, 2022, 2025)  # 3 periódicos dividem o SJR
    sem_empate = banco.nota(3, 2022, 2025)  # n_empatados = 1 no esquema real = sem empate
    assert (com_empate.n_empatados, com_empate.empate_sjr) == (3, True)
    assert (sem_empate.n_empatados, sem_empate.empate_sjr) == (1, False)
    assert not Nota(50.0, 2025, "x", 1.0, 10, "Q1", None).empate_sjr


def test_periodico_sem_percentil(banco):
    # Tem linhas em periodico_categoria_ano, mas todas com percentil NULL (sem SJR).
    assert banco.nota(9, 2022, 2025) is None


def test_indice_issn_junta_impresso_e_online(banco):
    indice = banco.indice_issn()
    assert indice["19845146"] == {1} and indice["16790731"] == {1}


def test_indice_issn_normaliza_o_que_vem_do_banco(caminho_banco):
    con = sqlite3.connect(caminho_banco)
    con.execute("INSERT INTO periodico_issn VALUES ('1234-567x', '1234-567X', 7)")
    con.commit()
    con.close()
    with Banco(caminho_banco) as b:
        assert b.indice_issn()["1234567X"] == {7}


def test_banco_e_somente_leitura(caminho_banco):
    with Banco(caminho_banco) as b:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            b._con.execute("DELETE FROM periodico")


def test_banco_inexistente_e_banco_errado(tmp_path):
    with pytest.raises(FileNotFoundError):
        Banco(tmp_path / "nao_existe.sqlite")
    vazio = tmp_path / "vazio.sqlite"
    sqlite3.connect(vazio).close()
    with pytest.raises(ValueError, match="objetos esperados"):
        Banco(vazio)


def test_banco_com_coluna_faltando(tmp_path):
    caminho = tmp_path / "torto.sqlite"
    con = sqlite3.connect(caminho)
    con.executescript(
        "CREATE TABLE periodico_issn (issn TEXT, sid INTEGER);"
        "CREATE TABLE periodico (sourceid INTEGER, titulo TEXT);"
        "CREATE TABLE v_melhor_percentil (sourceid INTEGER);"
    )
    con.close()
    with pytest.raises(ValueError) as erro:
        Banco(caminho)
    assert "periodico_issn (sem sourceid)" in str(erro.value)
    assert "v_melhor_percentil (sem ano" in str(erro.value)


def test_arquivo_que_nao_e_sqlite(tmp_path):
    falso = tmp_path / "falso.sqlite"
    falso.write_text("isto não é um banco", encoding="utf-8")
    with pytest.raises(ValueError, match="não é um banco SQLite válido"):
        Banco(falso)


def test_banco_sem_nenhum_percentil(tmp_path):
    caminho = criar_banco(tmp_path / "x.sqlite")
    con = sqlite3.connect(caminho)
    con.execute("UPDATE periodico_categoria_ano SET percentil = NULL")
    con.commit()
    con.close()
    with Banco(caminho) as b, pytest.raises(ValueError, match="vazia"):
        b.anos_com_percentil()


def test_funciona_sem_a_coluna_n_empatados(tmp_path):
    caminho = criar_banco(tmp_path / "x.sqlite")
    con = sqlite3.connect(caminho)
    con.execute("ALTER TABLE periodico_categoria_ano DROP COLUMN n_empatados")
    con.commit()
    con.close()
    with Banco(caminho) as b:
        nota = b.nota(2, 2022, 2025)
        assert nota.percentil == 97.0 and nota.n_empatados is None and not nota.empate_sjr
