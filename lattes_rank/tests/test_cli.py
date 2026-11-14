import json
import sqlite3
from pathlib import Path

import pytest

from lattes_rank.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "artigos_completos.html"


def test_cli_imprime_o_top_e_grava_json(caminho_banco, tmp_path, capsys):
    saida = tmp_path / "saida.json"
    codigo = main([str(FIXTURE), "--db", str(caminho_banco), "--json", str(saida)])
    texto = capsys.readouterr().out
    assert codigo == 0
    assert "Journal of Business and Economic Statistics" in texto
    assert "Artigos considerados: artigos de 2022 a 2025" in texto
    assert "†" in texto and "97.00*" in texto
    dados = json.loads(saida.read_text(encoding="utf-8"))
    assert [l["posicao"] for l in dados["top"]] == [1, 2, 3, 4]
    assert dados["contagens"]["pontuado"] == 6


def test_cli_top_menor(caminho_banco, capsys):
    assert main([str(FIXTURE), "--db", str(caminho_banco), "--top", "2"]) == 0
    texto = capsys.readouterr().out
    assert "(top 2)" in texto and "(+2 periódico(s) pontuado(s) fora do top)" in texto


def test_cli_top_invalido(caminho_banco):
    with pytest.raises(SystemExit) as saida:
        main([str(FIXTURE), "--db", str(caminho_banco), "--top", "0"])
    assert saida.value.code == 2


def test_cli_janela_vem_do_banco(caminho_banco, capsys):
    con = sqlite3.connect(caminho_banco)
    con.execute("UPDATE periodico_categoria_ano SET percentil = NULL WHERE ano = 2025")
    con.commit()
    con.close()
    main([str(FIXTURE), "--db", str(caminho_banco)])
    assert "Artigos considerados: artigos de 2022 a 2024" in capsys.readouterr().out


def test_cli_pasta_com_varios_curriculos(caminho_banco, tmp_path, capsys):
    pasta = tmp_path / "cvs"
    pasta.mkdir()
    (pasta / "a.html").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (pasta / "b.HTM").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (pasta / "ignorar.txt").write_text("x", encoding="utf-8")
    saida = tmp_path / "varios.json"
    assert main([str(pasta), "--db", str(caminho_banco), "--json", str(saida)]) == 0
    assert capsys.readouterr().out.count("Docente:") == 2
    dados = json.loads(saida.read_text(encoding="utf-8"))
    assert isinstance(dados, list) and len(dados) == 2


@pytest.mark.parametrize(
    "caso",
    ["entrada_inexistente", "banco_inexistente", "pasta_vazia", "banco_esquema_errado", "arquivo_nao_sqlite"],
)
def test_cli_erros_sao_mensagens_e_nao_tracebacks(caso, caminho_banco, tmp_path, capsys):
    entrada, banco = FIXTURE, caminho_banco
    if caso == "entrada_inexistente":
        entrada = tmp_path / "nao_existe.html"
    elif caso == "banco_inexistente":
        banco = tmp_path / "nao_existe.sqlite"
    elif caso == "pasta_vazia":
        entrada = tmp_path / "vazia"
        entrada.mkdir()
    elif caso == "banco_esquema_errado":
        banco = tmp_path / "errado.sqlite"
        sqlite3.connect(banco).execute("CREATE TABLE x (a)").connection.close()
    elif caso == "arquivo_nao_sqlite":
        banco = tmp_path / "texto.sqlite"
        banco.write_text("não sou um banco", encoding="utf-8")
    assert main([str(entrada), "--db", str(banco)]) == 2
    capturado = capsys.readouterr()
    assert capturado.err.startswith("Erro: ") and "Traceback" not in capturado.err
    assert capturado.out == ""


def test_cli_le_xml_com_o_mesmo_top_do_html(caminho_banco, tmp_path):
    def top(entrada):
        saida = tmp_path / f"{entrada.suffix}.json"
        assert main([str(entrada), "--db", str(caminho_banco), "--json", str(saida)]) == 0
        return [l["periodico"] for l in json.loads(saida.read_text(encoding="utf-8"))["top"]]

    assert top(FIXTURE.with_suffix(".xml")) == top(FIXTURE)


def test_cli_xml_invalido_sai_com_codigo_2(caminho_banco, tmp_path, capsys):
    ruim = tmp_path / "ruim.xml"
    ruim.write_bytes(b'<?xml version="1.0"?><outra-coisa/>')
    assert main([str(ruim), "--db", str(caminho_banco)]) == 2
    assert "não é um currículo Lattes" in capsys.readouterr().err
