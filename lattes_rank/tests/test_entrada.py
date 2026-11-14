import io
import zipfile

import pytest
from conftest import FIXTURES

from lattes_rank import entrada
from lattes_rank.entrada import ArquivoInvalido, ler_arquivo, ler_bytes

XML = (FIXTURES / "artigos_completos.xml").read_bytes()


def _zip(conteudo: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as arquivo_zip:
        for nome, dados in conteudo.items():
            arquivo_zip.writestr(nome, dados)
    return buffer.getvalue()


def test_html_vai_para_o_leitor_de_html(html_artigos):
    assert len(ler_bytes(html_artigos.encode("utf-8"), "a.html").artigos) == 17


def test_xml_vai_para_o_leitor_de_xml():
    cv = ler_bytes(XML, "a.xml")
    assert len(cv.artigos) == 17 and cv.licencas


def test_detecta_pelo_conteudo_e_nao_pela_extensao():
    assert ler_bytes(XML, "nome_errado.html").licencas


def test_xhtml_com_declaracao_xml_continua_html():
    dados = b'<?xml version="1.0" encoding="UTF-8"?><html><body><p>nada</p></body></html>'
    cv = ler_bytes(dados, "x.html")
    assert cv.artigos == [] and any("Nenhum artigo encontrado no HTML" in a for a in cv.avisos)


def test_zip_com_um_xml():
    assert len(ler_bytes(_zip({"curriculo.xml": XML}), "cv.zip").artigos) == 17


@pytest.mark.parametrize("conteudo", [{}, {"a.xml": XML, "b.xml": XML}, {"leia.txt": b"oi"}])
def test_zip_sem_exatamente_um_xml_levanta(conteudo):
    with pytest.raises(ArquivoInvalido, match="exatamente um arquivo .xml"):
        ler_bytes(_zip(conteudo), "cv.zip")


def test_zip_corrompido_levanta():
    with pytest.raises(ArquivoInvalido, match="corrompido"):
        ler_bytes(b"PK\x03\x04" + b"lixo" * 10, "cv.zip")


def test_zip_grande_demais_levanta(monkeypatch):
    monkeypatch.setattr(entrada, "LIMITE_DESCOMPACTADO", 10)
    with pytest.raises(ArquivoInvalido, match="grande demais"):
        ler_bytes(_zip({"curriculo.xml": XML}), "cv.zip")


def test_ler_arquivo_do_disco():
    cv = ler_arquivo(FIXTURES / "artigos_completos.xml")
    assert len(cv.artigos) == 17
    assert cv.arquivo.endswith("artigos_completos.xml")


def _zip_com_flag_de_criptografia(dados: bytes) -> bytes:
    bruto = bytearray(_zip({"curriculo.xml": dados}))
    # bit 0 das "general purpose flags": no cabeçalho local (offset 6) e no central (offset 8)
    bruto[6] |= 1
    central = bruto.find(b"PK\x01\x02")
    bruto[central + 8] |= 1
    return bytes(bruto)


def _zip_deflate_corrompido() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
        arquivo_zip.writestr("curriculo.xml", XML)
    bruto = bytearray(buffer.getvalue())
    inicio = 30 + len("curriculo.xml")  # dados comprimidos logo após o cabeçalho local
    bruto[inicio : inicio + 40] = b"\xff" * 40
    return bytes(bruto)


@pytest.mark.parametrize("dados", [_zip_com_flag_de_criptografia(XML), _zip_deflate_corrompido()])
def test_zip_criptografado_ou_corrompido_levanta(dados):
    with pytest.raises(ArquivoInvalido):
        ler_bytes(dados, "cv.zip")


def test_zip_com_xml_utf16_e_entidade_levanta():
    xml = (
        '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY a "AAAA">]>'
        '<CURRICULO-VITAE><DADOS-GERAIS NOME-COMPLETO="&a;"/></CURRICULO-VITAE>'
    ).encode("utf-16")
    with pytest.raises(ArquivoInvalido):
        ler_bytes(_zip({"curriculo.xml": xml}), "cv.zip")
