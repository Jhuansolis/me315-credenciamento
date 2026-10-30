import pytest
from src.percentil import percentil


def test_melhor_revista_vale_1():
    assert percentil(1, 100) == 1.0


def test_pior_revista():
    assert percentil(100, 100) == pytest.approx(0.01)


def test_posicao_invalida():
    with pytest.raises(ValueError):
        percentil(0, 10)
