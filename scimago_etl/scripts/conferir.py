import sqlite3, pandas as pd
con = sqlite3.connect("scimago.db")
consultas = {
    "Periódicos por ano": "SELECT ano, COUNT(*) n, SUM(sjr IS NULL) sem_sjr FROM metrica_anual GROUP BY ano",
    "Categorias suspeitas": """SELECT q.ano, c.nome, q.n_com_sjr, ROUND(q.concordancia_quartil,2) conc
        FROM qualidade_categoria_ano q JOIN categoria c ON c.id=q.categoria_id
        WHERE q.suspeita_incompleta=1 ORDER BY q.n_com_sjr DESC LIMIT 15""",
    "Exemplo (Nature Biomedical Eng.)": "SELECT * FROM v_issn_ano WHERE issn='2157846X'",
}
for titulo, sql in consultas.items():
    print(f"\n== {titulo}"); print(pd.read_sql(sql, con).to_string())