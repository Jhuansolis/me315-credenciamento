import sqlite3, pandas as pd
pd.set_option("display.width", 200)
con = sqlite3.connect("scimago.db")
for cat in ["Literature and Literary Theory", "Industrial and Manufacturing Engineering"]:
    df = pd.read_sql("""
        SELECT p.posicao, p.n_categoria, p.quartil_scimago, m.sjr
        FROM periodico_categoria_ano p
        JOIN categoria c ON c.id = p.categoria_id
        JOIN metrica_anual m ON m.sourceid = p.sourceid AND m.ano = p.ano
        WHERE c.nome = ? AND p.ano = 2024 AND p.posicao IS NOT NULL
        ORDER BY p.posicao""", con, params=[cat])
    n = df.n_categoria.iloc[0]
    print(f"\n== {cat} (n={n})")
    print("Empates no SJR:", df.sjr.duplicated(keep=False).sum(), "periódicos")
    print("Última posição de cada quartil (SCImago):")
    print(df.groupby("quartil_scimago").posicao.max())
    print("Esperado se o universo fosse só o nosso:", [round(n*k/4) for k in (1, 2, 3)])