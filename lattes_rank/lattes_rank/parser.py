"""Leitura do HTML do Currículo Lattes.

Aceita a página inteira salva com Ctrl+S ou apenas o trecho copiado do F12
(``div#artigos-completos``). Cada artigo é um ``div.artigo-completo`` e traz,
no atributo ``cvuri`` do ``span.citado``, o ISSN, o DOI, o título e o nome do
periódico. O ano vem num ``span`` próprio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag

from .issn import normalizar_issn


@dataclass(frozen=True)
class Artigo:
    sequencia: int | None
    ano: int | None
    titulo: str | None
    periodico_nome: str | None
    issn_bruto: str | None
    issn: str | None  # normalizado
    doi: str | None


@dataclass
class Curriculo:
    arquivo: str
    id_lattes: str | None
    nome: str | None
    data_atualizacao: str | None
    artigos: list[Artigo] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def decodificar_html(dados: bytes) -> str:
    """UTF-8 primeiro; se falhar, usa o charset declarado e por fim cp1252.

    A ordem importa: já vimos página salva em UTF-8 que declara
    ``windows-1252`` no <meta>, então confiar só no <meta> estraga os acentos.
    """
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    candidatos: list[str] = []
    achado = re.search(rb"charset=[\"']?([A-Za-z0-9_\-]+)", dados[:4096])
    if achado:
        candidatos.append(achado.group(1).decode("ascii"))
    candidatos.append("cp1252")
    for codificacao in candidatos:
        try:
            return dados.decode(codificacao)
        except (UnicodeDecodeError, LookupError):
            continue
    return dados.decode("latin-1")


def _parametro(cvuri: str, nome: str) -> str | None:
    achado = re.search(rf"[?&]{nome}=([^&]*)", cvuri)
    if not achado:
        return None
    return achado.group(1).strip() or None


def _titulo(cvuri: str) -> str | None:
    # O título é texto livre e pode conter "&"; ele termina antes de &sequencial=.
    achado = re.search(r"[?&]titulo=(.*?)&sequencial=", cvuri, flags=re.DOTALL)
    return (achado.group(1).strip() or None) if achado else None


def _nome_periodico(cvuri: str) -> str | None:
    # É o último parâmetro; pega até o fim.
    achado = re.search(r"[?&]nomePeriodico=(.*)$", cvuri, flags=re.DOTALL)
    return (achado.group(1).strip() or None) if achado else None


def _texto(tag: Tag | None) -> str:
    return tag.get_text(strip=True) if tag else ""


def _extrair_artigo(bloco: Tag, avisos: list[str]) -> Artigo:
    cvuri = ""
    span_citado = bloco.select_one("span.citado")
    if span_citado is not None:
        cvuri = span_citado.get("cvuri", "") or ""

    # Sequência ("17. ")
    sequencia = None
    achado_seq = re.match(r"\s*(\d+)", _texto(bloco.select_one("b")))
    if achado_seq:
        sequencia = int(achado_seq.group(1))
    rotulo = f"artigo {sequencia}" if sequencia is not None else "artigo sem número"

    # ISSN: cvuri é a fonte principal; data-issn do selo JCR é reserva.
    issn_bruto = _parametro(cvuri, "issn")
    if issn_bruto is None:
        img_jcr = bloco.select_one("img[data-issn]")
        if img_jcr is not None:
            issn_bruto = (img_jcr.get("data-issn") or "").strip() or None

    # DOI: cvuri, ou o link do ícone DOI.
    doi = _parametro(cvuri, "doi")
    if doi is None:
        link_doi = bloco.select_one("a.icone-doi")
        if link_doi is not None:
            achado_doi = re.search(r"doi\.org/(.+)$", link_doi.get("href", "") or "")
            if achado_doi:
                doi = achado_doi.group(1).strip() or None

    # Ano: span próprio; reserva = último "AAAA." do texto da citação.
    ano = None
    texto_ano = _texto(bloco.select_one('span.informacao-artigo[data-tipo-ordenacao="ano"]'))
    if re.fullmatch(r"\d{4}", texto_ano):
        ano = int(texto_ano)
    else:
        anos = re.findall(r"[,\s](\d{4})\.", bloco.get_text(" ", strip=True))
        if anos:
            ano = int(anos[-1])
            avisos.append(f"{rotulo}: ano lido do texto da citação ({ano}).")
        else:
            avisos.append(f"{rotulo}: ano não encontrado.")

    if not cvuri:
        avisos.append(f"{rotulo}: sem dados de citação (cvuri); ISSN pode estar ausente.")

    return Artigo(
        sequencia=sequencia,
        ano=ano,
        titulo=_titulo(cvuri),
        periodico_nome=_nome_periodico(cvuri),
        issn_bruto=issn_bruto,
        issn=normalizar_issn(issn_bruto),
        doi=doi,
    )


def interpretar_html(html: str, arquivo: str = "<memória>") -> Curriculo:
    soup = BeautifulSoup(html, "html.parser")
    avisos: list[str] = []

    if html.count("�") >= 5:
        avisos.append(
            "O arquivo contém caracteres de substituição (acentos perdidos). "
            "ISSN, ano e DOI não são afetados; nomes e títulos sim."
        )

    # Cabeçalho (ausente quando só o trecho da seção foi copiado)
    nome = _texto(soup.select_one("h2.nome")) or None
    info = soup.select_one(".infpessoa")
    texto_info = info.get_text(" ", strip=True) if info is not None else ""
    achado_id = re.search(r"ID Lattes:\s*(\d{16})", texto_info) or re.search(
        r"lattes\.cnpq\.br/(\d{16})", texto_info
    )
    achado_data = re.search(r"curr.culo\s+em\s+(\d{2}/\d{2}/\d{4})", texto_info)

    # Só a seção de artigos em periódicos; outras seções não usam a classe,
    # mas restringir evita surpresas se o Lattes mudar isso.
    raiz = soup.select_one("#artigos-completos")
    if raiz is not None:
        blocos = raiz.select(".artigo-completo")
    else:
        blocos = soup.select(".artigo-completo")
        avisos.append(
            "Seção #artigos-completos não encontrada; usei todos os blocos .artigo-completo."
        )
    if not blocos:
        avisos.append("Nenhum artigo encontrado no HTML.")

    artigos = [_extrair_artigo(bloco, avisos) for bloco in blocos]
    return Curriculo(
        arquivo=arquivo,
        id_lattes=achado_id.group(1) if achado_id else None,
        nome=nome,
        data_atualizacao=achado_data.group(1) if achado_data else None,
        artigos=artigos,
        avisos=avisos,
    )


def ler_curriculo(caminho: str | Path) -> Curriculo:
    caminho = Path(caminho)
    return interpretar_html(decodificar_html(caminho.read_bytes()), arquivo=str(caminho))
