"""Ranking dos periódicos de um docente a partir do HTML do Currículo Lattes.

Fluxo: parser (HTML -> artigos) -> banco (ISSN -> periódico -> percentil SJR)
-> ranking (política de anos, desempates) -> relatório.
"""

__all__ = ["issn", "parser", "banco", "ranking", "relatorio"]
