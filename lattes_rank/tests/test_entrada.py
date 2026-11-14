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
