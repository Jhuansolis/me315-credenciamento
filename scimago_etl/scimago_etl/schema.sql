-- Schema SQLite do SCImago (2022-2025). Recriado do zero a cada carga.
PRAGMA foreign_keys = ON;

CREATE TABLE arquivo_fonte (
    id           INTEGER PRIMARY KEY,
    nome         TEXT NOT NULL UNIQUE,
    ano          INTEGER NOT NULL,
    area         TEXT NOT NULL,
    n_linhas     INTEGER NOT NULL,
    carregado_em TEXT NOT NULL
);

CREATE TABLE area (
    id   INTEGER PRIMARY KEY,
    nome TEXT NOT NULL UNIQUE
);

CREATE TABLE categoria (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL UNIQUE,
    area_id INTEGER REFERENCES area(id)   -- área "dona"; NULL se não deu para inferir
);

-- Dados cadastrais: um registro por periódico (valores do ano mais recente em que aparece).
CREATE TABLE periodico (
    sourceid           INTEGER PRIMARY KEY,
    titulo             TEXT NOT NULL,
    tipo               TEXT,
    publisher          TEXT,
    pais               TEXT,
    regiao             TEXT,
    cobertura          TEXT,
    cobertura_inicio   INTEGER,
    cobertura_fim      INTEGER,
    descontinuado      INTEGER NOT NULL DEFAULT 0,
    primeiro_ano       INTEGER,   -- primeiro ano em que aparece nos arquivos
    ultimo_ano         INTEGER
);

-- ISSN sem hífen e em maiúsculas (ex.: '2157846X'). Chave para cruzar com o Lattes.
CREATE TABLE periodico_issn (
    issn          TEXT NOT NULL,
    issn_formatado TEXT NOT NULL,          -- '2157-846X'
    sourceid      INTEGER NOT NULL REFERENCES periodico(sourceid),
    PRIMARY KEY (issn, sourceid)
);
CREATE INDEX ix_issn ON periodico_issn(issn);

-- Métricas por periódico e ano.
CREATE TABLE metrica_anual (
    sourceid               INTEGER NOT NULL REFERENCES periodico(sourceid),
    ano                    INTEGER NOT NULL,
    titulo_no_ano          TEXT,
    sjr                    REAL,          -- NULL = sem SJR no ano
    quartil_melhor         TEXT CHECK (quartil_melhor IN ('Q1','Q2','Q3','Q4')),  -- global, entre TODAS as categorias
    h_index                INTEGER,
    total_docs_ano         INTEGER,
    total_docs_3anos       INTEGER,
    total_refs             INTEGER,
    total_citacoes_3anos   INTEGER,
    docs_citaveis_3anos    INTEGER,
    citacoes_por_doc_2anos REAL,
    refs_por_doc           REAL,
    pct_feminino           REAL,
    overton                INTEGER,
    open_access            INTEGER,
    open_access_diamond    INTEGER,
    PRIMARY KEY (sourceid, ano)
);

CREATE TABLE periodico_area_ano (
    sourceid    INTEGER NOT NULL REFERENCES periodico(sourceid),
    ano         INTEGER NOT NULL,
    area_id     INTEGER NOT NULL REFERENCES area(id),
    rank_na_area INTEGER,               -- NULL se o arquivo da área não foi carregado
    quartil_melhor_na_area TEXT,        -- "SJR Best Quartile" daquele arquivo (só categorias da área)
    PRIMARY KEY (sourceid, ano, area_id)
);

-- Coração da análise: posição e percentil do periódico em cada categoria/ano.
CREATE TABLE periodico_categoria_ano (
    sourceid        INTEGER NOT NULL REFERENCES periodico(sourceid),
    ano             INTEGER NOT NULL,
    categoria_id    INTEGER NOT NULL REFERENCES categoria(id),
    quartil_scimago TEXT,               -- quartil publicado pelo SCImago na categoria
    posicao         REAL,               -- 1 = maior SJR; inteiro com empates="melhor", pode ser x,5 com "media"
    n_categoria     INTEGER,            -- periódicos com SJR na categoria no ano
    n_empatados     INTEGER,            -- quantos dividem o mesmo SJR (1 = sem empate)
    percentil       REAL,               -- ver percentil.py
    PRIMARY KEY (sourceid, ano, categoria_id)
);
CREATE INDEX ix_pca_cat ON periodico_categoria_ano(categoria_id, ano);

-- Qualidade: quão confiável é o percentil de cada categoria/ano.
CREATE TABLE qualidade_categoria_ano (
    ano                  INTEGER NOT NULL,
    categoria_id         INTEGER NOT NULL REFERENCES categoria(id),
    n_periodicos         INTEGER NOT NULL,
    n_com_sjr            INTEGER NOT NULL,
    n_em_empate          INTEGER NOT NULL,  -- periódicos que dividem SJR com outro
    concordancia_quartil REAL,          -- fração em que nosso quartil = quartil SCImago
    area_carregada       INTEGER,       -- 1 se o arquivo da área dona daquele ano foi lido
    incompleta           INTEGER NOT NULL,  -- ERRO: área dona não carregada no ano
    diverge_do_scimago   INTEGER NOT NULL,  -- INFORMATIVO: concordância < limiar (empates ou universo maior no SCImago)
    PRIMARY KEY (ano, categoria_id)
);

CREATE TABLE metadado_carga (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

-- Melhor percentil do periódico no ano (entre todas as suas categorias).
CREATE VIEW v_melhor_percentil AS
SELECT sourceid, ano, categoria_id, categoria, percentil, posicao, n_categoria, quartil_scimago
FROM (
    SELECT p.sourceid, p.ano, p.categoria_id, c.nome AS categoria, p.percentil, p.posicao,
           p.n_categoria, p.quartil_scimago,
           ROW_NUMBER() OVER (PARTITION BY p.sourceid, p.ano
                              ORDER BY p.percentil DESC, p.n_categoria DESC) AS ordem
    FROM periodico_categoria_ano p
    JOIN categoria c ON c.id = p.categoria_id
    WHERE p.percentil IS NOT NULL
)
WHERE ordem = 1;

-- Consulta pronta para o cruzamento com publicações: ISSN + ano -> métricas.
CREATE VIEW v_issn_ano AS
SELECT i.issn, i.issn_formatado, m.ano, per.sourceid, per.titulo, m.sjr, m.quartil_melhor,
       mp.percentil AS melhor_percentil, mp.categoria AS categoria_melhor_percentil,
       per.descontinuado
FROM periodico_issn i
JOIN periodico per ON per.sourceid = i.sourceid
JOIN metrica_anual m ON m.sourceid = i.sourceid
LEFT JOIN v_melhor_percentil mp ON mp.sourceid = m.sourceid AND mp.ano = m.ano;
