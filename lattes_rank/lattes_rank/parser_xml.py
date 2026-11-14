"""Leitura do XML do Currículo Lattes (exportado pelo próprio docente).

Monta o mesmo ``Curriculo``/``Artigo`` do leitor de HTML. Só lê o cabeçalho
(ID, nome, data de atualização), o PcD, as licenças e os artigos publicados:
os dados pessoais do XML (CPF, documentos, filiação, endereço) são ignorados.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .issn import normalizar_issn
from .parser import Artigo, Curriculo, Licenca


class ArquivoInvalido(ValueError):
    """Arquivo enviado que não dá para ler como currículo Lattes."""


def _valor(elemento: ET.Element | None, atributo: str) -> str | None:
    if elemento is None:
        return None
    return (elemento.get(atributo) or "").strip() or None


def _data(ddmmaaaa: str | None) -> str | None:
    if ddmmaaaa is None or not re.fullmatch(r"\d{8}", ddmmaaaa):
        return None
    return f"{ddmmaaaa[:2]}/{ddmmaaaa[2:4]}/{ddmmaaaa[4:]}"


def _artigo(sequencia: int, elemento: ET.Element, avisos: list[str]) -> Artigo:
    basicos = elemento.find("DADOS-BASICOS-DO-ARTIGO")
    detalhes = elemento.find("DETALHAMENTO-DO-ARTIGO")
    texto_ano = _valor(basicos, "ANO-DO-ARTIGO")
    ano = int(texto_ano) if texto_ano and re.fullmatch(r"\d{4}", texto_ano) else None
    if ano is None:
        avisos.append(f"artigo {sequencia}: ano não encontrado.")
    issn_bruto = _valor(detalhes, "ISSN")
    return Artigo(
        sequencia=sequencia,
        ano=ano,
        titulo=_valor(basicos, "TITULO-DO-ARTIGO"),
        periodico_nome=_valor(detalhes, "TITULO-DO-PERIODICO-OU-REVISTA"),
        issn_bruto=issn_bruto,
        issn=normalizar_issn(issn_bruto),
        doi=_valor(basicos, "DOI"),
    )


def interpretar_xml(dados: bytes, arquivo: str = "<memória>") -> Curriculo:
    # O Lattes não usa DTD nem entidades; recusar evita expansão de entidades maliciosas.
    if b"<!DOCTYPE" in dados or b"<!ENTITY" in dados:
        raise ArquivoInvalido("O XML enviado não é um currículo Lattes.")
    try:
        # bytes: o ElementTree respeita o encoding declarado (ISO-8859-1 no Lattes)
        raiz = ET.fromstring(dados)
    except ET.ParseError as erro:
        raise ArquivoInvalido("O arquivo XML está corrompido ou incompleto.") from erro
    if raiz.tag != "CURRICULO-VITAE":
        raise ArquivoInvalido("O XML enviado não é um currículo Lattes.")

    avisos: list[str] = []
    gerais = raiz.find("DADOS-GERAIS")
    artigos = [
        _artigo(i, elemento, avisos)
        for i, elemento in enumerate(raiz.iterfind(".//ARTIGOS-PUBLICADOS/ARTIGO-PUBLICADO"), start=1)
    ]
    if not artigos:
        avisos.append("Nenhum artigo encontrado no XML.")
    licencas = [
        Licenca(
            tipo=_valor(lic, "TIPO-LICENCA") or "(tipo não informado)",
            inicio=_data(_valor(lic, "DATA-INICIO-LICENCA")),
            fim=_data(_valor(lic, "DATA-FIM-LICENCA")),
        )
        for lic in raiz.iterfind("DADOS-GERAIS/LICENCAS/LICENCA")
    ]
    return Curriculo(
        arquivo=arquivo,
        id_lattes=_valor(raiz, "NUMERO-IDENTIFICADOR"),
        nome=_valor(gerais, "NOME-COMPLETO"),
        data_atualizacao=_data(_valor(raiz, "DATA-ATUALIZACAO")),
        artigos=artigos,
        avisos=avisos,
        licencas=licencas,
        pcd=_valor(gerais, "PCD"),
    )
