"""Banco SQLite FICTÍCIO para os testes.

O esquema NÃO é copiado: é lido do próprio ``scimago_etl/scimago_etl/schema.sql``
(etapa 1), então qualquer mudança de esquema lá quebra os testes aqui. Os
periódicos, ISSNs e percentis são inventados e NÃO refletem o SCImago.

Semântica do esquema real reproduzida aqui:
- ``n_empatados`` = quantos periódicos dividem o SJR na categoria/ano; 1 = sem empate.
- ``posicao`` é REAL.
- Periódico sem SJR no ano: linha em ``metrica_anual`` com ``sjr`` NULL e linhas
  em ``periodico_categoria_ano`` com ``percentil``/``posicao``/``n_empatados`` NULL.
"""

import sqlite3
from pathlib import Path

ESQUEMA_REAL = Path(__file__).resolve().parents[2] / "scimago_etl" / "scimago_etl" / "schema.sql"

CATEGORIAS = {1: "Statistics and Probability", 2: "Economics and Econometrics", 3: "Finance"}
N_CATEGORIA = 100

# sourceid: (título, [ISSNs])
PERIODICOS = {
    1: ("Revista Brasileira de Financas", ["19845146", "16790731"]),  # online + impresso
    2: ("Journal of Business and Economic Statistics", ["15372707"]),
    3: ("Journal of Forecasting", ["1099131X"]),
    4: ("Econometrics and Statistics", ["24523062"]),
    5: ("International Journal of Forecasting", ["01692070"]),
    6: ("Journal of Empirical Finance", ["09275398"]),
    7: ("Econometrics", ["22251146"]),
    8: ("Applied Economics", ["00036846"]),
    9: ("Journal of Statistical Computation and Simulation", ["00949655"]),  # sem percentil em nenhum ano
    10: ("Empirical Economics", ["03777332"]),
    11: ("Journal of the American Water Resources Association", ["1093474X"]),
    12: ("Mathematics and Computers in Simulation", ["03784754"]),
}

# sourceid: lista de (ano, categoria_id, percentil, n_empatados); percentil None = sem SJR no ano
PERCENTIS = {
    1: [(2022, 1, 40.0, 1), (2022, 3, 55.0, 1), (2023, 3, 50.0, 1), (2024, 3, 61.5, 1), (2025, 3, 58.0, 1)],
    2: [(2022, 1, 97.0, 3), (2023, 1, 96.0, 1), (2024, 1, 95.0, 1), (2025, 1, 94.0, 1)],
    3: [(2022, 1, 80.0, 1), (2023, 1, 88.0, 1), (2024, 1, 85.0, 1), (2025, 1, 83.0, 1)],
    4: [(2022, 2, 88.0, 1), (2023, 2, 80.0, 1), (2024, 2, 82.0, 1), (2025, 2, 81.0, 1)],
    5: [(2022, 1, 97.0, 1), (2023, 1, 98.0, 1), (2024, 1, 99.0, 1), (2025, 1, 99.0, 1)],
    6: [(2023, 3, 90.0, 1), (2025, 3, 85.0, 1)],
    7: [(2024, 2, 70.0, 1)],
    8: [(2023, 2, 75.0, 1)],
    9: [(2022, 1, None, None), (2023, 1, None, None), (2024, 1, None, None), (2025, 1, None, None)],
    10: [(2025, 2, 60.0, 1)],
    11: [(2022, 2, 66.0, 1)],
    12: [(2022, 1, 60.0, 1)],
}


def _posicao(percentil: float) -> float:
    # Inverso de percentil = 100·(n − posição + 1)/n (método topo_100, D1).
    return N_CATEGORIA - percentil * N_CATEGORIA / 100 + 1


def criar_banco(caminho: Path) -> Path:
    if not ESQUEMA_REAL.is_file():
        raise FileNotFoundError(f"Esquema da etapa 1 não encontrado: {ESQUEMA_REAL}")
    con = sqlite3.connect(caminho)
    con.executescript(ESQUEMA_REAL.read_text(encoding="utf-8"))
    con.executemany("INSERT INTO categoria (id, nome) VALUES (?, ?)", CATEGORIAS.items())
    for sourceid, (titulo, issns) in PERIODICOS.items():
        con.execute("INSERT INTO periodico (sourceid, titulo) VALUES (?, ?)", (sourceid, titulo))
        for issn in issns:
            con.execute(
                "INSERT INTO periodico_issn (issn, issn_formatado, sourceid) VALUES (?, ?, ?)",
                (issn, f"{issn[:4]}-{issn[4:]}", sourceid),
            )
    for sourceid, linhas in PERCENTIS.items():
        for ano, categoria_id, percentil, n_emp in linhas:
            com_sjr = percentil is not None
            con.execute(
                "INSERT INTO periodico_categoria_ano "
                "(sourceid, ano, categoria_id, quartil_scimago, posicao, n_categoria, n_empatados, percentil) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sourceid, ano, categoria_id, "Q1" if com_sjr else None,
                    _posicao(percentil) if com_sjr else None, N_CATEGORIA if com_sjr else None, n_emp, percentil,
                ),
            )
            con.execute(
                "INSERT OR IGNORE INTO metrica_anual (sourceid, ano, sjr, quartil_melhor) VALUES (?, ?, ?, ?)",
                (sourceid, ano, 1.0 if com_sjr else None, "Q1" if com_sjr else None),
            )
    con.commit()
    con.close()
    return caminho
