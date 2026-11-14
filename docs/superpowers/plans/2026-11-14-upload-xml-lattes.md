# Upload do XML do Lattes — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** o app e o CLI aceitam o currículo Lattes em HTML, XML ou ZIP (com o XML dentro) e dão a mesma nota; licenças/PcD do XML viram um lembrete no painel do Artigo Y.

**Architecture:** um leitor de XML novo em `lattes_rank` monta o mesmo `Curriculo`/`Artigo` do leitor de HTML; uma função de entrada única detecta o formato pelo conteúdo. `src/integracao.py` expõe essa entrada e o texto do lembrete ao `app.py`. Ranking, regras e relatório não mudam.

**Tech Stack:** Python 3.12+, `xml.etree.ElementTree`, `zipfile`, BeautifulSoup (já usado), Streamlit ≥ 1.67, pytest.

**Spec:** `docs/superpowers/specs/2026-11-14-upload-xml-lattes-design.md`

## Global Constraints

- Nenhuma dependência nova em `requirements.txt` / `lattes_rank/requirements.txt`.
- O leitor de XML não lê nem guarda dados pessoais: só `NUMERO-IDENTIFICADOR`, `NOME-COMPLETO`, `DATA-ATUALIZACAO`, `PCD`, `LICENCAS` e os artigos.
- Nenhum XML real no repositório: a fixture tem cabeçalho fictício (o bloco de artigos é bibliografia pública, a mesma da fixture HTML já versionada).
- Ranking (`ranking.py`), regras (`src/regras.py`) e relatório (`relatorio.py`) não ganham ramificação por formato.
- Datas no formato `DD/MM/AAAA` (como o HTML já devolve `data_atualizacao`).
- Erro de arquivo vira `ArquivoInvalido` (subclasse de `ValueError`) com mensagem em português; o app mostra `st.error` e nunca traceback.
- Rodar testes: `python -m pytest tests` (raiz) e `cd lattes_rank && python -m pytest`.

## Review Focus

1. Artigo no XML sem `ISSN`/`ANO-DO-ARTIGO` (ou vazios) → `Artigo` com `None` e aviso, sem exceção (o ranking já explica "sem ISSN"). Teste na Task 1.
2. ZIP sem `.xml` ou com mais de um `.xml` → `ArquivoInvalido` com mensagem clara. Teste na Task 2.
3. HTML que começa com `<?xml ...?>` (XHTML salvo pelo navegador) continua indo para o leitor de HTML. Teste na Task 2.
4. XML com `<!DOCTYPE`/`<!ENTITY` ou malformado → `ArquivoInvalido`, nunca expansão de entidades. Testes nas Tasks 1 e 2.
5. XML declarado em UTF-8 (não só ISO-8859-1) lê acentos corretamente. Teste na Task 1.

---

### Task 1: Leitor de XML

**Files:**
- Modify: `lattes_rank/lattes_rank/parser.py` (dataclasses `Licenca`, `Curriculo`)
- Create: `lattes_rank/lattes_rank/parser_xml.py`
- Create: `lattes_rank/tests/fixtures/artigos_completos.xml`
- Test: `lattes_rank/tests/test_parser_xml.py`

**Interfaces:**
- Produces (em `parser.py`):
  - `@dataclass(frozen=True) class Licenca: tipo: str; inicio: str | None; fim: str | None` (datas `DD/MM/AAAA`)
  - `Curriculo` ganha, no fim, `licencas: list[Licenca] = field(default_factory=list)` e `pcd: str | None = None` (valor bruto do atributo `PCD`, `None` se ausente ou vazio). O leitor de HTML não muda: deixa os padrões.
- Produces (em `parser_xml.py`):
  - `class ArquivoInvalido(ValueError)`
  - `interpretar_xml(dados: bytes, arquivo: str = "<memória>") -> Curriculo`

- [ ] **Step 1: Gerar a fixture (comando único, não versionar o script)**

A partir do XML real (`~/Downloads/9315014843913122.xml`), crie a fixture só com a lista de `ARTIGO-PUBLICADO` e um cabeçalho fictício. Rode na raiz do repositório:

```bash
python3 -I - ~/Downloads/9315014843913122.xml lattes_rank/tests/fixtures/artigos_completos.xml <<'EOF'
import sys, xml.etree.ElementTree as ET
real = ET.parse(sys.argv[1]).getroot()
cv = ET.Element("CURRICULO-VITAE", {"SISTEMA-ORIGEM-XML": "LATTES_OFFLINE",
     "NUMERO-IDENTIFICADOR": "1234567890123456", "DATA-ATUALIZACAO": "26102026", "HORA-ATUALIZACAO": "092500"})
dg = ET.SubElement(cv, "DADOS-GERAIS", {"NOME-COMPLETO": "Fulana de Tal Conceição", "PCD": "SIM"})
lic = ET.SubElement(dg, "LICENCAS")
ET.SubElement(lic, "LICENCA", {"TIPO-LICENCA": "PATERNIDADE", "DATA-INICIO-LICENCA": "10032022",
     "DATA-FIM-LICENCA": "29032022"})  # datas fictícias
pb = ET.SubElement(cv, "PRODUCAO-BIBLIOGRAFICA")
pb.append(real.find("PRODUCAO-BIBLIOGRAFICA/ARTIGOS-PUBLICADOS"))
ET.ElementTree(cv).write(sys.argv[2], encoding="ISO-8859-1", xml_declaration=True)
EOF
grep -c "CPF\|PASSAPORTE\|NOME-DO-PAI" lattes_rank/tests/fixtures/artigos_completos.xml   # esperado: 0
```

- [ ] **Step 2: Escrever os testes que falham** em `lattes_rank/tests/test_parser_xml.py`

```python
FIXTURE_XML = FIXTURES / "artigos_completos.xml"   # FIXTURES de conftest

def test_le_os_17_artigos_com_mesmos_ano_issn_doi_do_html(curriculo):
    cv = interpretar_xml(FIXTURE_XML.read_bytes(), "fixture.xml")
    assert len(cv.artigos) == 17
    assert [a.sequencia for a in cv.artigos] == list(range(1, 18))   # ordem do arquivo
    assert sorted((a.ano, a.issn, a.doi) for a in cv.artigos) == \
           sorted((a.ano, a.issn, a.doi) for a in curriculo.artigos)   # curriculo = fixture HTML
    assert cv.avisos == []

def test_cabecalho_licencas_e_pcd():
    cv = interpretar_xml(FIXTURE_XML.read_bytes(), "fixture.xml")
    assert (cv.nome, cv.id_lattes, cv.data_atualizacao) == ("Fulana de Tal Conceição", "1234567890123456", "26/10/2026")
    assert cv.licencas == [Licenca("PATERNIDADE", "10/03/2022", "29/03/2022")]
    assert cv.pcd == "SIM"
    assert cv.arquivo == "fixture.xml"

def test_campos_do_artigo():
    cv = interpretar_xml(FIXTURE_XML.read_bytes())
    eciperu = next(a for a in cv.artigos if a.issn == "18130194")
    assert (eciperu.ano, eciperu.doi, eciperu.periodico_nome, eciperu.issn_bruto) == (2009, None, "ECIPERU", "18130194")
    assert eciperu.titulo.startswith("Factores que influyen")

def test_xml_utf8_com_acento():   # Review Focus 5
    xml = '<?xml version="1.0" encoding="UTF-8"?><CURRICULO-VITAE NUMERO-IDENTIFICADOR="1"><DADOS-GERAIS NOME-COMPLETO="João Ninguém"/></CURRICULO-VITAE>'
    cv = interpretar_xml(xml.encode("utf-8"))
    assert cv.nome == "João Ninguém" and cv.artigos == [] and cv.licencas == [] and cv.pcd is None
    assert any("Nenhum artigo" in a for a in cv.avisos)

def test_artigo_sem_issn_e_sem_ano_vira_none_com_aviso():   # Review Focus 1
    xml = (b'<?xml version="1.0"?><CURRICULO-VITAE><PRODUCAO-BIBLIOGRAFICA><ARTIGOS-PUBLICADOS>'
           b'<ARTIGO-PUBLICADO><DADOS-BASICOS-DO-ARTIGO TITULO-DO-ARTIGO="T"/>'
           b'<DETALHAMENTO-DO-ARTIGO ISSN=""/></ARTIGO-PUBLICADO>'
           b'</ARTIGOS-PUBLICADOS></PRODUCAO-BIBLIOGRAFICA></CURRICULO-VITAE>')
    cv = interpretar_xml(xml)
    assert cv.artigos[0].issn is None and cv.artigos[0].ano is None
    assert any("artigo 1" in a and "ano" in a for a in cv.avisos)

@pytest.mark.parametrize("dados", [
    b"<CURRICULO-VITAE><nao-fecha>",
    b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaa">]><CURRICULO-VITAE/>',   # Review Focus 4
    b'<?xml version="1.0"?><outra-coisa/>',
])
def test_xml_invalido_levanta_arquivo_invalido(dados):
    with pytest.raises(ArquivoInvalido):
        interpretar_xml(dados)
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd lattes_rank && python -m pytest tests/test_parser_xml.py -q`
Expected: FAIL (ImportError: `parser_xml` / `Licenca`)

- [ ] **Step 4: Implementar** `Licenca` e os campos novos em `parser.py`, e `interpretar_xml` em `parser_xml.py`

- Recusar antes de analisar se `b"<!DOCTYPE"` ou `b"<!ENTITY"` aparecer nos dados; `ET.ParseError` → `ArquivoInvalido("O arquivo XML está corrompido ou incompleto.")`; raiz diferente de `CURRICULO-VITAE` → `ArquivoInvalido("O XML enviado não é um currículo Lattes.")`. Passe **bytes** ao `ET.fromstring` (respeita o `encoding` declarado).
- Artigos: `.//ARTIGOS-PUBLICADOS/ARTIGO-PUBLICADO`, em ordem, com `sequencia` de 1 a N. Campos: `DADOS-BASICOS-DO-ARTIGO` (`ANO-DO-ARTIGO`, `TITULO-DO-ARTIGO`, `DOI`) e `DETALHAMENTO-DO-ARTIGO` (`TITULO-DO-PERIODICO-OU-REVISTA`, `ISSN` → `issn_bruto`, e `normalizar_issn` → `issn`). Valores vazios viram `None`. Ano que não é `\d{4}` → `None` e aviso `"artigo {n}: ano não encontrado."` (mesmo texto do HTML).
- Datas `DDMMAAAA` → `DD/MM/AAAA`; qualquer outra coisa → `None`.
- Sem artigos → aviso `"Nenhum artigo encontrado no XML."`.

- [ ] **Step 5: Rodar e ver passar**

Run: `cd lattes_rank && python -m pytest -q`
Expected: todos passam (os antigos também).

- [ ] **Step 6: Commit**

```bash
git add lattes_rank/lattes_rank/parser.py lattes_rank/lattes_rank/parser_xml.py lattes_rank/tests/test_parser_xml.py lattes_rank/tests/fixtures/artigos_completos.xml
git commit -m "lattes_rank: leitor do XML do Lattes (mesmo Curriculo do HTML, com licenças e PcD)"
```

---

### Task 2: Entrada única (HTML/XML/ZIP) e CLI

**Files:**
- Create: `lattes_rank/lattes_rank/entrada.py`
- Modify: `lattes_rank/lattes_rank/cli.py` (`EXTENSOES`, uso de `ler_arquivo`, texto de ajuda)
- Modify: `lattes_rank/README.md` (como obter o XML; ENTRADA aceita `.xml`/`.zip`; tabela de módulos)
- Test: `lattes_rank/tests/test_entrada.py`, `lattes_rank/tests/test_cli.py`

**Interfaces:**
- Consumes: `interpretar_xml`, `ArquivoInvalido` (Task 1); `interpretar_html`, `decodificar_html` (`parser.py`).
- Produces (em `entrada.py`):
  - `LIMITE_DESCOMPACTADO = 20 * 1024 * 1024`
  - `ler_bytes(dados: bytes, arquivo: str = "<memória>") -> Curriculo`
  - `ler_arquivo(caminho: str | Path) -> Curriculo`
  - reexporta `ArquivoInvalido`

- [ ] **Step 1: Escrever os testes que falham** em `test_entrada.py`

```python
XML = (FIXTURES / "artigos_completos.xml").read_bytes()

def _zip(conteudo: dict[str, bytes]) -> bytes:   # ZIP em memória (io.BytesIO + zipfile.ZipFile "w")
    ...

def test_html_vai_para_o_leitor_de_html(html_artigos):
    assert len(ler_bytes(html_artigos.encode("utf-8"), "a.html").artigos) == 17

def test_xml_vai_para_o_leitor_de_xml():
    cv = ler_bytes((FIXTURES / "artigos_completos.xml").read_bytes(), "a.xml")
    assert len(cv.artigos) == 17 and cv.licencas

def test_detecta_pelo_conteudo_e_nao_pela_extensao():
    assert ler_bytes(XML, "nome_errado.html").licencas

def test_xhtml_com_declaracao_xml_continua_html():   # Review Focus 3
    dados = b'<?xml version="1.0" encoding="UTF-8"?><html><body><p>nada</p></body></html>'
    cv = ler_bytes(dados, "x.html")
    assert cv.artigos == [] and any("Nenhum artigo encontrado no HTML" in a for a in cv.avisos)

def test_zip_com_um_xml():
    assert len(ler_bytes(_zip({"curriculo.xml": XML}), "cv.zip").artigos) == 17

@pytest.mark.parametrize("conteudo", [{}, {"a.xml": XML, "b.xml": XML}, {"leia.txt": b"oi"}])
def test_zip_sem_exatamente_um_xml_levanta(conteudo):   # Review Focus 2
    with pytest.raises(ArquivoInvalido, match="exatamente um arquivo .xml"):
        ler_bytes(_zip(conteudo), "cv.zip")

def test_zip_grande_demais_levanta(monkeypatch):
    monkeypatch.setattr(entrada, "LIMITE_DESCOMPACTADO", 10)
    with pytest.raises(ArquivoInvalido, match="grande demais"):
        ler_bytes(_zip({"curriculo.xml": XML}), "cv.zip")

def test_ler_arquivo_do_disco():
    assert len(ler_arquivo(FIXTURES / "artigos_completos.xml").artigos) == 17
```

Em `test_cli.py`, acrescente:

```python
def test_cli_le_xml_com_o_mesmo_top_do_html(caminho_banco, tmp_path):
    def top(entrada):
        saida = tmp_path / f"{entrada.suffix}.json"
        assert main([str(entrada), "--db", str(caminho_banco), "--json", str(saida)]) == 0
        return [l["periodico"] for l in json.loads(saida.read_text(encoding="utf-8"))["top"]]
    assert top(FIXTURE.with_suffix(".xml")) == top(FIXTURE)

def test_cli_xml_invalido_sai_com_codigo_2(caminho_banco, tmp_path, capsys):
    ruim = tmp_path / "ruim.xml"; ruim.write_bytes(b'<?xml version="1.0"?><outra-coisa/>')
    assert main([str(ruim), "--db", str(caminho_banco)]) == 2
    assert "não é um currículo Lattes" in capsys.readouterr().err
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd lattes_rank && python -m pytest tests/test_entrada.py tests/test_cli.py -q`
Expected: FAIL (ImportError `entrada`; CLI não lê XML)

- [ ] **Step 3: Implementar `entrada.py` e ajustar o CLI**

Regra de detecção (nesta ordem):
1. Começa com `b"PK\x03\x04"` → ZIP: exatamente um membro terminando em `.xml` (sem diferenciar maiúsculas; ignore diretórios), senão `ArquivoInvalido("O ZIP deve conter exatamente um arquivo .xml do Lattes.")`. Se `file_size` do membro > `LIMITE_DESCOMPACTADO` → `ArquivoInvalido("O XML dentro do ZIP é grande demais.")`; leia no máximo `LIMITE_DESCOMPACTADO + 1` bytes. `zipfile.BadZipFile` → `ArquivoInvalido("O arquivo ZIP está corrompido.")`. O conteúdo vai para `interpretar_xml`.
2. Nos primeiros 4096 bytes (sem BOM, sem espaços à esquerda, em minúsculas): começa com `<?xml` ou `<curriculo-vitae` **e** não contém `<html` → `interpretar_xml`.
3. Caso contrário → `interpretar_html(decodificar_html(dados), arquivo)`.

No CLI: `EXTENSOES = {".html", ".htm", ".xml", ".zip"}`, trocar `ler_curriculo` por `ler_arquivo`, atualizar o `help` de `entrada` e a mensagem de pasta vazia. `ArquivoInvalido` já cai no `except ValueError`.

- [ ] **Step 4: Rodar e ver passar**

Run: `cd lattes_rank && python -m pytest -q`
Expected: todos passam.

- [ ] **Step 5: Atualizar `lattes_rank/README.md`**: seção "Como obter o XML do Lattes" (o docente exporta o próprio currículo em XML pela plataforma; `.xml` ou `.zip` servem), ENTRADA aceita `.html`/`.htm`/`.xml`/`.zip`, e as linhas de `parser_xml.py` e `entrada.py` na tabela de módulos.

- [ ] **Step 6: Commit**

```bash
git add lattes_rank/lattes_rank/entrada.py lattes_rank/lattes_rank/cli.py lattes_rank/tests/test_entrada.py lattes_rank/tests/test_cli.py lattes_rank/README.md
git commit -m "lattes_rank: entrada única HTML/XML/ZIP com detecção pelo conteúdo; CLI lê XML"
```

---

### Task 3: App e integração

**Files:**
- Modify: `src/integracao.py` (troca `ler_html` por `ler_arquivo`; `lembrete_artigo_y`; reexporta `ArquivoInvalido`)
- Modify: `app.py`
- Delete: `src/lattes.py`
- Modify: `tests/test_integracao.py` (import `ler_arquivo`), `tests/test_app.py`, `tests/_app_com_upload.py` (só renomear a variável de ambiente para `ME315_ARQUIVO_FALSO`)
- Modify: `README.md`, `docs/superpowers/specs/2026-11-13-motor-regras-streamlit-design.md` (tirar "upload de XML" dos não-objetivos, com remissão à spec nova)

**Interfaces:**
- Consumes: `ler_bytes`, `ArquivoInvalido` (Task 2); `Curriculo.licencas`, `Curriculo.pcd`, `Licenca` (Task 1).
- Produces (em `src/integracao.py`):
  - `ler_arquivo(dados: bytes, nome_arquivo: str) -> Curriculo` (substitui `ler_html`)
  - `lembrete_artigo_y(curriculo: Curriculo) -> str | None`
  - `ArquivoInvalido`

- [ ] **Step 1: Escrever os testes que falham**

Em `tests/test_integracao.py` (troque `ler_html` por `ler_arquivo` nos usos existentes):

```python
FIXTURE_XML = FIXTURE.with_suffix(".xml")

def test_xml_e_html_dao_a_mesma_avaliacao(banco):
    h = avaliar(ler_arquivo(FIXTURE.read_bytes(), "a.html"), banco, DeclaracaoArtigoY())
    x = avaliar(ler_arquivo(FIXTURE_XML.read_bytes(), "a.xml"), banco, DeclaracaoArtigoY())
    chave = lambda a: (a.ano, a.periodico, a.percentil)
    assert sorted(map(chave, h.pontuaveis)) == sorted(map(chave, x.pontuaveis))

def test_lembrete_com_licencas_e_pcd():
    texto = lembrete_artigo_y(ler_arquivo(FIXTURE_XML.read_bytes(), "a.xml"))
    assert "1 licença" in texto and "PATERNIDADE de 10/03/2022 a 29/03/2022" in texto
    assert "PcD: SIM" in texto
    assert "não decide" in texto

def test_sem_lembrete_para_html_ou_xml_sem_licenca():
    assert lembrete_artigo_y(ler_arquivo(FIXTURE.read_bytes(), "a.html")) is None
    vazio = b'<?xml version="1.0"?><CURRICULO-VITAE><DADOS-GERAIS PCD="NAO"/></CURRICULO-VITAE>'
    assert lembrete_artigo_y(ler_arquivo(vazio, "a.xml")) is None
```

Em `tests/test_app.py`:

```python
FIXTURE_XML = FIXTURE.with_suffix(".xml")

def test_upload_do_xml_da_apto_e_mostra_lembrete(monkeypatch):
    at = _app_com_arquivo(FIXTURE_XML, monkeypatch)
    assert not at.exception
    assert [s.value for s in at.success] == ["APTO: nota ≥ 1,25"]
    assert any("PATERNIDADE" in i.value for i in at.info)
    assert at.number_input[0].value == 0          # lembrete não preenche o campo

def test_upload_de_xml_invalido_mostra_erro_sem_excecao(tmp_path, monkeypatch):
    ruim = tmp_path / "ruim.xml"; ruim.write_bytes(b'<?xml version="1.0"?><outra-coisa/>')
    at = _app_com_arquivo(ruim, monkeypatch)
    assert not at.exception
    assert [e.value for e in at.error] == ["O XML enviado não é um currículo Lattes."]
    assert not at.metric

def test_upload_do_html_nao_mostra_lembrete(monkeypatch):
    at = _app_com_arquivo(FIXTURE, monkeypatch)
    assert not any("licença" in i.value for i in at.info)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests -q`
Expected: FAIL (ImportError `ler_arquivo` / `lembrete_artigo_y`)

- [ ] **Step 3: Implementar**

`lembrete_artigo_y`: `None` se não há licenças e `pcd` é `None` ou `"NAO"`/`"NÃO"`. Senão, texto fixo:

```
O XML do Lattes registra: {n} licença(s) ({TIPO} de {inicio} a {fim}; ...). PcD: {pcd}.
Confira e preencha os campos abaixo; o sistema não decide se cada licença conta.
```

(omita a parte das licenças ou a do PcD quando não houver; data ausente vira "?"; use "1 licença"/"2 licenças").

`app.py`:
- `file_uploader("Envie o currículo Lattes (HTML ou XML)", type=["html", "htm", "xml", "zip"])`; caption explicando os dois caminhos: salvar a página (Ctrl+S, "somente HTML") **ou** exportar o XML do próprio currículo na Plataforma Lattes (`.xml` ou `.zip`). Mantenha "Nada do que você enviar é gravado."
- Logo após o uploader, se houver arquivo: `curriculo = curriculo_do_arquivo(...)` (agora chamando `ler_arquivo`) dentro de `try/except ArquivoInvalido as erro: st.error(str(erro)); st.stop()`.
- Logo depois do `st.subheader("Artigo Y …")`, se `curriculo` e `lembrete_artigo_y(curriculo)` → `st.info(texto)`.
- O resto do fluxo (nome, avisos, avaliação) não muda; o `st.info` de "Envie o …" passa a dizer "Envie o currículo Lattes (HTML ou XML) para ver os artigos e a nota."

Apague `src/lattes.py`. Atualize o `README.md` da raiz (primeira frase, "Estrutura" e a nota do deploy citando que o XML também serve) e a linha de não-objetivos da spec antiga.

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests -q && (cd lattes_rank && python -m pytest -q)`
Expected: todos passam.

- [ ] **Step 5: Conferir no app de verdade**

Run: `streamlit run app.py`, senha `1234`, enviar `lattes_rank/tests/fixtures/artigos_completos.xml` e depois o `.html`.
Expected: mesma nota e APTO nos dois; o lembrete azul aparece só com o XML, sob "Artigo Y"; um `.txt` renomeado para `.xml` mostra erro vermelho.

- [ ] **Step 6: Commit**

```bash
git add -A src/ app.py tests/ README.md docs/superpowers/specs/2026-11-13-motor-regras-streamlit-design.md
git commit -m "App: aceita o XML do Lattes (e .zip); lembrete de licenças/PcD no Artigo Y"
```
