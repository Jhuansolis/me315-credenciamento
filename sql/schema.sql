-- Revistas e posições do SJR por área e ano
CREATE TABLE IF NOT EXISTS sjr (
    issn        TEXT    NOT NULL,   -- ISSN normalizado, só dígitos/X, sem hífen
    titulo      TEXT,
    area        TEXT    NOT NULL,   -- categoria Scimago
    ano         INTEGER NOT NULL,   -- 2022..2025
    posicao     INTEGER NOT NULL,   -- posição no Scimago (1 = melhor)
    total_area  INTEGER NOT NULL,   -- nº de revistas na área naquele ano
    PRIMARY KEY (issn, area, ano)
);

-- Avaliações salvas (depende da pergunta 12 ao professor)
CREATE TABLE IF NOT EXISTS avaliacao (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    docente     TEXT    NOT NULL,
    data        TEXT    NOT NULL DEFAULT (date('now')),
    resultado   REAL,
    aprovado    INTEGER             -- 0/1
);
