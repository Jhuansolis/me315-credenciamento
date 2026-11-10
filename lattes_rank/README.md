# lattes_rank — periódicos de maior percentil de um docente (etapa 2)

Lê o HTML **público** do Currículo Lattes de um docente, coleta os periódicos em que
ele publicou artigos completos e devolve os **4 periódicos de maior percentil SJR**
segundo o banco SQLite da etapa 1 (`scimago_etl`, anos 2022–2025).
O banco é aberto **somente para leitura**; nada é gravado nele.

## Como obter o HTML do Lattes

O XML do Lattes só pode ser baixado pelo próprio pesquisador. Por isso a ferramenta usa a página pública:

1. Abra `http://lattes.cnpq.br/<ID de 16 dígitos>` e resolva o captcha.
2. Na página do currículo, use **Ctrl+S** e escolha "Página da Web, somente HTML" ou "completa".
   Basta o `.html`; a pasta `_files` não é usada.
3. Alternativa: no F12, copie o `outerHTML` de `div#artigos-completos` e salve num `.html`.
   Nesse caso o relatório sai sem nome, ID e data de atualização.

O arquivo salvo pode estar em UTF-8 declarando `windows-1252` no `<meta>`, ou em cp1252 de
fato. O leitor tenta UTF-8, depois o charset do `<meta>` e por fim cp1252/latin-1. Se
encontrar 5 ou mais caracteres `�`, avisa que os acentos se perderam. ISSN, ano e DOI não
são afetados.

## Uso

```bash
pip install -r requirements.txt
cd lattes_rank
python -m lattes_rank CURRICULO.html --db ../scimago_etl/scimago.db
python -m lattes_rank pasta_com_htmls/ --db scimago.db --top 4 --json resultado.json
python -m pytest -q
```

- `ENTRADA`: um arquivo `.html`/`.htm` ou uma pasta com vários. Cada currículo vira um relatório.
- `--top N`: quantos periódicos listar (padrão 4).
- `--json`: grava o resultado completo, com o status e o motivo de cada artigo.
- Erros como arquivo ou banco inexistente, ou banco com esquema errado, saem como
  `Erro: ...` com código 2.
- A janela da nota (2022–2025) é lida do banco (`MIN/MAX(ano)` de `v_melhor_percentil`),
  não do código.

## Regras aplicadas

1. **Artigos considerados:** só os publicados de 2022 a 2025. Artigos de 2026 em diante
   **nunca** pontuam. Artigos sem ano ficam de fora.
2. **Nota do periódico:** o **maior percentil entre 2022 e 2025**, na melhor categoria de cada
   ano (`v_melhor_percentil`), **independente do ano do artigo**. Se a nota empata entre anos,
   vale o mais recente.
3. **Casamento por ISSN:** o ISSN é normalizado (só dígitos e `X`, sem completar zeros) e
   validado (formato `^\d{7}[\dX]$` e dígito verificador, módulo 11). Os artigos são
   agrupados por `sourceid`, então o ISSN impresso e o online do mesmo periódico contam como
   um só. Um ISSN que aponta para mais de um `sourceid` é ambíguo e fica "não localizado".
4. **Saída:** os 4 periódicos **distintos** de maior nota. Desempate: maior nº de artigos do
   docente no periódico, depois o ano de artigo mais recente, depois o título.
5. **Status de cada artigo** (avaliado nesta ordem):

   | status | quando | `codigo_motivo` no JSON |
   |---|---|---|
   | `fora_da_janela` | sem ano ou ano fora da regra | `sem_ano`, `fora_da_politica` |
   | `nao_localizado` | ISSN não casa | `sem_issn`, `formato_invalido`, `digito_verificador`, `ausente_no_banco`, `ambiguo` |
   | `sem_percentil` | o periódico está na base, mas sem SJR em 2022–2025 | `sem_sjr_na_janela` |
   | `pontuado` | o artigo entra no ranking | — |

6. **Marcas no relatório:**
   - `†`: a nota é igual à de um periódico vizinho, e a ordem saiu dos desempates.
   - `*`: o percentil vem de um bloco de **SJR empatado** na categoria (`n_empatados > 1`).
     Pela decisão D2 da etapa 1, os empatados recebem a melhor posição do bloco. Isso deve
     constar no relatório final do trabalho.

## Estrutura

| Módulo | Responsabilidade |
|---|---|
| `issn.py` | Normalização, formato e dígito verificador |
| `parser.py` | HTML do Lattes → `Curriculo` / `Artigo` (BeautifulSoup, `html.parser`) |
| `banco.py` | Leitura do SQLite (`mode=ro`), conferência do esquema e `Nota` de cada periódico |
| `ranking.py` | Política de anos, status de cada artigo e ranking com desempates |
| `relatorio.py` | Relatório em texto e dicionário para JSON |
| `cli.py`, `__main__.py` | Linha de comando |

Os testes usam um banco **fictício** (`tests/banco_ficticio.py`), criado a partir do próprio
`scimago_etl/scimago_etl/schema.sql`. Uma mudança no esquema da etapa 1 quebra os testes daqui,
e isso é intencional. A fixture `tests/fixtures/artigos_completos.html` é a seção de artigos de
um currículo público real, com 17 artigos.

## Pendências (não decididas; deixadas configuráveis ou documentadas)

- **Quanto a condição especial retroage.** `ranking.politica_estendida(base_min, base_max,
  anos_retroativos=None)` já existe e tem testes (`None` = sem limite inferior; a nota continua
  sendo o máximo de 2022–2025, e 2026 continua fora). Ela **ainda não está na CLI**.
- **Periódico sem SJR no ano de publicação** (pendência da etapa 1). Como a nota é o máximo
  da janela, isso só afeta periódicos sem SJR em nenhum ano de 2022 a 2025, que ficam como
  `sem_percentil`.
- **Normalização de nomes para "não localizados".** O casamento hoje é só por ISSN. O ponto
  de extensão está documentado em `ranking.classificar_artigos`.
- **Persistência.** Nada é gravado no banco. Proposta para uma etapa futura (não implementada):

  ```sql
  CREATE TABLE docente (
      id_lattes        TEXT PRIMARY KEY,         -- 16 dígitos
      nome             TEXT,
      data_atualizacao TEXT,                     -- do currículo (dd/mm/aaaa → ISO)
      arquivo_origem   TEXT,
      lido_em          TEXT NOT NULL
  );
  CREATE TABLE artigo_lattes (
      id_lattes     TEXT NOT NULL REFERENCES docente(id_lattes),
      sequencia     INTEGER NOT NULL,            -- ordem no currículo
      ano           INTEGER,
      titulo        TEXT,
      periodico_nome TEXT,                       -- como está no Lattes
      issn          TEXT,                        -- normalizado
      doi           TEXT,
      sourceid      INTEGER REFERENCES periodico(sourceid),  -- NULL se não localizado
      status        TEXT NOT NULL,
      codigo_motivo TEXT,
      PRIMARY KEY (id_lattes, sequencia)
  );
  ```

## Limitações conhecidas

- Periódico fora do SCImago: se ele não está nos CSVs de 2022–2025, não há percentil. Exemplo
  real: a *Revista Brasileira de Finanças* (ISSN 1984-5146 / 1679-0731) não consta nas listas
  do SCImago, então os artigos nela aparecem em "não localizados".
- O percentil herda as limitações da etapa 1 (`scimago_etl/DECISOES.md`, D1–D3): empates de
  SJR com 3 casas decimais e um universo só de periódicos.
- Quando duas categorias do mesmo ano têm o mesmo percentil e o mesmo `n_categoria`, a categoria
  exibida pela `v_melhor_percentil` é arbitrária. A nota não muda.
