# ME315 — Sistema de Credenciamento Docente (PPGE)

Projeto final da disciplina ME315. Aplicação em **Python + Streamlit + SQLite** que lê o currículo Lattes (XML) de um docente, cruza os artigos com o SJR (Scimago) de 2022–2025 e calcula se ele atende às regras de credenciamento.

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
app.py              interface Streamlit
src/
  db.py             conexão e criação das tabelas SQLite
  sjr.py            importa os CSVs do Scimago para o banco
  lattes.py         extrai os artigos do XML do Lattes
  percentil.py      percentil de cada revista por área/ano
  regras.py         janela, ampliações e escolha dos 4 melhores artigos
sql/schema.sql      definição das tabelas
data/               CSVs brutos do SJR (NÃO versionados)
tests/              testes com pytest
docs/               decisões e perguntas ao professor
```

## Fluxo de trabalho

Leia o [CONTRIBUTING.md](CONTRIBUTING.md) antes de começar. Resumo: ninguém faz commit direto na `main`; toda mudança entra por Pull Request revisado por outra pessoa.
