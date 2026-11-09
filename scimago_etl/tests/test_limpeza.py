from pathlib import Path

import pandas as pd
import pytest

from scimago_etl import limpeza, percentil
from scimago_etl.leitura import identificar_arquivo


@pytest.mark.parametrize("nome, ano, area", [
    ("scimagojr 2022 Subject Area - Biochemistry, Genetics and Molecular Biology.csv", 2022,
     "Biochemistry, Genetics and Molecular Biology"),
    ("f32cd9b2-scimagojr_2024_Subject_Area_-_Biochemistry_Genetics_and_Molecular_Biology.csv", 2024,
     "Biochemistry, Genetics and Molecular Biology"),
    ("scimagojr 2025 Subject Area - Computer Science.csv", 2025, "Computer Science"),
])
def test_nome_arquivo(nome, ano, area):
    a = identificar_arquivo(Path(nome))
    assert (a.ano, a.area, a.area_reconhecida) == (ano, area, True)


def test_nome_fora_do_padrao():
    assert identificar_arquivo(Path("notas.csv")) is None


def test_issn():
    assert limpeza.normalizar_issn("2157846x, 0007-9235") == ["2157846X", "00079235"]
    assert limpeza.normalizar_issn("-") == []
    assert limpeza.normalizar_issn("") == []
    assert limpeza.normalizar_issn("123") == []
    assert limpeza.formatar_issn("2157846X") == "2157-846X"


def test_categorias():
    t = "Medicine (miscellaneous) (Q1); Genetics (Q3); Information Systems"
    assert limpeza.separar_categorias(t) == [
        ("Medicine (miscellaneous)", "Q1"), ("Genetics", "Q3"), ("Information Systems", None)]
    assert limpeza.melhor_quartil_global(t) == "Q1"
    assert limpeza.melhor_quartil_global("Pollution; Energy") is None


def test_decimal_e_bool():
    assert limpeza.para_decimal(pd.Series(["8,997", "", "-"])).tolist()[0] == pytest.approx(8.997)
    assert limpeza.para_decimal(pd.Series(["", "-"])).isna().all()
    assert limpeza.para_bool(pd.Series(["Yes", "No"])).tolist() == [1, 0]


def test_cobertura():
    assert limpeza.faixa_cobertura("2014-2016, 2018-2026") == (2014, 2026)
    assert limpeza.faixa_cobertura("") == (None, None)


def _cat(sjrs):
    return pd.DataFrame({"sourceid": range(len(sjrs)), "ano": 2025, "categoria": "X", "sjr": sjrs})


def test_percentil_topo_100_com_empate_e_sem_sjr():
    r = percentil.calcular(_cat([5.0, 3.0, 3.0, 1.0, None]), "topo_100")
    assert r["posicao"].tolist()[:4] == [1, 2, 2, 4]
    assert r["n_categoria"].tolist()[:4] == [4, 4, 4, 4]
    assert r["percentil"].tolist()[:4] == [100.0, 75.0, 75.0, 25.0]
    assert pd.isna(r["percentil"].iloc[4])


def test_empates_melhor_vs_media_e_n_empatados():
    melhor = percentil.calcular(_cat([5.0, 3.0, 3.0, 1.0]), "topo_100", "melhor")
    media = percentil.calcular(_cat([5.0, 3.0, 3.0, 1.0]), "topo_100", "media")
    assert melhor["posicao"].tolist() == [1, 2, 2, 4]
    assert media["posicao"].tolist() == [1, 2.5, 2.5, 4]
    assert melhor["n_empatados"].tolist() == [1, 2, 2, 1]
    assert melhor["percentil"].iloc[1] > media["percentil"].iloc[1]   # melhor favorece o empatado


def test_percentil_linear():
    r = percentil.calcular(_cat([5.0, 3.0, 1.0]), "linear_0_100")
    assert r["percentil"].tolist() == [100.0, 50.0, 0.0]
    assert percentil.calcular(_cat([2.0]), "linear_0_100")["percentil"].tolist() == [100.0]


def test_percentil_por_ano_e_categoria_separados():
    df = pd.DataFrame({"sourceid": [1, 2, 1, 2], "ano": [2024, 2024, 2025, 2025],
                       "categoria": "X", "sjr": [1.0, 2.0, 3.0, 0.5]})
    r = percentil.calcular(df)
    assert r["posicao"].tolist() == [2, 1, 1, 2]


def test_dedup_quartil_global():
    base = dict(titulo="J", sjr=0.65, h_index=90, total_docs_ano=1, issn_bruto="1", areas_bruto="A; B",
                categorias_bruto="Chem (Q2); Biochemistry (Q3)", issns=[["00000001"]])
    df = pd.DataFrame([{**base, "sourceid": 1, "ano": 2025, "area_arquivo": "A", "quartil_melhor": "Q3"},
                       {**base, "sourceid": 1, "ano": 2025, "area_arquivo": "B", "quartil_melhor": "Q2"}])
    unica, inc = limpeza.deduplicar(df)
    assert len(unica) == 1 and unica["quartil_melhor"].iloc[0] == "Q2" and inc.empty


# ---------------------------------------------------------------- regressão: categoria ambígua
def _linha_bruta(sourceid, area_arquivo, categorias, areas, sjr="1,000", ano=2025):
    from scimago_etl.config import COLUNAS
    linha = {c: "" for c in COLUNAS.values()}
    linha.update(rank_area="1", sourceid=str(sourceid), titulo=f"J{sourceid}", tipo="journal",
                 issn_bruto=f"0000000{sourceid}", open_access="No", open_access_diamond="No",
                 sjr=sjr, quartil_melhor="Q1", h_index="1", total_docs_3anos="1", total_refs="1",
                 total_citacoes_3anos="1", docs_citaveis_3anos="1", overton="0", cobertura="2020-2026",
                 categorias_bruto=categorias, areas_bruto=areas)
    linha.update(total_docs_ano="1", ano=ano, area_arquivo=area_arquivo, arquivo=f"{ano}-{area_arquivo}.csv")
    return linha


def test_categoria_ambigua_nao_vira_erro():
    """Periódicos de 'Cat Ambigua' estão sempre em A e B -> área não inferível.
    Isso não pode ser marcado como 'incompleta'. Antes, quando havia também categorias
    com área conhecida, o pandas 3 convertia o None em NaN e gerava um falso ERRO."""
    from scimago_etl import banco
    from scimago_etl.leitura import ArquivoFonte
    linhas = []
    for sid in (1, 2):
        for area in ("Area A", "Area B"):
            linhas.append(_linha_bruta(sid, area, "Cat Ambigua (Q1)", "Area A; Area B", sjr=f"{sid},000"))
    linhas.append(_linha_bruta(3, "Area A", "Cat Clara (Q1)", "Area A"))   # categoria com área conhecida
    bruto = pd.DataFrame(linhas)
    arquivos = [ArquivoFonte(Path(f"{a}.csv"), 2025, a, False) for a in ("Area A", "Area B")]
    t = banco.montar_tabelas(bruto, arquivos, "topo_100", "melhor")
    cats = t["categoria"].set_index("nome")["area_id"]
    assert pd.isna(cats["Cat Ambigua"]) and not pd.isna(cats["Cat Clara"])
    q = t["qualidade_categoria_ano"].assign(nome=lambda d: d["categoria_id"].map(t["categoria"].set_index("id")["nome"]))
    q = q.set_index("nome")
    assert q.loc["Cat Ambigua", "incompleta"] == 0
    assert pd.isna(q.loc["Cat Ambigua", "area_carregada"])
    assert q.loc["Cat Clara", "area_carregada"] == 1


def test_mapeamento_manual_de_categoria(monkeypatch):
    from scimago_etl import banco
    monkeypatch.setattr(banco, "CATEGORIA_AREA_MANUAL", {"Cat Ambigua": "Area B"})
    cat = pd.DataFrame({"sourceid": [1, 2], "ano": 2025, "categoria": "Cat Ambigua"})
    areas = pd.DataFrame({"sourceid": [1, 1, 2, 2], "ano": 2025, "area": ["Area A", "Area B"] * 2})
    assert banco.inferir_area_das_categorias(cat, areas)["Cat Ambigua"] == "Area B"
