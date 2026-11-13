# ME315 — Sistema de Credenciamento Docente (PPGE)

Projeto final da disciplina ME315. Aplicação em **Python + Streamlit + SQLite** que lê o currículo Lattes (HTML) de um docente, cruza os artigos com o SJR (Scimago) de 2022–2025 e calcula se ele atende às regras de credenciamento.

**Entrega:** 3 de dezembro de 2026

## Equipe

| Nome | Usuário GitHub | Módulo principal |
|------|----------------|------------------|
| Jhuan | @jhuansolis | 
| _____ | @_____ | 
| _____ | @_____ | 
| _____ | @_____ | 

> Primeira tarefa de cada um: abrir um PR preenchendo sua linha nesta tabela.

## Como rodar

```bash
git clone https://github.com/<usuario>/me315-credenciamento.git
cd me315-credenciamento
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Testes:

```bash
pytest
```

## Estrutura

```
app.py                interface Streamlit (upload do Lattes, Artigo Y, seleção e nota)
src/
  regras.py           motor de regras: nota (Artigo X), janela de artigos (Artigo Y), pré-seleção
  integracao.py       liga o HTML do Lattes e o banco SCImago ao motor de regras
sql/schema.sql        definição das tabelas
scimago_etl/          etapa 1: CSVs do SJR -> banco SQLite (scimago.db é versionado)
lattes_rank/          etapa 2: HTML do Lattes -> artigos com percentil SJR
tests/                testes com pytest
docs/                 decisões, perguntas ao professor e especificações
```

## Regras do credenciamento

Resumo; o detalhe e as decisões estão em
[docs/superpowers/specs/2026-11-13-motor-regras-streamlit-design.md](docs/superpowers/specs/2026-11-13-motor-regras-streamlit-design.md).

- **Artigo X (nota):** cada artigo vale o maior percentil SJR do seu periódico em 2022–2025
  (0 a 1). Contam até 4 artigos distintos; só soma quem tem percentil ≥ 0,25. Apto se a nota
  for ≥ 1,25. O sistema pré-seleciona os 4 melhores e o usuário pode trocar.
- **Artigo Y (ampliação da janela de artigos):** o ano inicial recua conforme o declarado:
  +24 meses por licença parental, +24 meses (uma única vez) para PcD, e + os meses de licença
  médica. Somam-se os meses e arredonda-se para cima em anos. A nota do periódico não muda.
- Artigos duplicados no Lattes contam uma vez. Nenhum dado do usuário é gravado.

## Deploy no Streamlit Cloud

1. Fazer o merge das branches na `main` (o banco `scimago_etl/scimago.db` precisa estar na `main`).
2. Em share.streamlit.io, entrar com o GitHub do dono do repositório, clicar em *Create app*,
   escolher o repositório `Jhuansolis/me315-credenciamento`, a branch `main` e o arquivo `app.py`.
3. Em *Advanced settings*, escolher Python 3.12.
4. Abrir o link gerado, enviar o HTML da fixture (`lattes_rank/tests/fixtures/artigos_completos.html`)
   e conferir a nota.

## Etapa 2 — ranking de periódicos a partir do Lattes (`lattes_rank/`)

Lê o HTML **público** do currículo (Ctrl+S na página `lattes.cnpq.br/<ID>`, depois de resolver o captcha) e
devolve os 4 periódicos de maior percentil SJR (máximo de 2022–2025), usando o banco da etapa 1 só para leitura:

```bash
cd lattes_rank
python -m lattes_rank CURRICULO.html --db ../scimago_etl/scimago.db [--top 4] [--json saida.json]
python -m pytest -q
```

Regras, decisões pendentes e proposta de tabelas futuras estão em [lattes_rank/README.md](lattes_rank/README.md).

## Fluxo de trabalho

Leia o [CONTRIBUTING.md](CONTRIBUTING.md) antes de começar. Resumo: ninguém faz commit direto na `main`; toda mudança entra por Pull Request revisado por outra pessoa.
