import sys
from pathlib import Path

# O Streamlit Cloud (e o AppTest) nem sempre põem a pasta do app no sys.path.
_RAIZ = str(Path(__file__).resolve().parent)
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

import hmac  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.integracao import abrir_banco, avaliar, ler_html  # noqa: E402
from src.regras import (  # noqa: E402
    PARAMETROS_PADRAO,
    DeclaracaoArtigoY,
    calcular_nota,
    janela_de_artigos,
    preselecionar,
)

TITULO = "ME315 — Credenciamento Docente"
PARAMS = PARAMETROS_PADRAO

st.set_page_config(page_title=TITULO)

SENHA_PADRAO = "1234"


def senha_esperada() -> str:
    """Senha dos secrets do Streamlit (chave `senha`); sem secrets configurados, 1234."""
    try:
        return str(st.secrets.get("senha", SENHA_PADRAO))
    except FileNotFoundError:  # nenhum secrets.toml (rodando local)
        return SENHA_PADRAO


def exigir_senha() -> None:
    """Mostra a tela de senha e para o app até a senha certa ser digitada."""
    if st.session_state.get("autenticado"):
        return
    st.title(TITULO)
    with st.form("login"):
        senha = st.text_input("Senha do departamento", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        if hmac.compare_digest(senha.encode(), senha_esperada().encode()):
            st.session_state["autenticado"] = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


exigir_senha()


@st.cache_resource
def banco_scimago():
    return abrir_banco()


@st.cache_data(show_spinner="Lendo o currículo...")
def curriculo_do_arquivo(dados: bytes, nome: str):
    # o parse do HTML leva ~1 s: a chave do cache são os bytes do arquivo
    return ler_html(dados, nome)


def numero(valor: float, casas: int = 4) -> str:
    """Formata com vírgula decimal (padrão brasileiro).

    4 casas por padrão: percentil, contribuição e nota (0–1) têm exatamente 4 casas
    (vêm de 0–100 com 2); arredondar para 2 mostraria, por ex., 0,25 com "Conta: não".
    Os limites (0,25 e 1,25) são formatados com 2 casas.
    """
    return f"{valor:.{casas}f}".replace(".", ",")


st.title(TITULO)
banco = banco_scimago()

arquivo = st.file_uploader(
    "Envie o HTML do Lattes (Ctrl+S na página do currículo)", type=["html", "htm"]
)
st.caption(
    "Abra o currículo em lattes.cnpq.br, resolva o captcha e salve a página "
    "(Ctrl+S, \"Página da Web, somente HTML\"). Nada do que você enviar é gravado."
)

st.subheader("Artigo Y — ampliação do período (opcional)")
col1, col2 = st.columns(2)
with col1:
    n_parentais = st.number_input("Nº de licenças parentais", min_value=0, step=1)
    meses_medica = st.number_input("Meses de licença médica (total)", min_value=0, step=1)
with col2:
    # wrap=True: dentro de st.columns o padrão (None) corta o rótulo com "..."
    pcd_docente = st.checkbox("Sou pessoa com deficiência (PcD)", wrap=True)
    pcd_familiar = st.checkbox(
        "Tenho cônjuge ou dependente com deficiência ou condição que demande cuidados contínuos",
        wrap=True,
    )
declaracao = DeclaracaoArtigoY(
    n_licencas_parentais=int(n_parentais),
    pcd_docente=pcd_docente,
    pcd_familiar=pcd_familiar,
    meses_licenca_medica=int(meses_medica),
)


def mostrar_janela(janela) -> None:
    st.markdown(f"**Janela de artigos: {janela.ano_min}–{janela.ano_max}**")
    with st.expander("Memória de cálculo"):
        for linha in janela.memoria:
            st.write(linha)


if arquivo is None:
    mostrar_janela(janela_de_artigos(*banco.anos_com_percentil(), declaracao, PARAMS))
    st.info("Envie o HTML do currículo Lattes para ver os artigos e a nota.")
    st.stop()

curriculo = curriculo_do_arquivo(arquivo.getvalue(), arquivo.name)
if curriculo.nome:
    st.markdown(f"**{curriculo.nome}**")
if curriculo.id_lattes:
    st.write(f"ID Lattes: {curriculo.id_lattes}")
if curriculo.data_atualizacao:
    st.write(f"Última atualização do currículo: {curriculo.data_atualizacao}")
for aviso in curriculo.avisos:
    st.warning(aviso)

avaliacao = avaliar(curriculo, banco, declaracao, PARAMS)
janela = avaliacao.janela
mostrar_janela(janela)

st.subheader("Artigos elegíveis (pontuados)")
por_id = {a.id: a for a in avaliacao.pontuaveis}
escolhidos = []
if not por_id:
    st.info("Nenhum artigo do currículo pôde ser pontuado.")
else:
    ids = st.multiselect(
        f"Escolha até {PARAMS.max_artigos} artigos",
        options=list(por_id),
        default=preselecionar(avaliacao.pontuaveis, PARAMS),
        format_func=lambda i: (
            f"{por_id[i].titulo or '(sem título)'} — {por_id[i].periodico} "
            f"({por_id[i].ano}) · p = {numero(por_id[i].percentil)}"
        ),
        max_selections=PARAMS.max_artigos,
        # nova chave quando o arquivo ou a janela mudam: a seleção volta à pré-seleção
        key=f"selecao_{arquivo.name}_{arquivo.size}_{janela.ano_min}",
    )
    escolhidos = [por_id[i] for i in ids]

resultado = calcular_nota(escolhidos, PARAMS)
if resultado.itens:
    st.dataframe(
        pd.DataFrame(
            {
                "Título": i.artigo.titulo or "",
                "Periódico": i.artigo.periodico,
                "Ano": i.artigo.ano,
                "Percentil": numero(i.artigo.percentil) + ("*" if i.artigo.empate_sjr else ""),
                f"Conta (≥ {numero(PARAMS.corte_individual, 2)})": "sim" if i.conta else "não",
                "Contribuição": numero(i.contribuicao),
            }
            for i in resultado.itens
        ),
        hide_index=True,
    )
    if any(i.artigo.empate_sjr for i in resultado.itens):
        st.caption("* percentil com empate de SJR entre categorias do periódico.")

st.metric("Nota", numero(resultado.total))
if resultado.apto:
    st.success(f"APTO: nota ≥ {numero(PARAMS.nota_minima, 2)}")
else:
    st.error(f"NÃO APTO: nota < {numero(PARAMS.nota_minima, 2)}")

with st.expander("Artigos que não entraram"):
    if avaliacao.nao_entraram:
        st.dataframe(
            pd.DataFrame(
                {
                    "Título": n.titulo or "",
                    "Periódico": n.periodico or "",
                    "Ano": n.ano,
                    "Motivo": n.motivo,
                }
                for n in avaliacao.nao_entraram
            ),
            hide_index=True,
        )
    else:
        if curriculo.artigos:
            st.write("Nenhum artigo ficou de fora.")
        else:
            st.write("Nenhum artigo encontrado no arquivo.")
