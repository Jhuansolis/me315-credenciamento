import pytest

from lattes_rank.issn import digito_verificador_ok, formato_valido, normalizar_issn


@pytest.mark.parametrize(
    "bruto, esperado",
    [
        ("0377-7332", "03777332"),
        ("03777332", "03777332"),
        (" 1093-474x ", "1093474X"),
        ("", None),
        (None, None),
        ("---", None),
    ],
)
def test_normalizar(bruto, esperado):
    assert normalizar_issn(bruto) == esperado


def test_nao_completa_zeros():
    # Não "conserta" ISSN curto: melhor não localizar do que casar errado.
    assert normalizar_issn("377332") == "377332"
    assert not formato_valido("377332")


@pytest.mark.parametrize("issn", ["03777332", "1093474X", "15372707", "1099131X", "24523062", "01692070", "00949655"])
def test_issns_reais_do_curriculo_passam_no_digito_verificador(issn):
    assert formato_valido(issn)
    assert digito_verificador_ok(issn)


def test_digito_verificador_errado():
    assert formato_valido("03777333")
    assert not digito_verificador_ok("03777333")


def test_formato_invalido():
    assert not formato_valido(None)
    assert not formato_valido("0377733")
    assert not formato_valido("0377733A")
    assert not digito_verificador_ok("ABC")
