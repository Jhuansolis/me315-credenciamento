import json

from lattes_rank.parser import Curriculo
from lattes_rank.ranking import avaliar_curriculo, politica_estendida
from lattes_rank.relatorio import formatar_texto, para_dict


def test_texto_tem_cabecalho_regras_e_contagens(curriculo, banco):
    texto = formatar_texto(avaliar_curriculo(curriculo, banco))
    assert "Docente: (nome não encontrado no HTML)" in texto  # a fixture é só a seção de artigos
    assert "Arquivo: fixture" in texto
    assert "REGRAS APLICADAS" in texto
    assert "Artigos considerados: artigos de 2022 a 2025; posteriores a 2025 nunca entram." in texto
    assert "maior percentil SJR entre 2022 e 2025" in texto
    assert "Artigos lidos: 17 | elegíveis pela regra de anos: 6" in texto
    assert "fora da regra de anos: 11" in texto


def test_marcas_de_empate_e_notas_de_rodape(curriculo, banco):
    texto = formatar_texto(avaliar_curriculo(curriculo, banco))
    linhas = texto.splitlines()
    jbes = next(l for l in linhas if "Journal of Business and Economic Statistics" in l)
    ecosta = next(l for l in linhas if "Econometrics and Statistics" in l and "97.00" not in l)
    rbf = next(l for l in linhas if "Revista Brasileira de Financas" in l)
    assert "97.00*" in jbes and "†" not in jbes  # empate de SJR (n_empatados = 3), sem empate de nota
    assert "88.00†" in ecosta and "*" not in ecosta
    assert "61.50 " in rbf  # nenhuma marca: n_empatados = 1 não é empate
    assert "† mesma nota" in texto and "* o percentil vem de um bloco de SJR empatado" in texto
    assert "posição 4 de 100, Q1 no SCImago, 3 periódicos com o mesmo SJR" in texto


def test_sem_empates_nao_ha_notas_de_rodape(banco):
    from lattes_rank.parser import Artigo

    cv = Curriculo("x", None, None, None, [Artigo(1, 2024, "t", "RBF", "19845146", "19845146", None)])
    texto = formatar_texto(avaliar_curriculo(cv, banco))
    assert "†" not in texto and "* o percentil" not in texto


def test_listas_auxiliares_e_fora_da_regra_agrupado_por_ano(curriculo, banco):
    texto = formatar_texto(avaliar_curriculo(curriculo, banco, politica_estendida(2022, 2025)))
    assert "NÃO LOCALIZADOS NA BASE" in texto and "ECIPERU" in texto
    assert "SEM PERCENTIL EM 2022-2025" in texto and "Journal of Statistical Computation and Simulation" in texto
    assert "FORA DA REGRA DE ANOS\n  2026 (2): Empirical Economics; JOURNAL OF THE AMERICAN WATER" in texto
    assert "(+" in texto  # há pontuados fora do top


def test_sem_artigos(banco):
    cv = Curriculo("vazio.html", None, None, None, [], ["Nenhum artigo encontrado no HTML."])
    texto = formatar_texto(avaliar_curriculo(cv, banco))
    assert "Nenhum periódico pontuado." in texto
    assert "AVISOS\n  - Nenhum artigo encontrado no HTML." in texto


def test_dict_para_json(curriculo, banco):
    dados = para_dict(avaliar_curriculo(curriculo, banco))
    json.dumps(dados, ensure_ascii=False)  # serializável
    assert dados["contagens"] == {
        "lidos": 17, "elegiveis": 6, "pontuado": 6, "fora_da_janela": 11, "nao_localizado": 0, "sem_percentil": 0,
    }
    assert dados["regra_de_anos"] == {"descricao": "artigos de 2022 a 2025", "ano_min": 2022, "ano_max": 2025}
    primeiro = dados["top"][0]
    assert (primeiro["empate_sjr"], primeiro["n_empatados"], primeiro["posicao_na_categoria"]) == (True, 3, 4.0)
    assert {a["codigo_motivo"] for a in dados["artigos"] if a["status"] == "fora_da_janela"} == {"fora_da_politica"}
