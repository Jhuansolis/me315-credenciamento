import pytest
from conftest import FIXTURES

from lattes_rank.parser import Licenca
from lattes_rank.parser_xml import ArquivoInvalido, interpretar_xml

FIXTURE_XML = FIXTURES / "artigos_completos.xml"


def test_le_os_17_artigos_com_mesmos_ano_issn_doi_do_html(curriculo):
    cv = interpretar_xml(FIXTURE_XML.read_bytes(), "fixture.xml")
    assert len(cv.artigos) == 17
    assert [a.sequencia for a in cv.artigos] == list(range(1, 18))  # ordem do arquivo
    # curriculo = fixture HTML do mesmo docente
    assert sorted((a.ano, a.issn, a.doi) for a in cv.artigos) == sorted(
        (a.ano, a.issn, a.doi) for a in curriculo.artigos
    )
    assert cv.avisos == []


def test_cabecalho_licencas_e_pcd():
    cv = interpretar_xml(FIXTURE_XML.read_bytes(), "fixture.xml")
    assert (cv.nome, cv.id_lattes, cv.data_atualizacao) == (
        "Fulana de Tal Conceição",
        "1234567890123456",
        "26/10/2026",
    )
    assert cv.licencas == [Licenca("PATERNIDADE", "10/03/2022", "29/03/2022")]
    assert cv.pcd == "SIM"
    assert cv.arquivo == "fixture.xml"


def test_campos_do_artigo():
    cv = interpretar_xml(FIXTURE_XML.read_bytes())
    eciperu = next(a for a in cv.artigos if a.issn == "18130194")
    assert (eciperu.ano, eciperu.doi, eciperu.periodico_nome, eciperu.issn_bruto) == (
        2009,
        None,
        "ECIPERU",
        "18130194",
    )
    assert eciperu.titulo.startswith("Factores que influyen")


def test_xml_utf8_com_acento():
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><CURRICULO-VITAE NUMERO-IDENTIFICADOR="1">'
        '<DADOS-GERAIS NOME-COMPLETO="João Ninguém"/></CURRICULO-VITAE>'
    )
    cv = interpretar_xml(xml.encode("utf-8"))
    assert cv.nome == "João Ninguém" and cv.artigos == [] and cv.licencas == [] and cv.pcd is None
    assert any("Nenhum artigo" in a for a in cv.avisos)


def test_artigo_sem_issn_e_sem_ano_vira_none_com_aviso():
    xml = (
        b'<?xml version="1.0"?><CURRICULO-VITAE><PRODUCAO-BIBLIOGRAFICA><ARTIGOS-PUBLICADOS>'
        b'<ARTIGO-PUBLICADO><DADOS-BASICOS-DO-ARTIGO TITULO-DO-ARTIGO="T"/>'
        b'<DETALHAMENTO-DO-ARTIGO ISSN=""/></ARTIGO-PUBLICADO>'
        b"</ARTIGOS-PUBLICADOS></PRODUCAO-BIBLIOGRAFICA></CURRICULO-VITAE>"
    )
    cv = interpretar_xml(xml)
    assert cv.artigos[0].issn is None and cv.artigos[0].ano is None
    assert any("artigo 1" in a and "ano" in a for a in cv.avisos)


@pytest.mark.parametrize(
    "dados",
    [
        b"<CURRICULO-VITAE><nao-fecha>",
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaa">]><CURRICULO-VITAE/>',
        b'<?xml version="1.0"?><outra-coisa/>',
        # UTF-16: a busca por bytes "<!DOCTYPE" não acha a declaração
        '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY a "AAAA">]>'
        '<CURRICULO-VITAE><DADOS-GERAIS NOME-COMPLETO="&a;"/></CURRICULO-VITAE>'.encode("utf-16"),
        b'<?xml version="1.0" encoding="foo-bar"?><CURRICULO-VITAE/>',
        b'<?xml version="1.0" encoding="Shift_JIS"?><CURRICULO-VITAE/>',
    ],
)
def test_xml_invalido_levanta_arquivo_invalido(dados):
    with pytest.raises(ArquivoInvalido):
        interpretar_xml(dados)


def test_fixture_nao_tem_data_de_nascimento():
    assert b"DATA-NASCIMENTO" not in FIXTURE_XML.read_bytes()
