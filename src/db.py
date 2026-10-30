"""Conexão SQLite e criação das tabelas."""
import sqlite3
from pathlib import Path

DB_PATH = Path("data/me315.db")
SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


def conectar(caminho: Path = DB_PATH) -> sqlite3.Connection:
    """Abre o banco e garante que as tabelas existem."""
    con = sqlite3.connect(caminho)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    return con
