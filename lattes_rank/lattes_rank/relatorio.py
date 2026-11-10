"""Saída em texto (terminal) e em dicionário (JSON) para um Resultado."""

from __future__ import annotations

from collections import defaultdict

from .ranking import (
    FORA_DA_JANELA,
    NAO_LOCALIZADO,
    PONTUADO,
    SEM_PERCENTIL,
    ArtigoAvaliado,
    LinhaRanking,
    Resultado,
)

MARCA_EMPATE_NOTA = "†"
MARCA_EMPATE_SJR = "*"


def _cortar(texto: str, largura: int) -> str:
    return texto if len(texto) <= largura else texto[: largura - 1] + "…"


def _numero(valor: float | None) -> str:
    """4.0 -> '4'; 4.5 -> '4.5'."""
    if valor is None:
        return "?"
    return str(int(valor)) if float(valor).is_integer() else f"{valor:g}"


def _nome_artigo(a: ArtigoAvaliado) -> str:
    return a.periodico_base or a.artigo.periodico_nome or "(sem nome)"


def _linha_lista(a: ArtigoAvaliado) -> str:
    ano = a.artigo.ano if a.artigo.ano is not None else "----"
    return f"  {ano}  {_cortar(_nome_artigo(a), 55)}  — {a.motivo}"


def formatar_texto(resultado: Resultado) -> str:
    cv = resultado.curriculo
    ini, fim = resultado.janela_nota
    c = resultado.contagens
    linhas: list[str] = []

    # -- cabeçalho ---------------------------------------------------------
    linhas.append(f"Docente: {cv.nome or '(nome não encontrado no HTML)'}")
    linhas.append(f"ID Lattes: {cv.id_lattes or '(não encontrado)'}")
    linhas.append(f"Currículo atualizado em: {cv.data_atualizacao or '(não encontrado)'}")
    linhas.append(f"Arquivo: {cv.arquivo}")
    linhas.append("")

    # -- regras ------------------------------------------------------------
    linhas.append("REGRAS APLICADAS")
    linhas.append(f"  - Artigos considerados: {resultado.politica.descricao}; posteriores a {fim} nunca entram.")
    linhas.append(
        f"  - Nota do periódico: maior percentil SJR entre {ini} e {fim}, na melhor categoria de cada ano,"
        " independente do ano do artigo (empate entre anos: o mais recente)."
    )
    linhas.append("  - Casamento por ISSN (impresso e online do mesmo periódico contam como um só).")
    linhas.append("  - Desempate: nº de artigos no periódico, ano de artigo mais recente, título.")
    linhas.append("")

    # -- contagens ---------------------------------------------------------
    linhas.append(
        f"Artigos lidos: {len(resultado.avaliados)} | elegíveis pela regra de anos: {resultado.n_elegiveis} "
        f"(pontuados: {c.get(PONTUADO, 0)}, não localizados: {c.get(NAO_LOCALIZADO, 0)}, "
        f"sem percentil: {c.get(SEM_PERCENTIL, 0)}) | fora da regra de anos: {c.get(FORA_DA_JANELA, 0)}"
    )
    linhas.append("")

    # -- top ---------------------------------------------------------------
    top = resultado.top
    linhas.append(f"PERIÓDICOS COM MAIOR PERCENTIL (top {len(top)})")
    if not top:
        linhas.append("  Nenhum periódico pontuado.")
    else:
        linhas.append(
            f"  {'#':>2}  {'Periódico':<46} {'Percentil':>9}    {'Ano':>4}  {'Artigos':>7}  Anos dos artigos"
        )
        for l in top:
            marca = (MARCA_EMPATE_NOTA if l.empatado_na_nota else "") + (MARCA_EMPATE_SJR if l.empate_sjr else "")
            anos = ", ".join(str(a) for a in l.anos_artigos)
            linhas.append(
                f"  {l.posicao:>2}  {_cortar(l.periodico, 46):<46} {l.percentil:>9.2f}{marca:<2}  "
                f"{l.ano_do_percentil:>4}  {l.n_artigos:>7}  {anos}"
            )
            detalhe = f"categoria {l.categoria}: posição {_numero(l.nota.posicao)} de {_numero(l.nota.n_categoria)}"
            if l.nota.quartil_scimago:
                detalhe += f", {l.nota.quartil_scimago} no SCImago"
            if l.empate_sjr:
                detalhe += f", {l.nota.n_empatados} periódicos com o mesmo SJR"
            linhas.append(f"      {detalhe}")
        if any(l.empatado_na_nota for l in top):
            linhas.append(
                f"  {MARCA_EMPATE_NOTA} mesma nota que um periódico vizinho no ranking (pode estar fora do top);"
                " a ordem saiu dos desempates."
            )
        if any(l.empate_sjr for l in top):
            linhas.append(
                f"  {MARCA_EMPATE_SJR} o percentil vem de um bloco de SJR empatado na categoria; empatados recebem"
                " a melhor posição do bloco (decisão D2 da etapa 1)."
            )
    restante = resultado.ranking[len(top):]
    if restante:
        linhas.append(f"  (+{len(restante)} periódico(s) pontuado(s) fora do top)")

    # -- listas auxiliares -------------------------------------------------
    nao_loc = resultado.por_status(NAO_LOCALIZADO)
    if nao_loc:
        linhas += ["", "NÃO LOCALIZADOS NA BASE (conferir manualmente)"]
        linhas += [_linha_lista(a) for a in nao_loc]

    sem_perc = resultado.por_status(SEM_PERCENTIL)
    if sem_perc:
        linhas += ["", f"SEM PERCENTIL EM {ini}-{fim}"]
        linhas += [_linha_lista(a) for a in sem_perc]

    fora = resultado.por_status(FORA_DA_JANELA)
    if fora:
        linhas += ["", "FORA DA REGRA DE ANOS"]
        por_ano: dict[int | None, list[ArtigoAvaliado]] = defaultdict(list)
        for a in fora:
            por_ano[a.artigo.ano].append(a)
        for ano in sorted(por_ano, key=lambda x: (x is None, -(x or 0))):
            itens = por_ano[ano]
            rotulo = "sem ano" if ano is None else str(ano)
            nomes = "; ".join(_cortar(a.artigo.periodico_nome or "(sem nome)", 45) for a in itens)
            linhas.append(f"  {rotulo} ({len(itens)}): {nomes}")

    if cv.avisos:
        linhas += ["", "AVISOS"]
        linhas += [f"  - {aviso}" for aviso in cv.avisos]
    return "\n".join(linhas)


def _linha_para_dict(l: LinhaRanking) -> dict:
    return {
        "posicao": l.posicao,
        "sourceid": l.sourceid,
        "periodico": l.periodico,
        "percentil": l.percentil,
        "ano_do_percentil": l.ano_do_percentil,
        "categoria": l.categoria,
        "posicao_na_categoria": l.nota.posicao,
        "n_categoria": l.nota.n_categoria,
        "quartil_scimago": l.nota.quartil_scimago,
        "n_artigos": l.n_artigos,
        "anos_artigos": list(l.anos_artigos),
        "ano_mais_recente": l.ano_mais_recente,
        "issns": list(l.issns),
        "empatado_na_nota": l.empatado_na_nota,
        "empate_sjr": l.empate_sjr,
        "n_empatados": l.nota.n_empatados,
    }


def para_dict(resultado: Resultado) -> dict:
    cv = resultado.curriculo
    return {
        "docente": {"nome": cv.nome, "id_lattes": cv.id_lattes, "data_atualizacao": cv.data_atualizacao, "arquivo": cv.arquivo},
        "regra_de_anos": {
            "descricao": resultado.politica.descricao,
            "ano_min": resultado.politica.ano_min,
            "ano_max": resultado.politica.ano_max,
        },
        "janela_da_nota": list(resultado.janela_nota),
        "contagens": {
            "lidos": len(resultado.avaliados),
            "elegiveis": resultado.n_elegiveis,
            **{s: resultado.contagens.get(s, 0) for s in (PONTUADO, FORA_DA_JANELA, NAO_LOCALIZADO, SEM_PERCENTIL)},
        },
        "top": [_linha_para_dict(l) for l in resultado.top],
        "ranking_completo": [_linha_para_dict(l) for l in resultado.ranking],
        "artigos": [
            {
                "sequencia": a.artigo.sequencia,
                "ano": a.artigo.ano,
                "titulo": a.artigo.titulo,
                "periodico_lattes": a.artigo.periodico_nome,
                "issn_bruto": a.artigo.issn_bruto,
                "issn": a.artigo.issn,
                "doi": a.artigo.doi,
                "status": a.status,
                "codigo_motivo": a.codigo_motivo,
                "motivo": a.motivo,
                "sourceid": a.sourceid,
                "periodico_base": a.periodico_base,
                "percentil": a.nota.percentil if a.nota else None,
                "ano_do_percentil": a.nota.ano if a.nota else None,
            }
            for a in resultado.avaliados
        ],
        "avisos": cv.avisos,
    }
