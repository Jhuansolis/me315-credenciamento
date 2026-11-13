"""Executa o app.py real com st.file_uploader trocado por um arquivo local (só para os testes).

O caminho do arquivo vem da variável de ambiente ME315_HTML_FALSO.
"""

import os
import runpy
from pathlib import Path

import streamlit as st


class _ArquivoFalso:
    def __init__(self, caminho: str):
        self._dados = Path(caminho).read_bytes()
        self.name = Path(caminho).name
        self.size = len(self._dados)

    def getvalue(self) -> bytes:
        return self._dados


_arquivo = _ArquivoFalso(os.environ["ME315_HTML_FALSO"])
st.file_uploader = lambda *a, **k: _arquivo
runpy.run_path(str(Path(__file__).resolve().parent.parent / "app.py"), run_name="__main__")
