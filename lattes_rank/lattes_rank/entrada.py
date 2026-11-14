"""Entrada única: lê o currículo Lattes em HTML, XML ou ZIP (com o XML dentro).

O formato é detectado pelo conteúdo, não pela extensão do arquivo.
"""

from __future__ import annotations

import io
import zipfile
import zlib
from pathlib import Path

from .parser import Curriculo, decodificar_html, interpretar_html
from .parser_xml import ArquivoInvalido, interpretar_xml

__all__ = ["ArquivoInvalido", "LIMITE_DESCOMPACTADO", "ler_arquivo", "ler_bytes"]

LIMITE_DESCOMPACTADO = 20 * 1024 * 1024  # um currículo XML real tem centenas de KB
_ASSINATURAS_ZIP = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")  # normal, vazio, "spanned"


def _xml_do_zip(dados: bytes) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as arquivo_zip:
            membros = [
                m for m in arquivo_zip.infolist() if not m.is_dir() and m.filename.lower().endswith(".xml")
            ]
            if len(membros) != 1:
                raise ArquivoInvalido("O ZIP deve conter exatamente um arquivo .xml do Lattes.")
            membro = membros[0]
            if membro.file_size > LIMITE_DESCOMPACTADO:
                raise ArquivoInvalido("O XML dentro do ZIP é grande demais.")
            with arquivo_zip.open(membro) as fluxo:
                conteudo = fluxo.read(LIMITE_DESCOMPACTADO + 1)
    except ArquivoInvalido:
        raise
    except (zipfile.BadZipFile, EOFError, zlib.error, ValueError) as erro:
        raise ArquivoInvalido("O arquivo ZIP está corrompido.") from erro
    except (RuntimeError, NotImplementedError) as erro:  # criptografado ou compressão sem suporte
        raise ArquivoInvalido("O ZIP está protegido por senha ou usa compressão não suportada.") from erro
    if len(conteudo) > LIMITE_DESCOMPACTADO:  # tamanho declarado no ZIP pode mentir
        raise ArquivoInvalido("O XML dentro do ZIP é grande demais.")
    return conteudo


def _parece_xml(dados: bytes) -> bool:
    inicio = dados[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    return inicio.startswith((b"<?xml", b"<curriculo-vitae")) and b"<html" not in inicio


def ler_bytes(dados: bytes, arquivo: str = "<memória>") -> Curriculo:
    if dados.startswith(_ASSINATURAS_ZIP):
        return interpretar_xml(_xml_do_zip(dados), arquivo)
    if _parece_xml(dados):
        return interpretar_xml(dados, arquivo)
    return interpretar_html(decodificar_html(dados), arquivo)


def ler_arquivo(caminho: str | Path) -> Curriculo:
    caminho = Path(caminho)
    return ler_bytes(caminho.read_bytes(), arquivo=str(caminho))
