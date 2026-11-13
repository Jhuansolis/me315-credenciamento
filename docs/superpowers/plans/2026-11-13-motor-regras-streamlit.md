# Etapa 3 — Motor de regras e app Streamlit — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** App Streamlit em que o docente (ou a comissão) sobe o HTML do Lattes, declara o Artigo Y e vê a nota do Artigo X sobre até 4 artigos, pronto para deploy no Streamlit Community Cloud.

**Architecture:** `src/regras.py` é o motor puro (sem Streamlit, SQLite ou `lattes_rank`), com todos os números em `ParametrosRegras`. `src/integracao.py` liga a etapa 2 (`lattes_rank`: parser, banco, classificação) ao motor. `app.py` só coleta entradas e mostra resultados.

**Tech Stack:** Python, Streamlit (`streamlit.testing.v1.AppTest` para o teste do app), SQLite somente leitura, pytest, BeautifulSoup (via `lattes_rank`).

**Spec:** `docs/superpowers/specs/2026-11-13-motor-regras-streamlit-design.md`

## Global Constraints

- Código, nomes, mensagens e commits em português, como no resto do repositório (commits sem prefixo do tipo `feat:`).
- `src/regras.py` não importa `streamlit`, `sqlite3` nem `lattes_rank`.
- O motor trabalha com percentil em **0–1**; o banco guarda **0–100** (dividir por 100 em `src/integracao.py`).
- Nota do periódico = maior percentil de **2022–2025**, lido do banco (`banco.anos_com_percentil()`); a ampliação do Artigo Y recua só o ano inicial dos **artigos**. Artigos posteriores a 2025 nunca entram.
- Unidade = artigos distintos; vários artigos da mesma revista podem entrar.
- Valores padrão: parental **+24 meses por licença**; PcD **+24 meses uma única vez**; licença médica **+ meses informados**; soma em meses e `ceil(total/12)`; **até 4** artigos; corte individual **0,25**; nota mínima **1,25**; benefícios acumulam **sem teto**.
- Nenhum dado do usuário é gravado (sem login, sem histórico).
- Testes da raiz: `.venv/bin/python -m pytest tests -q`. Testes da etapa 2: `cd lattes_rank && ../.venv/bin/python -m pytest -q`.

## Review Focus

1. **Nota exatamente na fronteira** (artigo com p = 0,25; soma = 1,25 vinda de percentis do banco divididos por 100): deve contar e dar APTO. Teste na Task 2.
2. **Banco em cache usado por outra thread** (o Streamlit roda cada rerun/sessão em threads diferentes): não pode dar `sqlite3.ProgrammingError`. Teste na Task 4.
3. **HTML que não é Lattes ou sem artigos pontuáveis**: o app mostra avisos e nota 0 / NÃO APTO, sem exceção. Testes nas Tasks 2 e 4.
4. **Mudar o Artigo Y ou o arquivo depois de mexer na seleção**: o multiselect não pode ficar com um `default` fora das opções (o Streamlit lança exceção). Coberto pela chave do widget na Task 5 e pelo teste de `preselecionar` (ids sempre ⊆ entrada) na Task 2.
5. **Duplicata com DOI escrito de formas diferentes** (`https://doi.org/10.1/ABC` × `10.1/abc`) e **artigo sem DOI nem título**: o primeiro par é duplicata; o segundo nunca é marcado como duplicata. Teste na Task 2.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/regras.py` (substitui o stub) | Motor: parâmetros, Artigo X (duplicatas, pré-seleção, nota), Artigo Y (meses, anos, janela) |
| `src/integracao.py` (novo) | `sys.path` para `lattes_rank`, abrir banco, ler HTML, avaliar currículo → dados do motor |
| `lattes_rank/lattes_rank/banco.py` | Novo parâmetro `multithread` em `Banco.__init__` |
| `app.py` | Interface |
| `tests/test_regras.py`, `tests/test_integracao.py`, `tests/test_app.py` | Testes |
| `.gitignore`, `CONTRIBUTING.md`, `README.md`, `requirements.txt`, `docs/perguntas-professor.md` | Deploy e documentação |

---

### Task 1: Versionar o banco e preparar dependências

**Files:**
- Modify: `.gitignore` (após a linha `*.db`)
- Modify: `CONTRIBUTING.md` (regra "Fora do repositório")
- Modify: `requirements.txt`

- [ ] **Step 1:** Em `.gitignore`, logo após o bloco `*.db / *.sqlite / *.sqlite3`, adicionar `!scimago_etl/scimago.db` com o comentário `# exceção: banco da etapa 1 vai junto para o deploy (Streamlit Cloud)`.
- [ ] **Step 2:** Verificar: `git check-ignore -v scimago_etl/scimago.db` não imprime nada (código de saída 1); `git status --short` mostra `?? scimago_etl/scimago.db`.
- [ ] **Step 3:** Em `CONTRIBUTING.md`, trocar "banco `.db`" na regra "Fora do repositório" por: "outros bancos `.db` (exceção: `scimago_etl/scimago.db`, versionado para o deploy; ao regenerá-lo, commite junto com a mudança do ETL)".
- [ ] **Step 4:** `requirements.txt` da raiz: manter `streamlit>=1.38`, `pandas>=2.2`, `beautifulsoup4>=4.12`, `pytest>=8.0`; remover `lxml` (ninguém usa: o parser usa `html.parser`). Rodar `.venv/bin/pip install -r requirements.txt` e confirmar `.venv/bin/python -c "import streamlit, pandas, bs4"` sem erro. Se o Python 3.14 do venv não instalar o Streamlit, criar o venv com 3.12 e anotar no README (Task 5).
- [ ] **Step 5:** Rodar `.venv/bin/python -m pytest tests -q` → `3 passed`; `cd lattes_rank && ../.venv/bin/python -m pytest -q` → `74 passed`.
- [ ] **Step 6: Commit**

```bash
git add .gitignore CONTRIBUTING.md requirements.txt scimago_etl/scimago.db
git commit -m "Versiona o banco SCImago para o deploy e ajusta dependências"
```

---

### Task 2: Motor do Artigo X

**Files:**
- Modify (substituir o stub): `src/regras.py`
- Test: `tests/test_regras.py`

**Interfaces:**
- Produces (em `src/regras.py`):
  - `Arredondamento = Literal["cima", "baixo", "proximo"]`
  - `@dataclass(frozen=True) ParametrosRegras`: `meses_por_licenca_parental: int = 24`, `meses_pcd: int = 24`, `pcd_conta_uma_vez: bool = True`, `arredondamento: Arredondamento = "cima"`, `max_artigos: int = 4`, `corte_individual: float = 0.25`, `nota_minima: float = 1.25`. Constante `PARAMETROS_PADRAO = ParametrosRegras()`. (O `anos_base` do spec foi omitido: a janela base vem do banco e nada o usaria.)
  - `@dataclass(frozen=True) ArtigoPontuavel`: `id: int` (posição no currículo, 0-based), `titulo: str | None`, `periodico: str`, `ano: int`, `percentil: float` (0–1), `doi: str | None = None`, `empate_sjr: bool = False`.
  - `remover_duplicatas(artigos: list[ArtigoPontuavel]) -> tuple[list[ArtigoPontuavel], list[ArtigoPontuavel]]` → `(mantidos, duplicados)`, ambos na ordem de entrada.
  - `preselecionar(artigos: list[ArtigoPontuavel], params: ParametrosRegras = PARAMETROS_PADRAO) -> list[int]`
  - `@dataclass(frozen=True) ContribuicaoArtigo`: `artigo: ArtigoPontuavel`, `conta: bool`, `contribuicao: float`
  - `@dataclass(frozen=True) ResultadoNota`: `itens: tuple[ContribuicaoArtigo, ...]`, `total: float`, `apto: bool`
  - `calcular_nota(escolhidos: list[ArtigoPontuavel], params: ParametrosRegras = PARAMETROS_PADRAO) -> ResultadoNota`

- [ ] **Step 1: Escrever os testes que falham** em `tests/test_regras.py` (helper `art(id, p, ano=2024, doi=None, titulo="T")` que monta `ArtigoPontuavel(id, titulo, "Revista", ano, p, doi)`):

```python
def test_soma_os_artigos_que_passam_do_corte():
    r = calcular_nota([art(0, 0.9), art(1, 0.8), art(2, 0.2)])
    assert r.total == pytest.approx(1.7)
    assert [i.conta for i in r.itens] == [True, True, False]
    assert r.itens[2].contribuicao == 0
    assert r.apto

def test_fronteira_conta_e_aprova():  # Review Focus 1
    r = calcular_nota([art(0, 50.0 / 100), art(1, 50.0 / 100), art(2, 25.0 / 100)])
    assert r.itens[2].conta
    assert r.apto

def test_fronteira_com_ruido_de_ponto_flutuante():
    # percentis reais do banco (0–100) divididos por 100: a soma dá 1.2499999999999998
    r = calcular_nota([art(0, 25.02 / 100), art(1, 25.49 / 100), art(2, 74.49 / 100)])
    assert r.apto  # 1,25 com ruído de ponto flutuante ainda é ≥ 1,25 (tolerância 1e-9)

def test_lista_vazia_da_zero_e_nao_apto():  # Review Focus 3
    r = calcular_nota([])
    assert r.total == 0 and not r.apto and r.itens == ()

def test_mais_de_quatro_artigos_e_erro():
    with pytest.raises(ValueError):
        calcular_nota([art(i, 0.5) for i in range(5)])

def test_mesma_revista_pode_entrar_quatro_vezes():
    artigos = [art(i, 0.9) for i in range(4)]  # todos "Revista"
    assert calcular_nota(artigos).total == pytest.approx(3.6)

def test_preselecao_pega_os_quatro_maiores_com_desempate():
    artigos = [art(0, 0.5, 2022), art(1, 0.9), art(2, 0.5, 2025), art(3, 0.7), art(4, 0.5, 2025), art(5, 0.1)]
    assert preselecionar(artigos) == [1, 3, 2, 4]  # empate 0.5: ano mais recente, depois id

def test_preselecao_devolve_subconjunto_dos_ids():  # Review Focus 4
    assert preselecionar([art(7, 0.3)]) == [7]
    assert preselecionar([]) == []

def test_duplicata_por_doi_normalizado():  # Review Focus 5
    a = art(0, 0.9, doi="https://doi.org/10.1/ABC")
    b = art(1, 0.9, doi="10.1/abc")
    assert remover_duplicatas([a, b]) == ([a], [b])

def test_duplicata_sem_doi_por_titulo_e_ano():
    a = art(0, 0.9, titulo="Um Título, com Acentuação!")
    b = art(1, 0.9, titulo="um titulo com acentuacao")
    c = art(2, 0.9, ano=2023, titulo="um titulo com acentuacao")
    assert remover_duplicatas([a, b, c]) == ([a, c], [b])

def test_sem_doi_e_sem_titulo_nunca_e_duplicata():  # Review Focus 5
    a, b = art(0, 0.9, titulo=None), art(1, 0.9, titulo=None)
    assert remover_duplicatas([a, b]) == ([a, b], [])
```

- [ ] **Step 2:** Rodar `.venv/bin/python -m pytest tests/test_regras.py -q` → falha de importação.
- [ ] **Step 3: Implementar** os itens de *Produces* em `src/regras.py`, com docstring do módulo explicando as regras e apontando para o spec.
  - `calcular_nota`: `conta = artigo.percentil >= params.corte_individual - 1e-9`; `total` = soma das contribuições; `apto = total >= params.nota_minima - 1e-9`. Erro se `len(escolhidos) > params.max_artigos`.
  - `preselecionar`: ordenar por `(-percentil, -ano, id)` e pegar `params.max_artigos` ids.
  - Chave de duplicata (função privada `_chave_duplicata(artigo) -> tuple | None`): se há DOI, `("doi", doi minúsculo sem prefixo "https://doi.org/", "http://doi.org/" ou "doi:", sem espaços)`; senão, se há título, `("titulo", título sem acentos (unicodedata NFKD), minúsculo, só letras/dígitos/espaços colapsados, ano)`; senão `None` (nunca duplicata). Mantém a primeira ocorrência.
- [ ] **Step 4:** Rodar `.venv/bin/python -m pytest tests/test_regras.py -q` → todos passam.
- [ ] **Step 5: Commit**

```bash
git add src/regras.py tests/test_regras.py
git commit -m "Motor de regras: nota do Artigo X, pré-seleção e duplicatas"
```

---

### Task 3: Motor do Artigo Y

**Files:**
- Modify: `src/regras.py`
- Test: `tests/test_regras.py`
- Modify: `docs/perguntas-professor.md`

**Interfaces:**
- Consumes: `ParametrosRegras`, `PARAMETROS_PADRAO` (Task 2).
- Produces:
  - `@dataclass(frozen=True) DeclaracaoArtigoY`: `n_licencas_parentais: int = 0`, `pcd_docente: bool = False`, `pcd_familiar: bool = False`, `meses_licenca_medica: int = 0`. (O spec previa `pcd: bool`; foram separados em docente/familiar para que `pcd_conta_uma_vez` tenha efeito se a regra mudar.)
  - `meses_de_ampliacao(declaracao: DeclaracaoArtigoY, params: ParametrosRegras = PARAMETROS_PADRAO) -> int` — `ValueError` se algum número for negativo.
  - `anos_de_ampliacao(meses: int, params: ParametrosRegras = PARAMETROS_PADRAO) -> int`
  - `@dataclass(frozen=True) JanelaArtigos`: `ano_min: int`, `ano_max: int`, `anos_extras: int`, `memoria: tuple[str, ...]`
  - `janela_de_artigos(ano_base_min: int, ano_base_max: int, declaracao: DeclaracaoArtigoY, params: ParametrosRegras = PARAMETROS_PADRAO) -> JanelaArtigos`

- [ ] **Step 1: Escrever os testes que falham:**

```python
def test_meses_combinados():
    assert meses_de_ampliacao(DeclaracaoArtigoY(n_licencas_parentais=1, meses_licenca_medica=5)) == 29
    assert meses_de_ampliacao(DeclaracaoArtigoY(n_licencas_parentais=2)) == 48
    assert meses_de_ampliacao(DeclaracaoArtigoY()) == 0

def test_pcd_conta_uma_vez_por_padrao():
    d = DeclaracaoArtigoY(pcd_docente=True, pcd_familiar=True)
    assert meses_de_ampliacao(d) == 24
    assert meses_de_ampliacao(d, ParametrosRegras(pcd_conta_uma_vez=False)) == 48

def test_negativo_e_erro():
    with pytest.raises(ValueError):
        meses_de_ampliacao(DeclaracaoArtigoY(meses_licenca_medica=-1))

@pytest.mark.parametrize("modo,meses,anos", [
    ("cima", 0, 0), ("cima", 1, 1), ("cima", 12, 1), ("cima", 13, 2), ("cima", 29, 3),
    ("baixo", 29, 2), ("baixo", 11, 0),
    ("proximo", 18, 2), ("proximo", 17, 1), ("proximo", 29, 2),
])
def test_arredondamento(modo, meses, anos):
    assert anos_de_ampliacao(meses, ParametrosRegras(arredondamento=modo)) == anos

def test_janela_sem_ampliacao():
    j = janela_de_artigos(2022, 2025, DeclaracaoArtigoY())
    assert (j.ano_min, j.ano_max, j.anos_extras) == (2022, 2025, 0)

def test_janela_exemplo_do_spec_com_memoria():
    j = janela_de_artigos(2022, 2025, DeclaracaoArtigoY(n_licencas_parentais=1, meses_licenca_medica=5))
    assert (j.ano_min, j.ano_max, j.anos_extras) == (2019, 2025, 3)
    assert j.memoria == (
        "1 licença(s) parental(is): +24 meses",
        "Licença médica: +5 meses",
        "Total: 29 meses → 3 ano(s) a mais (arredondado para cima)",
        "Janela de artigos: 2019–2025",
    )

def test_acumulo_sem_teto():
    j = janela_de_artigos(2022, 2025, DeclaracaoArtigoY(n_licencas_parentais=3, pcd_docente=True, meses_licenca_medica=30))
    assert j.ano_min == 2022 - 11  # 72 + 24 + 30 = 126 meses → 11 anos
```

- [ ] **Step 2:** Rodar `.venv/bin/python -m pytest tests/test_regras.py -q` → os novos falham.
- [ ] **Step 3: Implementar** os itens de *Produces*. "proximo" = meio para cima (`(meses + 6) // 12`). Linhas da memória, nesta ordem e só quando o item for diferente de zero: `"{n} licença(s) parental(is): +{m} meses"`, `"PcD: +{m} meses"`, `"Licença médica: +{m} meses"`; sempre `"Total: {meses} meses → {anos} ano(s) a mais (arredondado {para cima|para baixo|para o mais próximo})"` e `"Janela de artigos: {ano_min}–{ano_max}"` (travessão `–`).
- [ ] **Step 4:** Rodar `.venv/bin/python -m pytest tests/test_regras.py -q` → todos passam.
- [ ] **Step 5:** Em `docs/perguntas-professor.md`, mover para "Já definido" as perguntas 8, 9, 10 e 13 com as respostas: 8 = proposta "meses somados, arredondados para cima" (a validar com o professor); 9 = cada licença parental soma +24 meses; 10 = PcD conta uma vez; 13 = upload do HTML público (não XML). Acrescentar: "PcD é +2 anos (o 'até cinco' do case é erro); artigos distintos, podendo ser da mesma revista; duplicatas contam uma vez".
- [ ] **Step 6: Commit**

```bash
git add src/regras.py tests/test_regras.py docs/perguntas-professor.md
git commit -m "Motor de regras: ampliação da janela (Artigo Y)"
```

---

### Task 4: Integração com a etapa 2

**Files:**
- Modify: `lattes_rank/lattes_rank/banco.py` (`Banco.__init__`)
- Test: `lattes_rank/tests/test_banco.py`
- Create: `src/integracao.py`
- Test: `tests/test_integracao.py`

**Interfaces:**
- Consumes: Tasks 2 e 3; de `lattes_rank`: `parser.decodificar_html(bytes) -> str`, `parser.interpretar_html(html, arquivo) -> Curriculo`, `banco.Banco`, `banco.anos_com_percentil() -> (int, int)`, `ranking.classificar_artigos(artigos, banco, politica, janela_nota) -> list[ArtigoAvaliado]`, `ranking.politica_padrao`, `ranking.politica_estendida(base_min, base_max, anos_retroativos)`, `ranking.PONTUADO`.
- Produces:
  - `Banco(caminho, multithread: bool = False)` — com `True`, conecta com `check_same_thread=False` (seguro: conexão `mode=ro`).
  - Em `src/integracao.py`: `RAIZ: Path`, `CAMINHO_BANCO = RAIZ / "scimago_etl" / "scimago.db"`
  - `abrir_banco(caminho: Path = CAMINHO_BANCO) -> Banco` (sempre `multithread=True`)
  - `ler_html(dados: bytes, nome_arquivo: str) -> Curriculo`
  - `@dataclass(frozen=True) ArtigoNaoEntrou`: `id: int`, `titulo: str | None`, `periodico: str | None`, `ano: int | None`, `status: str`, `motivo: str`
  - `@dataclass AvaliacaoCurriculo`: `curriculo: Curriculo`, `janela: JanelaArtigos`, `janela_nota: tuple[int, int]`, `pontuaveis: list[ArtigoPontuavel]`, `nao_entraram: list[ArtigoNaoEntrou]`
  - `avaliar(curriculo: Curriculo, banco: Banco, declaracao: DeclaracaoArtigoY, params: ParametrosRegras = PARAMETROS_PADRAO) -> AvaliacaoCurriculo`

- [ ] **Step 1: Teste que falha** em `lattes_rank/tests/test_banco.py` (Review Focus 2):

```python
def test_banco_multithread_pode_ser_usado_em_outra_thread(caminho_banco):
    with Banco(caminho_banco, multithread=True) as b:
        resultado = {}
        t = threading.Thread(target=lambda: resultado.update(anos=b.anos_com_percentil()))
        t.start(); t.join()
        assert resultado["anos"] == b.anos_com_percentil()
```

- [ ] **Step 2:** `cd lattes_rank && ../.venv/bin/python -m pytest tests/test_banco.py -q` → falha (`unexpected keyword`). Implementar o parâmetro; rodar de novo → passa; suíte inteira da etapa 2 → `75 passed`.
- [ ] **Step 3: Testes que falham** em `tests/test_integracao.py`. Usar o banco fictício e a fixture da etapa 2: no topo, `import src.integracao` (que já põe `lattes_rank/` no `sys.path`) e `sys.path.insert(0, str(RAIZ / "lattes_rank" / "tests"))` para `from banco_ficticio import criar_banco`; fixture HTML em `lattes_rank/tests/fixtures/artigos_completos.html`.

```python
def test_avaliar_fixture_sem_ampliacao(banco):
    av = avaliar(curriculo_fixture(), banco, DeclaracaoArtigoY())
    assert av.janela_nota == (2022, 2025)
    assert (av.janela.ano_min, av.janela.ano_max) == (2022, 2025)
    assert av.pontuaveis  # a fixture tem artigos que casam com o banco fictício
    assert all(0 < a.percentil <= 1 for a in av.pontuaveis)
    assert all(2022 <= a.ano <= 2025 for a in av.pontuaveis)
    ids = [a.id for a in av.pontuaveis] + [n.id for n in av.nao_entraram]
    assert sorted(ids) == list(range(len(av.curriculo.artigos)))  # todo artigo aparece uma vez

def test_ampliacao_so_acrescenta_artigos_e_nao_muda_percentil(banco):
    base = avaliar(curriculo_fixture(), banco, DeclaracaoArtigoY())
    amp = avaliar(curriculo_fixture(), banco, DeclaracaoArtigoY(n_licencas_parentais=5))
    p_base = {a.id: a.percentil for a in base.pontuaveis}
    p_amp = {a.id: a.percentil for a in amp.pontuaveis}
    assert set(p_base) <= set(p_amp)
    assert all(p_amp[i] == p_base[i] for i in p_base)

def test_duplicata_vai_para_nao_entraram(banco):
    cur = curriculo_fixture()
    primeiro = next(a for a in avaliar(cur, banco, DeclaracaoArtigoY()).pontuaveis)
    cur.artigos.append(cur.artigos[primeiro.id])  # mesmo artigo cadastrado duas vezes
    av = avaliar(cur, banco, DeclaracaoArtigoY())
    dup = [n for n in av.nao_entraram if n.status == "duplicado"]
    assert len(dup) == 1 and dup[0].id == len(cur.artigos) - 1

def test_html_que_nao_e_lattes(banco):  # Review Focus 3
    cur = ler_html(b"<html><body>oi</body></html>", "x.html")
    assert cur.artigos == [] and cur.avisos
    av = avaliar(cur, banco, DeclaracaoArtigoY())
    assert av.pontuaveis == [] and av.nao_entraram == []
```

(`banco` aqui é uma fixture local em `tests/test_integracao.py` que cria o banco fictício em `tmp_path` e abre com `abrir_banco`.) Se a fixture HTML não tiver nenhum artigo que case com o banco fictício, o implementador ajusta o teste para usar o currículo da etapa 2 que o `test_ranking.py` já usa com sucesso.

- [ ] **Step 4:** Rodar `.venv/bin/python -m pytest tests/test_integracao.py -q` → falha de importação.
- [ ] **Step 5: Implementar `src/integracao.py`.** No topo, antes de qualquer import de `lattes_rank`, inserir `RAIZ / "lattes_rank"` em `sys.path` (senão a pasta `lattes_rank/` da raiz vira pacote vazio — ver `lattes_rank/tests/conftest.py`). `avaliar`: janela de nota = `banco.anos_com_percentil()`; janela = `janela_de_artigos(*janela_nota, declaracao, params)`; política = `politica_padrao(*janela_nota)` se `anos_extras == 0`, senão `politica_estendida(*janela_nota, janela.anos_extras)`; `classificar_artigos(curriculo.artigos, ...)`; `id` = índice do artigo no currículo; `pontuado` → `ArtigoPontuavel(percentil=nota.percentil / 100, periodico=periodico_base or periodico_nome, empate_sjr=nota.empate_sjr, doi=artigo.doi, ...)`; os demais → `ArtigoNaoEntrou(status=avaliado.status, motivo=avaliado.motivo)`; passar os pontuáveis por `remover_duplicatas` e mandar os duplicados para `nao_entraram` com `status="duplicado"`, `motivo="mesmo artigo já listado no currículo"`.
- [ ] **Step 6:** Rodar `.venv/bin/python -m pytest tests -q` → tudo passa.
- [ ] **Step 7: Commit**

```bash
git add lattes_rank/lattes_rank/banco.py lattes_rank/tests/test_banco.py src/integracao.py tests/test_integracao.py
git commit -m "Integração da etapa 2 com o motor de regras"
```

---

### Task 5: App Streamlit e instruções de deploy

**Files:**
- Modify (reescrever): `app.py`
- Test: `tests/test_app.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `abrir_banco`, `ler_html`, `avaliar`, `AvaliacaoCurriculo`, `ArtigoNaoEntrou` (Task 4); `DeclaracaoArtigoY`, `preselecionar`, `calcular_nota`, `PARAMETROS_PADRAO` (Tasks 2–3).

- [ ] **Step 1: Teste que falha** em `tests/test_app.py` (o `AppTest` não simula upload; o teste garante que a página sobe com o banco real e mostra o painel do Artigo Y):

```python
from streamlit.testing.v1 import AppTest

def test_app_carrega_sem_erro():
    at = AppTest.from_file("../app.py", default_timeout=30).run()  # caminho relativo a este arquivo de teste
    assert not at.exception
    assert at.title[0].value == "ME315 — Credenciamento Docente"
    assert len(at.number_input) == 2 and len(at.checkbox) == 2
```

- [ ] **Step 2:** Rodar `.venv/bin/python -m pytest tests/test_app.py -q` → falha (app atual não tem os campos).
- [ ] **Step 3: Implementar `app.py`** conforme o esboço da seção 4.3 do spec:
  - `st.set_page_config(page_title="ME315 — Credenciamento Docente")` e `st.title` com o mesmo texto.
  - Banco: função decorada com `@st.cache_resource` que retorna `abrir_banco()`.
  - Upload: `st.file_uploader("Envie o HTML do Lattes (Ctrl+S na página do currículo)", type=["html", "htm"])`, com uma legenda curta explicando como salvar.
  - Painel do Artigo Y, **sempre visível** (mesmo sem arquivo): `number_input` "Nº de licenças parentais" (`min_value=0, step=1`), checkbox "Sou pessoa com deficiência (PcD)", checkbox "Tenho cônjuge ou dependente com deficiência ou condição que demande cuidados contínuos", `number_input` "Meses de licença médica (total)" (`min_value=0, step=1`). Mostrar a janela calculada e a memória num `st.expander`. Sem arquivo, parar aqui com `st.info`.
  - Com arquivo: `ler_html(arquivo.getvalue(), arquivo.name)`; mostrar nome / ID Lattes / data de atualização quando houver e cada aviso com `st.warning`.
  - Seleção: `st.multiselect` com `options` = ids dos pontuáveis, `format_func` = "título — periódico (ano) · p = 0,xx" (vírgula decimal), `default=preselecionar(...)`, `max_selections=4` e **`key=f"selecao_{arquivo.name}_{arquivo.size}_{janela.ano_min}"`**, para a seleção voltar à pré-seleção quando o arquivo ou a janela mudam (Review Focus 4).
  - Tabela (`st.dataframe`) dos escolhidos: Título, Periódico, Ano, Percentil, Conta (≥ 0,25), Contribuição; marcar `*` no percentil quando `empate_sjr` e explicar a marca numa legenda.
  - Resultado: `st.metric("Nota", ...)` com vírgula decimal e 2 casas; `st.success("APTO: nota ≥ 1,25")` ou `st.error("NÃO APTO: nota < 1,25")`.
  - `st.expander("Artigos que não entraram")` com tabela de `nao_entraram` (Título, Periódico, Ano, Motivo).
  - Nenhum número de regra escrito no `app.py`: textos com 1,25 / 0,25 / 4 vêm de `PARAMETROS_PADRAO`.
- [ ] **Step 4:** Rodar `.venv/bin/python -m pytest tests -q` → tudo passa.
- [ ] **Step 5: Verificação manual.** `.venv/bin/streamlit run app.py`; enviar `lattes_rank/tests/fixtures/artigos_completos.html`. Conferir: lista de elegíveis com 4 pré-selecionados; nota e APTO/NÃO APTO; trocar a seleção recalcula; marcar 1 licença parental faz a janela virar 2020–2025, a lista ganhar artigos de 2020–2021 (se houver) e a seleção voltar à pré-seleção sem erro; "Artigos que não entraram" lista os motivos. Enviar um `.html` qualquer (não Lattes): aparece aviso e nenhuma exceção.
- [ ] **Step 6: README.** Substituir a seção "Estrutura" pela atual (sem os stubs `src/lattes.py`, `sjr.py`, `percentil.py`, `db.py` descritos como peças do fluxo; citar `src/regras.py`, `src/integracao.py`, `app.py`). Acrescentar "Regras do credenciamento" (resumo da seção 2 do spec, com link para ele) e "Deploy no Streamlit Cloud" com o checklist:
  1. Fazer o merge das branches na `main` (o banco `scimago_etl/scimago.db` precisa estar na `main`).
  2. Em share.streamlit.io, entrar com o GitHub do dono do repositório → *Create app* → repositório `Jhuansolis/me315-credenciamento`, branch `main`, arquivo `app.py`.
  3. Em *Advanced settings*, escolher Python 3.12 (ou a versão usada no Step 4 da Task 1).
  4. Abrir o link gerado, enviar o HTML da fixture e conferir a nota.
- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_app.py README.md
git commit -m "App Streamlit: upload do Lattes, Artigo Y, seleção e nota"
```
