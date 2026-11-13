from pathlib import Path

from streamlit.testing.v1 import AppTest

FIXTURE = Path(__file__).resolve().parent.parent / "lattes_rank" / "tests" / "fixtures" / "artigos_completos.html"


def _app_com_arquivo(caminho, monkeypatch):
    monkeypatch.setenv("ME315_HTML_FALSO", str(caminho))
    return AppTest.from_file("_app_com_upload.py", default_timeout=60).run()


def _textos(at):
    return [m.value for m in at.markdown] + [c.value for c in at.caption]


def test_app_carrega_sem_erro():
    at = AppTest.from_file("../app.py", default_timeout=30).run()  # caminho relativo a este arquivo de teste
    assert not at.exception
    assert at.title[0].value == "ME315 — Credenciamento Docente"
    assert len(at.number_input) == 2 and len(at.checkbox) == 2


def test_app_mudar_licencas_sem_arquivo_amplia_a_janela():
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    at.number_input[0].set_value(1).run()
    assert not at.exception
    assert at.number_input[0].value == 1
    assert "**Janela de artigos: 2020–2025**" in _textos(at)  # 1 licença = +24 meses = +2 anos


def test_upload_da_fixture_pre_seleciona_e_da_apto(monkeypatch):
    at = _app_com_arquivo(FIXTURE, monkeypatch)
    assert not at.exception
    assert at.multiselect and at.multiselect[0].value
    assert [s.value for s in at.success] == ["APTO: nota ≥ 1,25"]
    assert not at.error
    assert "**Janela de artigos: 2022–2025**" in _textos(at)


def test_upload_da_fixture_mudar_licencas_amplia_a_janela_sem_excecao(monkeypatch):
    at = _app_com_arquivo(FIXTURE, monkeypatch)
    at.number_input[0].set_value(1).run()
    assert not at.exception
    assert "**Janela de artigos: 2020–2025**" in _textos(at)
    at.number_input[0].set_value(0).run()
    assert not at.exception
    assert "**Janela de artigos: 2022–2025**" in _textos(at)


def test_upload_de_html_que_nao_e_lattes_da_aviso_nota_zero_e_nao_apto(tmp_path, monkeypatch):
    html = tmp_path / "outra.html"
    html.write_text("<html><body><p>nada de Lattes aqui</p></body></html>", encoding="utf-8")
    at = _app_com_arquivo(html, monkeypatch)
    assert not at.exception
    assert at.warning
    assert at.metric[0].value == "0,0000"
    assert [e.value for e in at.error] == ["NÃO APTO: nota < 1,25"]


def test_notas_mostram_4_casas_para_nao_contradizer_o_veredito(monkeypatch):
    at = _app_com_arquivo(FIXTURE, monkeypatch)
    nota = at.metric[0].value
    assert len(nota.split(",")[1]) == 4
