# Decisões metodológicas — ETL SCImago

Registro das escolhas de definição. Use como base para a seção de metodologia
e de limitações do relatório final.

## D1 — Fórmula do percentil
- **Decisão:** `percentil = 100 · (n − posição + 1) / n` (método `topo_100`): o 1º lugar tem 100.
- **Universo:** periódicos com SJR na categoria e no ano, juntando os 27 arquivos de área.
- **Alternativa disponível:** `--metodo-percentil linear_0_100`.

## D2 — Empates de SJR
- **Decisão (03/11/2026):** periódicos empatados recebem a **melhor posição do bloco**,
  o que dá o benefício da dúvida ao docente.
- **Motivo do problema:** o CSV traz o SJR com 3 casas decimais. Em categorias de valores
  baixos, isso gera empates em massa: em *Literature and Literary Theory* 2024, 1.010 de 1.101
  periódicos dividem o SJR com outro, e cerca de 113 estão empatados no valor mínimo.
- **Efeito observado:** nessas categorias, o SCImago desempata com mais precisão, então as
  fronteiras de quartil oscilam em torno das nossas (Literature 2024: Q1 termina na posição
  287 no SCImago contra 275 esperado; Q3 em 778 contra 826).
- **Observação para o relatório final:** a regra favorece periódicos que estão em blocos
  empatados sobre as fronteiras de quartil. Para a análise de sensibilidade, compare com
  `--empates media` (posição média do bloco, padrão estatístico). A coluna `n_empatados`
  de `periodico_categoria_ano` mostra quais percentis foram afetados.

## D3 — Universo de comparação: só periódicos
- **Decisão:** o percentil compara o periódico apenas com as fontes presentes nos CSVs (periódicos).
- **Efeito observado:** em algumas categorias o SCImago ranqueia também anais de congresso e
  séries de livros. Em *Industrial and Manufacturing Engineering* 2024, as fronteiras oficiais
  ficam cerca de 12% depois das nossas (Q1: 96 contra 85; Q2: 192 contra 170; Q3: 283 contra 254),
  o que indica cerca de 380 fontes no ranking deles contra as 339 que temos.
- **Consequência:** nosso percentil pode diferir do quartil oficial, sobretudo em engenharias e
  computação. O quartil oficial fica disponível na coluna `quartil_scimago`.

## D4 — Melhor quartil global
- O "SJR Best Quartile" de cada arquivo considera só as categorias da área do arquivo. O melhor
  quartil global é recalculado a partir de todas as categorias do periódico.

## D5 — Área "dona" de categorias ambíguas
- A área de cada categoria é inferida como a única área comum a todos os seus periódicos.
- Em algumas categorias todos os periódicos também pertencem a outra área, e a inferência
  fica ambígua. Exemplo: *Respiratory Care* e *Medical Assisting and Transcription*, sempre
  junto com Medicine.
- **Decisão:** essas categorias recebem a área por um mapeamento manual
  (`CATEGORIA_AREA_MANUAL` em `config.py`), conforme a classificação ASJC usada pelo SCImago.
  Ambas pertencem a Health Professions.
- A área dona só serve para checar se o universo da categoria está completo. Ela **não altera
  o percentil**, que já era calculado sobre todos os periódicos da categoria.
- **Correção de bug (03/11/2026):** a versão anterior marcava como ERRO ("área não carregada")
  as categorias sem área inferida. Era um falso alarme: os 108 arquivos estavam presentes.

## Pendentes
- Regra para periódico sem SJR no ano da publicação: há 3.828 periódicos sem SJR em 2022 e
  251 em 2025. Decidir entre não pontuar e usar o ano mais próximo com SJR.
- Regra de qual categoria usar: o melhor percentil entre todas (`v_melhor_percentil`) ou o de
  uma categoria específica.
