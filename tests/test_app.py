from streamlit.testing.v1 import AppTest


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
