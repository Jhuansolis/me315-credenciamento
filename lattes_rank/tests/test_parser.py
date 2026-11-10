from lattes_rank.parser import decodificar_html, interpretar_html

ISSNS_ESPERADOS = [
    "03777332", "1093474X", "19845146", "16790731", "15372707", "1099131X", "19845146", "24523062",
    "01692070", "01692070", "09275398", "22251146", "00036846", "00949655", "00949655", "03784754", "18130194",
]
ANOS_ESPERADOS = [2026, 2026, 2025, 2024, 2023, 2023, 2023, 2023, 2021, 2019, 2019, 2019, 2019, 2018, 2017, 2015, 2009]


def test_le_os_17_artigos(curriculo):
    assert len(curriculo.artigos) == 17
    assert [a.sequencia for a in curriculo.artigos] == list(range(1, 18))
    assert curriculo.avisos == []  # trecho sem cabeçalho nem problemas


def test_issn_e_ano(curriculo):
    assert [a.issn for a in curriculo.artigos] == ISSNS_ESPERADOS
    assert [a.ano for a in curriculo.artigos] == ANOS_ESPERADOS


def test_artigo_sem_doi_e_sem_selo_jcr_mantem_issn(curriculo):
    ultimo = curriculo.artigos[-1]
    assert ultimo.doi is None
    assert ultimo.issn == "18130194"
    assert ultimo.periodico_nome == "ECIPERU"


def test_artigo_com_doi_titulo_e_periodico(curriculo):
    primeiro = curriculo.artigos[0]
    assert primeiro.doi == "10.1007/s00181-026-02900-x"
    assert primeiro.titulo.startswith("Hierarchical risk clustering versus")
    assert primeiro.periodico_nome == "Empirical Economics"


def test_periodico_com_nome_duplo_e_acento(curriculo):
    rbf = curriculo.artigos[2]
    assert rbf.periodico_nome == "REVISTA BRASILEIRA DE FINANÇAS: RBFIN = RBFIN: BRAZILIAN FINANCE REVIEW"


def test_titulo_com_e_comercial_nao_quebra_os_outros_campos():
    html = (
        '<div id="artigos-completos"><div class="artigo-completo"><b>1. </b>'
        '<span class="informacao-artigo" data-tipo-ordenacao="ano">2023</span>'
        '<span class="citado" cvuri="/x?doi=10.1/abc&amp;issn=03777332&amp;volume=1&amp;issue=&amp;paginaInicial=1'
        '&amp;titulo=Risk &amp; Return: a study&amp;sequencial=1&amp;nomePeriodico=Journal A &amp; B"></span></div></div>'
    )
    artigo = interpretar_html(html).artigos[0]
    assert artigo.issn == "03777332"
    assert artigo.doi == "10.1/abc"
    assert artigo.titulo == "Risk & Return: a study"
    assert artigo.periodico_nome == "Journal A & B"


def test_issn_reserva_pelo_selo_jcr_e_ano_reserva_pelo_texto():
    html = (
        '<div id="artigos-completos"><div class="artigo-completo"><b>3. </b>'
        '<span class="transform">A. Autor. Um título. Revista X<sup><img class="ajaxJCR" data-issn="1099131X"></sup>, v. 1, p. 2, 2022.</span></div></div>'
    )
    curriculo = interpretar_html(html)
    artigo = curriculo.artigos[0]
    assert artigo.issn == "1099131X"
    assert artigo.ano == 2022
    assert any("ano lido do texto" in aviso for aviso in curriculo.avisos)
    assert any("cvuri" in aviso for aviso in curriculo.avisos)


def test_usa_so_a_secao_de_artigos():
    html = (
        '<div class="artigo-completo"><b>1. </b><span class="informacao-artigo" data-tipo-ordenacao="ano">2020</span></div>'
        '<div id="artigos-completos"><div class="artigo-completo"><b>1. </b>'
        '<span class="informacao-artigo" data-tipo-ordenacao="ano">2024</span></div></div>'
    )
    artigos = interpretar_html(html).artigos
    assert [a.ano for a in artigos] == [2024]


def test_sem_a_secao_usa_todos_os_blocos_e_avisa():
    html = '<div class="artigo-completo"><b>1. </b><span class="informacao-artigo" data-tipo-ordenacao="ano">2020</span></div>'
    curriculo = interpretar_html(html)
    assert len(curriculo.artigos) == 1
    assert any("#artigos-completos" in aviso for aviso in curriculo.avisos)


def test_html_sem_artigos_avisa():
    assert any("Nenhum artigo" in a for a in interpretar_html("<html></html>").avisos)


def test_cabecalho_do_curriculo():
    html = (
        '<div class="infpessoa"><h2 class="nome">Fulana de Tal</h2><ul class="informacoes-autor">'
        "<li>Endereço para acessar este CV: http://lattes.cnpq.br/9315014843913122</li>"
        '<li>ID Lattes: <span>9315014843913122</span></li>'
        "<li>Última atualização do currículo em 26/10/2026</li></ul></div>"
        '<div id="artigos-completos"></div>'
    )
    cv = interpretar_html(html)
    assert (cv.nome, cv.id_lattes, cv.data_atualizacao) == ("Fulana de Tal", "9315014843913122", "26/10/2026")


def test_decodifica_utf8_mesmo_com_meta_windows_1252(html_artigos):
    # Caso real: página salva em UTF-8 declarando windows-1252.
    dados = ('<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">' + html_artigos).encode("utf-8")
    assert "FINANÇAS" in decodificar_html(dados)


def test_decodifica_cp1252(html_artigos):
    dados = ('<meta charset="windows-1252">' + html_artigos).encode("cp1252")
    texto = decodificar_html(dados)
    assert "FINANÇAS" in texto
    assert [a.issn for a in interpretar_html(texto).artigos] == ISSNS_ESPERADOS


def test_avisa_quando_acentos_foram_perdidos():
    html = "<div>" + "�" * 10 + '</div><div id="artigos-completos"></div>'
    assert any("acentos perdidos" in a for a in interpretar_html(html).avisos)
