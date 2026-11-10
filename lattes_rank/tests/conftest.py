import sys
from pathlib import Path

import pytest

# Permite rodar tanto de dentro de lattes_rank/ quanto da raiz do repositório
# (na raiz, a pasta lattes_rank/ seria importada como pacote vazio).
RAIZ_SUBPROJETO = Path(__file__).resolve().parent.parent
if str(RAIZ_SUBPROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_SUBPROJETO))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def caminho_banco(tmp_path):
    from banco_ficticio import criar_banco

    return criar_banco(tmp_path / "ficticio.sqlite")


@pytest.fixture()
def banco(caminho_banco):
    from lattes_rank.banco import Banco

    with Banco(caminho_banco) as b:
        yield b


@pytest.fixture(scope="session")
def html_artigos() -> str:
    return (FIXTURES / "artigos_completos.html").read_text(encoding="utf-8")


@pytest.fixture()
def curriculo(html_artigos):
    from lattes_rank.parser import interpretar_html

    return interpretar_html(html_artigos, arquivo="fixture")
