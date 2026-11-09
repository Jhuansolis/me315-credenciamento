"""Montagem das tabelas finais e carga no SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import limpeza, percentil
from .config import CATEGORIA_AREA_MANUAL, LIMIAR_CONCORDANCIA_QUARTIL
from .leitura import ArquivoFonte

SCHEMA = Path(__file__).with_name("schema.sql")


def _nulos(df: pd.DataFrame) -> list[tuple]:
    """Converte pd.NA/NaN em None para o sqlite3."""
    return [tuple(None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in linha)
            for linha in df.itertuples(index=False, name=None)]


def inferir_area_das_categorias(cat: pd.DataFrame, areas: pd.DataFrame) -> pd.Series:
    """Área "dona" de cada categoria = interseção das áreas de todos os periódicos dela
    (somando todos os anos). Se a interseção tiver exatamente 1 área, é ela; senão NULL.

    Categorias ambíguas (todos os periódicos também estão em outra área, ex.: Respiratory
    Care sempre junto com Medicine) usam o mapeamento manual de config.CATEGORIA_AREA_MANUAL,
    que tem prioridade sobre a inferência."""
    areas_por_per = areas.groupby(["sourceid", "ano"])["area"].agg(frozenset)
    j = cat[["sourceid", "ano", "categoria"]].join(areas_por_per, on=["sourceid", "ano"])
    inter = j.groupby("categoria")["area"].agg(lambda s: frozenset.intersection(*s))
    dona = inter.map(lambda s: next(iter(s)) if len(s) == 1 else None).astype(object)
    for categoria, area in CATEGORIA_AREA_MANUAL.items():
        if categoria in dona.index:
            dona[categoria] = area
    return dona.where(dona.notna(), None)


def montar_tabelas(bruto: pd.DataFrame, arquivos: list[ArquivoFonte], metodo: str, empates: str) -> dict:
    df = limpeza.limpar(bruto)
    unica, inconsist = limpeza.deduplicar(df)

    cat = percentil.calcular(limpeza.explodir_categorias(unica), metodo, empates)
    areas = limpeza.explodir_areas(unica, df)
    issn = limpeza.explodir_issn(unica)

    # --- dimensões
    nomes_area = sorted(set(areas["area"]) | {a.area for a in arquivos})
    area_id = {n: i + 1 for i, n in enumerate(nomes_area)}
    area_da_cat = inferir_area_das_categorias(cat, areas)
    nomes_cat = sorted(cat["categoria"].unique())
    cat_id = {n: i + 1 for i, n in enumerate(nomes_cat)}
    t_categoria = pd.DataFrame({
        "id": [cat_id[n] for n in nomes_cat],
        "nome": nomes_cat,
        "area_id": [area_id.get(area_da_cat.get(n)) for n in nomes_cat],
    })

    # --- periódico: cadastro do ano mais recente
    recente = unica.sort_values("ano").groupby("sourceid").tail(1)
    anos = unica.groupby("sourceid")["ano"].agg(["min", "max"])
    t_periodico = recente.assign(
        primeiro_ano=recente["sourceid"].map(anos["min"]),
        ultimo_ano=recente["sourceid"].map(anos["max"]),
    )[["sourceid", "titulo_limpo", "tipo", "publisher", "pais", "regiao", "cobertura",
       "cobertura_inicio", "cobertura_fim", "descontinuado", "primeiro_ano", "ultimo_ano"]]

    t_issn = issn.drop_duplicates(["issn", "sourceid"])[["issn", "sourceid"]]
    t_issn.insert(1, "issn_formatado", t_issn["issn"].map(limpeza.formatar_issn))

    t_metrica = unica[["sourceid", "ano", "titulo", "sjr", "quartil_melhor", "h_index", "total_docs_ano",
                       "total_docs_3anos", "total_refs", "total_citacoes_3anos", "docs_citaveis_3anos",
                       "citacoes_por_doc_2anos", "refs_por_doc", "pct_feminino", "overton",
                       "open_access", "open_access_diamond"]]

    t_area_ano = areas.assign(area_id=areas["area"].map(area_id))[["sourceid", "ano", "area_id", "rank_area", "quartil_melhor_na_area"]]

    cat["categoria_id"] = cat["categoria"].map(cat_id)
    t_pca = cat[["sourceid", "ano", "categoria_id", "quartil_scimago", "posicao", "n_categoria",
                 "n_empatados", "percentil"]]

    # --- qualidade por categoria/ano
    cat["quartil_calc"] = limpeza.quartil_por_posicao(cat["posicao"].astype("Float64"),
                                                      cat["n_categoria"].astype("Float64"))
    comparavel = cat["quartil_calc"].notna() & cat["quartil_scimago"].notna()
    cat["concorda"] = (cat["quartil_calc"] == cat["quartil_scimago"]).where(comparavel)
    cat["em_empate"] = (cat["n_empatados"] > 1).fillna(False).astype(int)
    q = cat.groupby(["ano", "categoria"]).agg(
        n_periodicos=("sourceid", "size"),
        n_com_sjr=("sjr", "count"),
        n_em_empate=("em_empate", "sum"),
        concordancia_quartil=("concorda", "mean"),
    ).reset_index()
    carregados = {(a.ano, a.area) for a in arquivos}
    dona = q["categoria"].map(area_da_cat)
    # pd.isna e não "is None": o .map devolve NaN para área desconhecida, o que antes
    # fazia uma área não inferida ser lida como "área não carregada" (falso ERRO).
    q["area_carregada"] = [None if pd.isna(d) else int((ano, d) in carregados)
                           for ano, d in zip(q["ano"], dona)]
    q["incompleta"] = (q["area_carregada"] == 0).astype(int)
    q["diverge_do_scimago"] = ((q["incompleta"] == 0) &
                               (q["concordancia_quartil"] < LIMIAR_CONCORDANCIA_QUARTIL)).astype(int)
    q["categoria_id"] = q["categoria"].map(cat_id)
    t_qualidade = q[["ano", "categoria_id", "n_periodicos", "n_com_sjr", "n_em_empate", "concordancia_quartil",
                     "area_carregada", "incompleta", "diverge_do_scimago"]]

    # ISSN ligado a mais de um sourceid (fusão/cisão de periódicos) -> só reportar.
    colisoes = t_issn.groupby("issn")["sourceid"].nunique()
    return {
        "area": pd.DataFrame({"id": list(area_id.values()), "nome": list(area_id.keys())}),
        "categoria": t_categoria,
        "periodico": t_periodico,
        "periodico_issn": t_issn,
        "metrica_anual": t_metrica,
        "periodico_area_ano": t_area_ano,
        "periodico_categoria_ano": t_pca,
        "qualidade_categoria_ano": t_qualidade,
        "_extras": {
            "inconsistencias": inconsist,
            "issn_colisoes": colisoes[colisoes > 1],
            "sem_issn": unica.loc[unica["issns"].str.len() == 0, ["sourceid", "ano", "titulo", "issn_bruto"]],
            "linhas_brutas": len(df),
            "pares_unicos": len(unica),
            "qualidade": q,
        },
    }


def gravar(caminho_db: str | Path, tabelas: dict, arquivos: list[ArquivoFonte],
           bruto: pd.DataFrame, metodo: str, empates: str) -> None:
    caminho_db = Path(caminho_db)
    if caminho_db.exists():
        caminho_db.unlink()   # carga idempotente: sempre recria
    con = sqlite3.connect(caminho_db)
    try:
        con.executescript(SCHEMA.read_text(encoding="utf-8"))
        agora = datetime.now().isoformat(timespec="seconds")
        contagem = bruto.groupby("arquivo").size()
        con.executemany("INSERT INTO arquivo_fonte(nome, ano, area, n_linhas, carregado_em) VALUES (?,?,?,?,?)",
                        [(a.caminho.name, a.ano, a.area, int(contagem.get(a.caminho.name, 0)), agora)
                         for a in arquivos])
        ordem = ["area", "categoria", "periodico", "periodico_issn", "metrica_anual",
                 "periodico_area_ano", "periodico_categoria_ano", "qualidade_categoria_ano"]
        for nome in ordem:
            df = tabelas[nome]
            cols = ",".join(_colunas_destino(con, nome))
            marc = ",".join("?" * df.shape[1])
            con.executemany(f"INSERT INTO {nome}({cols}) VALUES ({marc})", _nulos(df))
        con.executemany("INSERT INTO metadado_carga VALUES (?,?)", [
            ("metodo_percentil", metodo),
            ("regra_empate", empates),
            ("limiar_concordancia", str(LIMIAR_CONCORDANCIA_QUARTIL)),
            ("carregado_em", agora),
            ("n_arquivos", str(len(arquivos))),
        ])
        con.commit()
    finally:
        con.close()


def _colunas_destino(con: sqlite3.Connection, tabela: str) -> list[str]:
    """Colunas da tabela na ordem do schema (o DataFrame é montado na mesma ordem)."""
    return [r[1] for r in con.execute(f"PRAGMA table_info({tabela})")]
