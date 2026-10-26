"""Validação dos dados: verificações em SQL sobre os Parquets por ano e invariantes das tabelas de saída.

Cada verificação devolve achados de nível "erro" (o pipeline não deve gravar as saídas) ou "aviso"
(vai para o relatório de qualidade, sem interromper).
"""

from dataclasses import dataclass

import duckdb

from config import (
    COMORBIDADE_DOMINIO,
    COMORBIDADES,
    EVOLUCAO_CURA,
    EVOLUCAO_DOMINIO,
    EVOLUCAO_OBITO,
    JANELA_DATA_DIAS,
    LIMITE_DATA_INVALIDA,
    LIMITE_SEM_DESFECHO,
    UFS_VALIDAS,
)

ERRO = "erro"
AVISO = "aviso"

# Contagens por ano calculadas sobre os Parquets (as chaves do relatório de qualidade).
CAMPOS_ESTATISTICA = [
    "linhas", "sem_uf", "uf_invalida", "sem_data", "data_fora_janela", "sem_desfecho",
    "evolucao_invalida", "comorbidade_invalida", "fora_da_serie_estado",
]


@dataclass(frozen=True)
class Achado:
    nivel: str
    codigo: str
    ano: int | None
    quantidade: int
    mensagem: str


def _lista_sql(valores) -> str:
    return ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in valores)


def estatisticas_por_ano(con: duckdb.DuckDBPyConnection) -> dict[int, dict[str, int]]:
    """Contagens de problemas em cada ano da view `casos` (ano sem nenhum caso sai com zeros)."""
    comorbidade_invalida = " OR ".join(
        f"({c} IS NOT NULL AND {c} NOT IN ({_lista_sql(COMORBIDADE_DOMINIO)}))" for c in COMORBIDADES
    )
    # Data fora do ano civil por mais de JANELA_DATA_DIAS dias (para cada lado).
    fora_janela = (f"DT_SIN_PRI IS NOT NULL AND (DT_SIN_PRI < make_date(ano::INTEGER, 1, 1) - {JANELA_DATA_DIAS} "
                   f"OR DT_SIN_PRI > make_date(ano::INTEGER, 12, 31) + {JANELA_DATA_DIAS})")
    linhas = con.execute(f"""
        SELECT ano,
            count(*) AS linhas,
            count(*) FILTER (WHERE SG_UF IS NULL) AS sem_uf,
            count(*) FILTER (WHERE SG_UF IS NOT NULL AND SG_UF NOT IN ({_lista_sql(UFS_VALIDAS)})) AS uf_invalida,
            count(*) FILTER (WHERE DT_SIN_PRI IS NULL) AS sem_data,
            count(*) FILTER (WHERE {fora_janela}) AS data_fora_janela,
            count(*) FILTER (WHERE EVOLUCAO IS NULL OR EVOLUCAO NOT IN ({EVOLUCAO_CURA}, {EVOLUCAO_OBITO}))
                AS sem_desfecho,
            count(*) FILTER (WHERE EVOLUCAO IS NOT NULL AND EVOLUCAO NOT IN ({_lista_sql(EVOLUCAO_DOMINIO)}))
                AS evolucao_invalida,
            count(*) FILTER (WHERE {comorbidade_invalida}) AS comorbidade_invalida,
            count(*) FILTER (WHERE SG_UF IS NULL OR DT_SIN_PRI IS NULL) AS fora_da_serie_estado
        FROM casos GROUP BY ano
    """).fetchall()
    por_ano = {ano: dict(zip(CAMPOS_ESTATISTICA, valores, strict=True)) for ano, *valores in linhas}
    for (ano,) in con.execute("SELECT ano FROM anos").fetchall():
        por_ano.setdefault(ano, dict.fromkeys(CAMPOS_ESTATISTICA, 0))
    return dict(sorted(por_ano.items()))


def validar_casos(estatisticas: dict[int, dict[str, int]]) -> list[Achado]:
    """Achados sobre os casos de cada ano, a partir de `estatisticas_por_ano`."""
    achados = []
    for ano, e in estatisticas.items():
        linhas = e["linhas"]
        if linhas == 0:
            achados.append(Achado(AVISO, "ANO_SEM_CASOS", ano, 0, f"{ano}: nenhum caso de COVID no arquivo do ano."))
            continue
        if e["evolucao_invalida"]:
            achados.append(Achado(ERRO, "EVOLUCAO_FORA_DO_DOMINIO", ano, e["evolucao_invalida"],
                                  f"{ano}: {e['evolucao_invalida']} casos com EVOLUCAO fora de {EVOLUCAO_DOMINIO}."))
        if e["comorbidade_invalida"]:
            achados.append(Achado(ERRO, "COMORBIDADE_FORA_DO_DOMINIO", ano, e["comorbidade_invalida"],
                                  f"{ano}: {e['comorbidade_invalida']} casos com comorbidade fora de "
                                  f"{COMORBIDADE_DOMINIO}."))
        datas_ruins = e["sem_data"] + e["data_fora_janela"]
        if datas_ruins:
            nivel = ERRO if datas_ruins / linhas > LIMITE_DATA_INVALIDA else AVISO
            achados.append(Achado(nivel, "DATA_INVALIDA", ano, datas_ruins,
                                  f"{ano}: {datas_ruins} de {linhas} casos com data de início dos sintomas ausente "
                                  f"({e['sem_data']}) ou fora do ano ± {JANELA_DATA_DIAS} dias ({e['data_fora_janela']})."))
        if e["sem_uf"]:
            achados.append(Achado(AVISO, "SEM_UF", ano, e["sem_uf"],
                                  f"{ano}: {e['sem_uf']} casos sem UF; ficam fora das tabelas por estado."))
        if e["uf_invalida"]:
            achados.append(Achado(AVISO, "UF_INVALIDA", ano, e["uf_invalida"],
                                  f"{ano}: {e['uf_invalida']} casos com UF que não é uma das 27 siglas."))
        if e["sem_desfecho"] / linhas > LIMITE_SEM_DESFECHO:
            achados.append(Achado(AVISO, "SEM_DESFECHO_ACIMA_DO_LIMITE", ano, e["sem_desfecho"],
                                  f"{ano}: {e['sem_desfecho']} de {linhas} casos "
                                  f"({e['sem_desfecho'] / linhas:.1%}) sem desfecho conhecido, acima de "
                                  f"{LIMITE_SEM_DESFECHO:.0%}. Em um ano parcial e recente, muitos casos ainda estão "
                                  "em andamento; nesse caso o aviso pode ser esperado."))
    return achados
