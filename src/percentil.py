"""Percentil de uma revista em uma área/ano.

Contrato: percentil(posicao, total) -> float em (0, 1], melhor revista = 1.0.
ATENÇÃO: direção da contagem pendente de confirmação (pergunta 1 ao professor).
"""


def percentil(posicao: int, total: int) -> float:
    """Usa a posição do Scimago (1 = melhor): p = (total - posicao + 1) / total."""
    if not 1 <= posicao <= total:
        raise ValueError("posição fora do intervalo")
    return (total - posicao + 1) / total
