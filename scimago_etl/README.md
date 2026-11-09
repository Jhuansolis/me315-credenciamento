# scimago_etl — SCImago (2022–2025) → SQLite

Lê os 108 CSVs do SCImago (27 subject areas × 4 anos), limpa, deduplica,
calcula o **percentil de cada periódico em cada categoria/ano** e grava tudo em SQLite.

## Uso

```bash
pip install -r requirements.txt
python -m scimago_etl --pasta "caminho/para/pasta_scimago" --banco scimago.db
python -m pytest -q tests
```

Opções: `--anos 2024 2025`, `--metodo-percentil topo_100|linear_0_100`,
`--empates melhor|media` (padrão `melhor`), `--relatorio saida.md`.
As decisões metodológicas estão em **`DECISOES.md`**.
O banco é recriado a cada execução, ou seja, a carga é idempotente. Junto ao banco sai
`scimago.relatorio.md` com as checagens de qualidade.

## Estrutura

| Módulo | Responsabilidade |
|---|---|
| `config.py` | Decisões de projeto: áreas, anos, método de percentil, limiar de qualidade |
| `leitura.py` | Acha os arquivos pelo nome, lê como texto, padroniza colunas |
| `limpeza.py` | Números, ISSN, categorias, quartis, deduplicação, "explode" de relações N:N |
| `percentil.py` | Posição e percentil por (ano, categoria) |
| `banco.py` | Monta as tabelas finais, infere a área de cada categoria, grava no SQLite |
| `schema.sql` | Tabelas e views |
| `__main__.py` | Linha de comando e relatório |

## Tabelas

- `periodico` — cadastro (1 linha por Sourceid)
- `periodico_issn` — ISSN sem hífen (`2157846X`), mais a versão formatada. Use para cruzar com o Lattes.
- `metrica_anual` — SJR, H-index, documentos etc. por periódico e ano
- `categoria`, `area`, `periodico_area_ano`
- `periodico_categoria_ano` — quartil SCImago, posição, n e **percentil** por categoria e ano
- `qualidade_categoria_ano` — confiabilidade do percentil de cada categoria e ano
- Views `v_melhor_percentil` (melhor categoria do periódico no ano) e `v_issn_ano` (ISSN + ano → métricas)

```sql
SELECT * FROM v_issn_ano WHERE issn = '2157846X' AND ano = 2024;
```

## Casos tratados

1. Separador `;` e decimal com vírgula; tudo é lido como texto para preservar zeros à esquerda.
2. A coluna `Total Docs. (AAAA)` muda de nome por ano. O ano dela é conferido com o nome do arquivo.
3. A coluna `Publisher` aparece duplicada.
4. Nomes de arquivo com vírgula ("Biochemistry, Genetics…") ou com `_`. Arquivo duplicado para o mesmo (ano, área) gera erro.
5. Vários ISSN por célula, dígito `X` e ISSN inválido ou ausente.
6. **O mesmo periódico aparece em vários arquivos de área no mesmo ano**: há uma linha por (Sourceid, ano), e as divergências vão para o relatório.
7. **`SJR Best Quartile` e `Rank` são relativos à área do arquivo** (ex.: Q3 no arquivo de Bioquímica e Q2 no de Ambientais). O melhor quartil global é recalculado a partir de todas as categorias. O valor por área fica em `periodico_area_ano`.
8. Periódico sem SJR no ano (quartil `-`, categorias sem `(Qx)`): ele entra no banco, mas fica fora do cálculo do percentil (`percentil` NULL).
9. Categorias com parênteses no nome: `Medicine (miscellaneous) (Q1)`.
10. Título com `(discontinued)`: é marcado e removido do título.
11. Cobertura com lacunas (`2014-2016, 2018-2026`).
12. Periódico ausente em algum dos anos: não há linha em `metrica_anual` para aquele ano.
13. Empates de SJR: recebem a mesma posição, a melhor do bloco (ver `DECISOES.md`, D2).

## Percentil

O universo de cada categoria e ano são todos os periódicos com SJR que pertencem a ela,
juntando os 27 arquivos. Isso é necessário porque um periódico de "Education" pode estar só
no arquivo de Social Sciences. Por isso o percentil só é confiável com a pasta completa:
a tabela `qualidade_categoria_ano` tem duas marcações:
`incompleta` (**erro**: a área dona da categoria não foi carregada naquele ano) e
`diverge_do_scimago` (**informativo**: os quartis recalculados discordam dos oficiais por
causa de empates ou de um universo maior no SCImago; ver `DECISOES.md`, D2 e D3).

Mesmo com tudo carregado, a concordância de quartil fica em ~97%, e não em 100%. O SCImago
calcula os quartis sobre um universo um pouco maior do que o que vem nos CSVs baixados.
Por isso, nas fronteiras de quartil, o nosso percentil pode divergir levemente do quartil oficial.
