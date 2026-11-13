# Etapa 3 — Motor de regras (Artigos X e Y) e app Streamlit

Data: 13/11/2026 · Entrega do trabalho: 03/12/2026

## 1. Intenção

Fechar o sistema de credenciamento do case ME315: o docente sobe o HTML público do
seu Lattes, declara sua situação do Artigo Y e vê se atinge a nota mínima do Artigo X.
A comissão usa **o mesmo fluxo** (sobe o HTML do docente e preenche o Artigo Y por ele).

É um trabalho de disciplina que simula o case, não um sistema real. Por isso:
- o Artigo Y é **autodeclarado** e o sistema confia no que é declarado (nada é inferido
  do Lattes, nada é comprovado, não há tratamento de LGPD);
- não há login, histórico, nem lista de pedidos: nada é gravado.

Requisito transversal do autor: **as regras devem ser fáceis de mudar depois**, porque
parte delas (licença médica, acúmulo) ainda será apresentada ao professor.

## 2. Regras de negócio (decididas)

### Artigo X — nota

- Nota de cada artigo `p_i` = maior percentil SJR do **periódico** em que saiu, considerando
  todas as categorias e os anos **2022–2025** (o que a etapa 2 já calcula em
  `lattes_rank.ranking` / `banco.nota`). Essa nota **não muda** quando a janela de artigos é
  ampliada pelo Artigo Y.
- No banco o percentil está em escala **0–100** (D1 da etapa 1); a fórmula do case usa
  **0–1**. O motor trabalha em 0–1 (dividir por 100 na fronteira).
- Unidade de seleção: **artigos distintos**, não periódicos distintos. Quatro artigos
  diferentes na mesma revista podem entrar os quatro. (Isso difere da saída atual da etapa 2,
  que agrupa por periódico; o motor deve usar a lista de **artigos** pontuados.)
- **Duplicatas no Lattes** (mesmo artigo cadastrado duas vezes) contam **uma vez só**
  *(decisão do redator, coerente com "artigos distintos")*. Chave: DOI normalizado
  (minúsculas, sem prefixo `https://doi.org/`); sem DOI, título normalizado (minúsculas,
  sem acentos/pontuação) + ano. Fica a primeira ocorrência do currículo; as demais vão para
  "não entraram" com o motivo "duplicado". A deduplicação é uma função própria e trocável.
- Nota final = `Σ p_i · I(p_i ≥ 0,25)` sobre **até 4** artigos escolhidos. Apto se `≥ 1,25`.
- O sistema **pré-seleciona os 4 artigos de maior `p_i`**; o usuário pode trocar a seleção
  (no máximo 4). Desempate da pré-seleção: ano mais recente, depois a ordem do currículo.

### Artigo Y — ampliação da janela de artigos

A janela base de artigos é 2022–2025 (lida do banco, como hoje). A ampliação recua só o
**ano inicial**; o ano final continua 2025 (artigos de 2026 nunca entram).

| Situação declarada | Ampliação | Observação |
|---|---|---|
| Licença parental | **+24 meses por licença** (50% da base de 4 anos) | Cada licença soma; o usuário informa a quantidade |
| PcD (docente, cônjuge ou dependente) | **+24 meses, uma única vez** | É uma condição só, mesmo que mais de uma pessoa se enquadre |
| Licença médica | **+ duração total, em meses** | O usuário informa o total de meses (soma de todas as licenças) |

- Os benefícios **se acumulam sem teto**.
- Conversão: somam-se **todos os meses** e só no fim converte-se em anos, **arredondando
  para cima**: `anos_extras = ceil(total_meses / 12)`; `ano_inicial = 2022 − anos_extras`.
  Exemplo: 1 parental + 5 meses médica = 29 meses → 3 anos → janela 2019–2025.
- O texto do case diz "PcD … até cinco anos": é erro do enunciado; vale +2 anos (total 6).
- A regra da licença médica (meses + arredondar para cima) é **proposta a validar com o
  professor**; alternativas que ele pode preferir: arredondar para baixo ou para o mais próximo.

## 3. Abordagens consideradas

- **A. Funções puras + objeto de parâmetros em Python — escolhida.** Um módulo de regras sem
  dependência de Streamlit nem de SQLite; todos os números num único objeto de configuração;
  uma função pequena por passo. Mudar uma regra = mudar um valor ou uma função, com teste.
- B. Regras em arquivo YAML/JSON. Descartada: mais uma camada de leitura/validação, e as
  mudanças prováveis (arredondamento, acúmulo) são de lógica, não só de números.
- C. Lógica dentro do `app.py`. Descartada: difícil de testar e de mudar.

## 4. Desenho

### 4.1 Motor de regras (`src/regras.py`)

Puro: recebe dados simples, devolve dados simples. Não importa `streamlit`, `sqlite3` nem
`lattes_rank` (o app faz a adaptação), para ser testável isoladamente.

Elementos (nomes indicativos):

- `ParametrosRegras` (dataclass congelada) com valores padrão:
  `anos_base=4`, `meses_por_licenca_parental=24`, `meses_pcd=24`, `pcd_conta_uma_vez=True`,
  `arredondamento="cima"` (`"cima" | "baixo" | "proximo"`), `max_artigos=4`,
  `corte_individual=0.25`, `nota_minima=1.25`.
- `DeclaracaoArtigoY`: `n_licencas_parentais: int`, `pcd: bool`, `meses_licenca_medica: int`
  (todos ≥ 0; validar).
- `meses_de_ampliacao(declaracao, params) -> int`
- `anos_de_ampliacao(meses, params) -> int`
- `janela_de_artigos(ano_base_min, ano_base_max, declaracao, params) -> (ano_min, ano_max, memoria)`
  onde `memoria` é uma lista de linhas legíveis explicando o cálculo (ex.: "1 licença parental:
  +24 meses", "Total 29 meses → 3 anos (arredondado para cima)").
- `ArtigoPontuavel`: identificador estável, título, periódico, ano, `percentil` em 0–1.
- `preselecionar(artigos, params) -> list[id]` (top 4 por percentil, desempates acima).
- `calcular_nota(artigos_escolhidos, params) -> ResultadoNota` com a contribuição de cada
  artigo (0 se `p < 0,25`), a soma, e `apto: bool`. Rejeitar mais de `max_artigos`.

### 4.2 Integração com a etapa 2

- O app usa `lattes_rank` para ler o HTML (`interpretar_html` / `decodificar_html`) e
  classificar os artigos (`classificar_artigos`) com a política de anos vinda do motor
  (`politica_estendida(base_min, base_max, anos_extras)`, ou `politica_padrao` quando 0).
- Os `ArtigoAvaliado` com status `pontuado` viram `ArtigoPontuavel` (percentil / 100).
- Os demais status (fora da janela, não localizado, sem percentil) são **mostrados** ao usuário
  com o motivo, para ele entender por que um artigo não entrou.

### 4.3 App Streamlit (`app.py`)

Uma página, sem login, sem gravar nada:

```
ME315 — Credenciamento Docente
[Upload do HTML do Lattes]
  → Nome, ID Lattes, data de atualização (quando houver)

Artigo Y — ampliação do período (opcional)
  Nº de licenças parentais [0]   ☐ PcD (docente/cônjuge/dependente)
  Meses de licença médica  [0]
  → Janela de artigos: 2019–2025  (memória de cálculo expansível)

Artigos elegíveis (pontuados)        ← multiselect, máx. 4, pré-selecionados os 4 melhores
  título | periódico | ano | percentil | conta? (≥ 0,25)

Resultado: Nota 1,42 ≥ 1,25 → APTO   (contribuição de cada artigo)

▸ Artigos que não entraram (status e motivo)
```

- Mudar o Artigo Y recalcula a janela e a lista de elegíveis; a seleção volta para a
  pré-seleção quando a lista de elegíveis muda.
- Marcas da etapa 2 (empate de SJR, `*`) aparecem na tabela como coluna/nota de rodapé.

### 4.4 Deploy (Streamlit Community Cloud)

- O `scimago_etl/scimago.db` (≈54 MB) **passa a ser versionado**: exceção no `.gitignore`
  (`!scimago_etl/scimago.db`). Atualizar a regra correspondente no `CONTRIBUTING.md`
  ("banco `.db` fora do repositório").
- O app abre o banco em modo somente leitura (`Banco` da etapa 2), uma vez, com
  `st.cache_resource`.
- `requirements.txt` da raiz deve bastar para o Streamlit Cloud instalar tudo.
- O repositório (`Jhuansolis/me315-credenciamento`) é **público** (decidido em 13/11/2026),
  então o app fica com link aberto para o professor e a turma. O dono é o Jhuan; só ele
  conecta o repo ao Streamlit Cloud. Quem implementa **prepara** o deploy (banco versionado,
  imports, requirements, `streamlit run app.py` funcionando localmente) e entrega um checklist
  curto; o clique de deploy é do Jhuan. A `main` não tem proteção configurada no GitHub, mas
  o fluxo combinado é PR com revisão: agrupar a exceção do banco e o ajuste de imports num
  PR cedo, para o deploy não esperar o resto.

### 4.5 Ordem de entrega sugerida

1. Motor do Artigo X (`calcular_nota`, `preselecionar`) + testes.
2. App com upload, lista de artigos, seleção e nota (janela fixa 2022–2025) + deploy.
3. Motor do Artigo Y (`meses_de_ampliacao`, `anos_de_ampliacao`, `janela_de_artigos`) + testes.
4. Painel do Artigo Y no app.

## 5. Objetivos, não-objetivos, anti-objetivos

- **Objetivos:** nota do Artigo X correta por artigo; janela do Artigo Y conforme a tabela;
  memória de cálculo visível; regras alteráveis mudando parâmetros ou uma função pequena;
  app no ar no Streamlit Cloud.
- **Não-objetivos:** login, perfis distintos docente/comissão, histórico, fila de pedidos,
  comprovação de licenças, upload de XML, casamento de periódicos por nome.
- **Anti-objetivos (seria falha mesmo funcionando):** regras espalhadas pelo `app.py`;
  números mágicos fora de `ParametrosRegras`; nota que muda quando a janela de artigos é
  ampliada (a nota do periódico é sempre 2022–2025); resultado sem explicação de por que um
  artigo não entrou.

## 6. Restrições

- Python + Streamlit + SQLite, como o resto do projeto. Banco da etapa 1 só leitura.
- Código e textos em português, como no resto do repositório.
- Fluxo do time: branch + PR com revisão (`CONTRIBUTING.md`).

## 7. Deixado para quem implementar

- Como o `app.py` (raiz) importa o pacote `lattes_rank` (que está em `lattes_rank/lattes_rank/`):
  ajuste de `sys.path`, pacote instalável, ou mover. Funcionar no Streamlit Cloud é o critério.
- O que fazer com os stubs antigos de `src/` (`lattes.py`, `sjr.py`, `percentil.py`, `db.py`,
  pensados para XML e outro esquema): podem ser removidos ou deixados; não fazem parte desta etapa.
- Layout fino do app, textos, componentes Streamlit exatos.
- Identificador estável de artigo para o multiselect (ex.: `sequencia` do currículo).
