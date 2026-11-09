"""Uso:
    python -m scimago_etl --pasta "caminho/da/pasta" --banco scimago.db
    python -m scimago_etl --pasta dados --banco scimago.db --anos 2024 2025 --metodo-percentil linear_0_100
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from . import banco, leitura, percentil
from .config import (ANOS_PADRAO, AREAS_SCIMAGO, EMPATES_PADRAO, LIMIAR_CONCORDANCIA_QUARTIL,
                     METODO_PERCENTIL_PADRAO)


def relatorio(arquivos, tabelas, metodo: str, empates: str) -> str:
    ex = tabelas["_extras"]
    q = ex["qualidade"]
    L = ["# Relatório da carga SCImago", ""]
    L.append(f"- Método de percentil: `{metodo}`")
    L.append(f"- Arquivos lidos: {len(arquivos)}")
    L.append(f"- Linhas brutas: {ex['linhas_brutas']}  |  pares (periódico, ano) únicos: {ex['pares_unicos']}")
    L.append(f"- Periódicos distintos: {len(tabelas['periodico'])}  |  categorias: {len(tabelas['categoria'])}")
    L.append("")

    por_ano = defaultdict(set)
    for a in arquivos:
        por_ano[a.ano].add(a.area)
    L.append("## Cobertura de arquivos por ano")
    for ano in sorted(por_ano):
        faltam = [x for x in AREAS_SCIMAGO if x not in por_ano[ano]]
        if not faltam:
            L.append(f"- {ano}: 27/27 áreas")
        elif len(faltam) <= 5:
            L.append(f"- {ano}: {len(por_ano[ano])}/27 áreas — faltam: {'; '.join(faltam)}")
        else:
            L.append(f"- {ano}: {len(por_ano[ano])}/27 áreas — presentes: {'; '.join(sorted(por_ano[ano]))}")
    desconhecidas = sorted({a.area for a in arquivos if not a.area_reconhecida})
    if desconhecidas:
        L.append(f"- Áreas com nome não reconhecido: {desconhecidas}")
    L.append("")

    m = tabelas["metrica_anual"]
    L.append("## Métricas")
    for ano, g in m.groupby("ano"):
        L.append(f"- {ano}: {len(g)} periódicos, {g['sjr'].isna().sum()} sem SJR")
    L.append(f"- Periódicos descontinuados: {int(tabelas['periodico']['descontinuado'].sum())}")
    L.append(f"- Linhas sem ISSN válido: {len(ex['sem_issn'])}")
    L.append(f"- ISSN ligados a mais de um Sourceid: {len(ex['issn_colisoes'])}")
    L.append(f"- (Periódico, ano) com valores divergentes entre arquivos de área: {len(ex['inconsistencias'])}")
    L.append("")

    L.append("## Qualidade do percentil por categoria")
    L.append(f"- Regra de empate: `{empates}`")
    sem_area = tabelas["categoria"].loc[tabelas["categoria"]["area_id"].isna(), "nome"].tolist()
    L.append(f"- Categorias sem área dona (nem inferida, nem no mapeamento manual): {len(sem_area)}"
             + (f" — {'; '.join(sem_area[:10])}" if sem_area else ""))
    if sem_area:
        L.append("  Para corrigir, acrescente-as em CATEGORIA_AREA_MANUAL (config.py).")
    inc = q[q["incompleta"] == 1]
    L.append(f"- **ERRO** — pares (categoria, ano) com área dona não carregada: {len(inc)} de {len(q)}")
    if len(inc) > 10:
        L.append(f"  Mostrando os 10 maiores de {len(inc)}.")
    for r in inc.sort_values("n_com_sjr", ascending=False).head(10).itertuples():
        L.append(f"  - {r.ano} · {r.categoria} (n={r.n_com_sjr})")
    completas = q[q["incompleta"] == 0]
    if len(completas):
        L.append(f"- Concordância média de quartil com o SCImago: {completas['concordancia_quartil'].mean():.3f}")
        L.append(f"- Periódicos em empate de SJR (soma categoria×ano): {int(completas['n_em_empate'].sum())}")
    div = q[q["diverge_do_scimago"] == 1]
    grandes = div[div["n_com_sjr"] >= 30]
    L.append(f"- Informativo — divergem do quartil SCImago (< {LIMIAR_CONCORDANCIA_QUARTIL}): {len(div)} "
             f"pares, dos quais {len(grandes)} com 30+ periódicos")
    if len(grandes):
        L.append("  Causas prováveis: empates de SJR (3 casas decimais) ou universo maior no SCImago")
        L.append("  (anais/séries de livros). Ver DECISOES.md, D2 e D3.")
        if len(grandes) > 15:
            L.append(f"  Mostrando os 15 maiores de {len(grandes)} (lista completa: tabela qualidade_categoria_ano).")
        for r in grandes.sort_values("n_com_sjr", ascending=False).head(15).itertuples():
            pct_emp = 100 * r.n_em_empate / r.n_com_sjr
            L.append(f"  - {r.ano} · {r.categoria}: concordância {r.concordancia_quartil:.2f}, "
                     f"n={r.n_com_sjr}, {pct_emp:.0f}% em empate")
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="scimago_etl", description="Carrega os CSVs do SCImago em SQLite.")
    ap.add_argument("--pasta", required=True, help="Pasta com os CSVs (busca recursiva)")
    ap.add_argument("--banco", default="scimago.db", help="Arquivo SQLite de saída (é recriado)")
    ap.add_argument("--anos", type=int, nargs="*", default=list(ANOS_PADRAO))
    ap.add_argument("--metodo-percentil", choices=percentil.METODOS, default=METODO_PERCENTIL_PADRAO)
    ap.add_argument("--empates", choices=tuple(percentil.EMPATES), default=EMPATES_PADRAO,
                    help="Regra de empate de SJR (padrão: melhor posição do bloco)")
    ap.add_argument("--relatorio", default=None, help="Onde salvar o relatório .md (padrão: ao lado do banco)")
    args = ap.parse_args(argv)

    arquivos = leitura.descobrir_arquivos(args.pasta, tuple(args.anos))
    if not arquivos:
        raise SystemExit(f"Nenhum CSV do SCImago encontrado em {args.pasta}")
    print(f"Lendo {len(arquivos)} arquivos...")
    bruto = leitura.ler_todos(arquivos)
    tabelas = banco.montar_tabelas(bruto, arquivos, args.metodo_percentil, args.empates)
    banco.gravar(args.banco, tabelas, arquivos, bruto, args.metodo_percentil, args.empates)

    texto = relatorio(arquivos, tabelas, args.metodo_percentil, args.empates)
    destino = Path(args.relatorio or Path(args.banco).with_suffix(".relatorio.md"))
    destino.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"Banco: {args.banco}\nRelatório: {destino}")


if __name__ == "__main__":
    main()
