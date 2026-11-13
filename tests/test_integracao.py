import sys
from pathlib import Path

import pytest

import src.integracao  # noqa: F401  (põe lattes_rank/ no sys.path)
from src.integracao import RAIZ, abrir_banco, avaliar, ler_html
from src.regras import DeclaracaoArtigoY

sys.path.insert(0, str(RAIZ / "lattes_rank" / "tests"))
from banco_ficticio import criar_banco  # noqa: E402

FIXTURE = RAIZ / "lattes_rank" / "tests" / "fixtures" / "artigos_completos.html"


@pytest.fixture()
def banco(tmp_path):
    b = abrir_banco(criar_banco(tmp_path / "ficticio.sqlite"))
    yield b
    b.fechar()


def curriculo_fixture():
    return ler_html(FIXTURE.read_bytes(), "fixture")


def test_avaliar_fixture_sem_ampliacao(banco):
    av = avaliar(curriculo_fixture(), banco, DeclaracaoArtigoY())
    assert av.janela_nota == (2022, 2025)
    assert (av.janela.ano_min, av.janela.ano_max) == (2022, 2025)
    assert av.pontuaveis
    assert all(0 < a.percentil <= 1 for a in av.pontuaveis)
    assert all(2022 <= a.ano <= 2025 for a in av.pontuaveis)
    assert all(a.periodico for a in av.pontuaveis)
    ids = [a.id for a in av.pontuaveis] + [n.id for n in av.nao_entraram]
    assert sorted(ids) == list(range(len(av.curriculo.artigos)))


def test_ampliacao_so_acrescenta_artigos_e_nao_muda_percentil(banco):
    base = avaliar(curriculo_fixture(), banco, DeclaracaoArtigoY())
    amp = avaliar(curriculo_fixture(), banco, DeclaracaoArtigoY(n_licencas_parentais=5))
    p_base = {a.id: a.percentil for a in base.pontuaveis}
    p_amp = {a.id: a.percentil for a in amp.pontuaveis}
    assert set(p_base) <= set(p_amp)
    assert all(p_amp[i] == p_base[i] for i in p_base)
    assert all(a.ano <= 2025 for a in amp.pontuaveis)
    assert amp.janela_nota == (2022, 2025)


def test_duplicata_vai_para_nao_entraram(banco):
    cur = curriculo_fixture()
    primeiro = next(a for a in avaliar(cur, banco, DeclaracaoArtigoY()).pontuaveis)
    cur.artigos.append(cur.artigos[primeiro.id])
    av = avaliar(cur, banco, DeclaracaoArtigoY())
    dup = [n for n in av.nao_entraram if n.status == "duplicado"]
    assert len(dup) == 1 and dup[0].id == len(cur.artigos) - 1
    assert dup[0].motivo == "mesmo artigo já listado no currículo"


def test_html_que_nao_e_lattes(banco):
    cur = ler_html(b"<html><body>oi</body></html>", "x.html")
    assert cur.artigos == [] and cur.avisos
    av = avaliar(cur, banco, DeclaracaoArtigoY())
    assert av.pontuaveis == [] and av.nao_entraram == []
