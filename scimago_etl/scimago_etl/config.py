"""Configurações centrais do ETL do SCImago.

Tudo que é "decisão de projeto" fica aqui, para o grupo revisar em um lugar só.
"""

# As 27 subject areas do SCImago (nomes exatamente como aparecem na coluna "Areas").
AREAS_SCIMAGO = [
    "Agricultural and Biological Sciences",
    "Arts and Humanities",
    "Biochemistry, Genetics and Molecular Biology",
    "Business, Management and Accounting",
    "Chemical Engineering",
    "Chemistry",
    "Computer Science",
    "Decision Sciences",
    "Dentistry",
    "Earth and Planetary Sciences",
    "Economics, Econometrics and Finance",
    "Energy",
    "Engineering",
    "Environmental Science",
    "Health Professions",
    "Immunology and Microbiology",
    "Materials Science",
    "Mathematics",
    "Medicine",
    "Multidisciplinary",
    "Neuroscience",
    "Nursing",
    "Pharmacology, Toxicology and Pharmaceutics",
    "Physics and Astronomy",
    "Psychology",
    "Social Sciences",
    "Veterinary",
]

# Categorias cuja área "dona" não dá para inferir pelos dados (todos os seus periódicos
# também pertencem a outra área). Valores conforme a classificação ASJC usada pelo SCImago.
# Ver DECISOES.md, D5. Acrescente aqui se o relatório listar outra categoria sem área.
CATEGORIA_AREA_MANUAL = {
    "Respiratory Care": "Health Professions",
    "Medical Assisting and Transcription": "Health Professions",
}

# Anos esperados na pasta (4 anos x 27 áreas = 108 arquivos).
ANOS_PADRAO = (2022, 2023, 2024, 2025)

# Método de percentil (ver percentil.py). CONFIRMAR com a definição do grupo.
METODO_PERCENTIL_PADRAO = "topo_100"

# Regra de empate de SJR (ver DECISOES.md, decisão D2). "melhor" = benefício da dúvida ao docente.
EMPATES_PADRAO = "melhor"

# Uma categoria é marcada como "suspeita de incompleta" quando os quartis
# recalculados por nós concordam com os do SCImago em menos que este limiar.
# Nos testes, categorias completas ficaram entre ~0,90 e 1,00; incompletas, abaixo de ~0,80.
LIMIAR_CONCORDANCIA_QUARTIL = 0.85

# Renomeação das colunas originais para nomes em snake_case.
# A coluna "Total Docs. (AAAA)" muda de nome a cada ano; é tratada à parte.
COLUNAS = {
    "Rank": "rank_area",
    "Sourceid": "sourceid",
    "Title": "titulo",
    "Type": "tipo",
    "Issn": "issn_bruto",
    "Publisher": "publisher",
    "Open Access": "open_access",
    "Open Access Diamond": "open_access_diamond",
    "SJR": "sjr",
    "SJR Best Quartile": "quartil_melhor",
    "H index": "h_index",
    "Total Docs. (3years)": "total_docs_3anos",
    "Total Refs.": "total_refs",
    "Total Citations (3years)": "total_citacoes_3anos",
    "Citable Docs. (3years)": "docs_citaveis_3anos",
    "Citations / Doc. (2years)": "citacoes_por_doc_2anos",
    "Ref. / Doc.": "refs_por_doc",
    "%Female": "pct_feminino",
    "Overton": "overton",
    "Country": "pais",
    "Region": "regiao",
    "Coverage": "cobertura",
    "Categories": "categorias_bruto",
    "Areas": "areas_bruto",
}

COLUNAS_DECIMAIS = ["sjr", "citacoes_por_doc_2anos", "refs_por_doc", "pct_feminino"]
COLUNAS_INTEIRAS = [
    "rank_area", "sourceid", "h_index", "total_docs_ano", "total_docs_3anos",
    "total_refs", "total_citacoes_3anos", "docs_citaveis_3anos", "overton",
]
