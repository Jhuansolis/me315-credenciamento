from pathlib import Path

from streamlit.testing.v1 import AppTest

FIXTURE = Path(__file__).resolve().parent.parent / "lattes_rank" / "tests" / "fixtures" / "artigos_completos.html"
FIXTURE_XML = FIXTURE.with_suffix(".xml")


def _app_com_arquivo(caminho, monkeypatch):
    monkeypatch.setenv("ME315_ARQUIVO_FALSO", str(caminho))
    return _autenticado(AppTest.from_file("_app_com_upload.py", default_timeout=60)).run()


def _autenticado(at):
    at.session_state["autenticado"] = True  # pula a tela de senha
    return at


def _app():
    return AppTest.from_file("../app.py", default_timeout=30)  # caminho relativo a este arquivo de teste


def _textos(at):
    return [m.value for m in at.markdown] + [c.value for c in at.caption]


def test_app_carrega_sem_erro():
    at = _autenticado(_app()).run()
    assert not at.exception
    assert at.title[0].value == "ME315 — Credenciamento Docente"
    assert len(at.number_input) == 2 and len(at.checkbox) == 2


def test_app_mudar_licencas_sem_arquivo_amplia_a_janela():
    at = _autenticado(_app()).run()
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


def test_sem_senha_so_aparece_a_tela_de_senha():
    at = _app().run()
    assert not at.exception
    assert len(at.text_input) == 1 and not at.number_input


def test_senha_errada_mostra_erro_e_nao_libera():
    at = _app().run()
    at.text_input[0].input("0000")
    at.button[0].click().run()
    assert not at.exception
    assert [e.value for e in at.error] == ["Senha incorreta."]
    assert not at.number_input


def test_senha_1234_libera_o_calculo():
    at = _app().run()
    at.text_input[0].input("1234")
    at.button[0].click().run()
    assert not at.exception
    assert not at.error
    assert len(at.number_input) == 2 and len(at.checkbox) == 2


def test_upload_do_xml_da_apto_e_mostra_lembrete(monkeypatch):
    at = _app_com_arquivo(FIXTURE_XML, monkeypatch)
    assert not at.exception
    assert [s.value for s in at.success] == ["APTO: nota ≥ 1,25"]
    assert any("PATERNIDADE" in i.value for i in at.info)
    assert at.number_input[0].value == 0  # o lembrete não preenche o campo


def test_upload_de_xml_invalido_mostra_erro_sem_excecao(tmp_path, monkeypatch):
    ruim = tmp_path / "ruim.xml"
    ruim.write_bytes(b'<?xml version="1.0"?><outra-coisa/>')
    at = _app_com_arquivo(ruim, monkeypatch)
    assert not at.exception
    assert [e.value for e in at.error] == ["O XML enviado não é um currículo Lattes."]
    assert not at.metric


def test_upload_do_html_nao_mostra_lembrete(monkeypatch):
    at = _app_com_arquivo(FIXTURE, monkeypatch)
    assert not any("licença" in i.value for i in at.info)
