"""Linha de comando: python -m lattes_rank ENTRADA --db BANCO.sqlite [--top 4] [--json saida.json]"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .banco import Banco
from .parser import ler_curriculo
from .ranking import avaliar_curriculo, politica_padrao
from .relatorio import formatar_texto, para_dict

EXTENSOES = {".html", ".htm"}


def _listar_entradas(entrada: Path) -> list[Path]:
    if entrada.is_dir():
        arquivos = sorted(p for p in entrada.iterdir() if p.is_file() and p.suffix.lower() in EXTENSOES)
        if not arquivos:
            raise FileNotFoundError(f"Nenhum arquivo .html/.htm encontrado em {entrada}")
        return arquivos
    if entrada.is_file():
        return [entrada]
    raise FileNotFoundError(f"Entrada não encontrada: {entrada}")


def _forcar_utf8() -> None:
    # No Windows o terminal pode não ser UTF-8; acentos e "†" quebrariam o print.
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lattes_rank",
        description="Lista os periódicos de maior percentil SJR de um docente a partir do HTML público do Lattes.",
    )
    parser.add_argument("entrada", type=Path, help="arquivo .html do currículo (ou pasta com vários .html/.htm)")
    parser.add_argument("--db", type=Path, required=True, help="banco SQLite da etapa 1 (aberto só para leitura)")
    parser.add_argument("--top", type=int, default=4, help="quantos periódicos listar (padrão: 4)")
    parser.add_argument("--json", type=Path, dest="saida_json", help="grava também o resultado completo em JSON")
    args = parser.parse_args(argv)

    if args.top < 1:
        parser.error("--top deve ser pelo menos 1")

    _forcar_utf8()

    try:
        entradas = _listar_entradas(args.entrada)
        with Banco(args.db) as banco:
            janela = banco.anos_com_percentil()  # a janela da nota vem do banco, não do código
            politica = politica_padrao(*janela)
            resultados = [
                avaliar_curriculo(ler_curriculo(p), banco, politica, janela, top_n=args.top) for p in entradas
            ]
        texto = ("\n" + "=" * 100 + "\n").join(formatar_texto(r) for r in resultados)
        if args.saida_json:
            dados = [para_dict(r) for r in resultados]
            args.saida_json.write_text(
                json.dumps(dados if len(dados) > 1 else dados[0], ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except (OSError, ValueError, sqlite3.Error) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2

    print(texto)
    if args.saida_json:
        print(f"\nJSON gravado em {args.saida_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
