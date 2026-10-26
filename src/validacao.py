"""Validação dos dados: verificações em SQL sobre os Parquets por ano e invariantes das tabelas de saída.

Cada verificação devolve achados de nível "erro" (o pipeline não deve gravar as saídas) ou "aviso"
(vai para o relatório de qualidade, sem interromper).
"""

from dataclasses import asdict, dataclass

import duckdb
import pandas as pd

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


def _contagens_inconsistentes(df: pd.DataFrame, sufixos: list[str]) -> int:
    """Linhas em que óbitos > desfechos conhecidos ou desfechos conhecidos > casos."""
    ruins = pd.Series(False, index=df.index)
    for s in sufixos:
        casos, obitos, desfecho = df[f"casos{s}"], df[f"obitos{s}"], df[f"desfecho_conhecido{s}"]
        ruins |= (obitos > desfecho) | (desfecho > casos)
    return int(ruins.sum())


def validar_saidas(
    estatisticas: dict[int, dict[str, int]],
    *,
    por_ano: pd.DataFrame,
    agregado: pd.DataFrame,
    estado: pd.DataFrame,
    serie_semanal: pd.DataFrame,
    serie_comorbidade: pd.DataFrame,
    serie_estado: pd.DataFrame,
) -> list[Achado]:
    """Invariantes entre as tabelas de saída e as contagens dos Parquets; qualquer violação é erro."""
    achados = []

    def erro(codigo: str, quantidade: int, mensagem: str, ano: int | None = None) -> None:
        achados.append(Achado(ERRO, codigo, ano, quantidade, mensagem))

    total = {campo: sum(e[campo] for e in estatisticas.values()) for campo in CAMPOS_ESTATISTICA}

    for ano, e in estatisticas.items():
        linhas_ano = por_ano[por_ano["ano"] == ano]
        if sorted(linhas_ano["comorbidade"]) != sorted(COMORBIDADES):
            erro("COMORBIDADES_INCOMPLETAS", len(linhas_ano),
                 f"{ano}: a tabela por comorbidade deveria ter as {len(COMORBIDADES)} comorbidades uma vez cada.", ano)
        excesso = int(((linhas_ano["casos_com"] + linhas_ano["casos_sem"]) > e["linhas"]).sum())
        if excesso:
            erro("CASOS_MAIORES_QUE_LINHAS", excesso,
                 f"{ano}: casos com + sem comorbidade passam do total de casos.", ano)

    tabelas = (("por ano", por_ano, ["_com", "_sem"]), ("agregada", agregado, ["_com", "_sem"]),
               ("por estado", estado, [""]))
    for nome, df, sufixos in tabelas:
        ruins = _contagens_inconsistentes(df, sufixos)
        if ruins:
            erro("CONTAGENS_INCONSISTENTES", ruins, f"Tabela {nome}: {ruins} linhas com óbitos > desfechos > casos.")
        taxas = df[[c for c in df.columns if c.startswith("taxa_letalidade")]]
        fora = int(((taxas < 0) | (taxas > 1)).sum().sum())
        if fora:
            erro("TAXA_FORA_DO_INTERVALO", fora, f"Tabela {nome}: {fora} taxas fora de [0, 1].")

    contagens = [f"{n}{s}" for s in ("_com", "_sem") for n in ("casos", "obitos", "desfecho_conhecido")]
    soma = por_ano.groupby("comorbidade")[contagens].sum()
    comparado = agregado.set_index("comorbidade")[contagens].reindex(soma.index)
    divergentes = int((comparado != soma).any(axis=1).sum())
    if divergentes:
        erro("AGREGADO_DIFERE_DA_SOMA", divergentes,
             f"{divergentes} comorbidades com o agregado diferente da soma dos anos.")

    somas = {
        "ESTADO_DIFERE_DOS_CASOS": (
            "casos por estado", int(estado["casos"].sum()), total["linhas"] - total["sem_uf"]),
        "SERIE_SEMANAL_DIFERE_DOS_CASOS": (
            "série semanal", int(serie_semanal["casos"].sum()), total["linhas"] - total["sem_data"]),
        "SERIE_ESTADO_DIFERE_DOS_CASOS": (
            "série semanal por estado", int(serie_estado["casos"].sum()),
            total["linhas"] - total["fora_da_serie_estado"]),
    }
    for codigo, (nome, obtido, esperado) in somas.items():
        if obtido != esperado:
            erro(codigo, abs(obtido - esperado), f"Soma de {nome} = {obtido}, mas os Parquets indicam {esperado}.")

    por_comorbidade = serie_comorbidade.groupby("comorbidade")["casos"].sum()
    maximo = agregado.set_index("comorbidade")["casos_com"].reindex(por_comorbidade.index)
    excesso = int((por_comorbidade > maximo).sum())
    if excesso:
        erro("SERIE_COMORBIDADE_MAIOR_QUE_CASOS", excesso,
             f"{excesso} comorbidades com mais casos na série que na tabela.")
    return achados


def montar_relatorio(estatisticas: dict[int, dict[str, int]], achados: list[Achado]) -> dict:
    """Relatório de qualidade sem data nem hora, para a saída ser a mesma em toda execução com os mesmos dados."""
    ordenados = sorted(achados, key=lambda a: (a.nivel != ERRO, a.codigo, a.ano or 0))
    return {
        "versao": 1,
        "aprovado": not any(a.nivel == ERRO for a in achados),
        "anos": {str(ano): dict(e) for ano, e in estatisticas.items()},
        "totais": {campo: sum(e[campo] for e in estatisticas.values()) for campo in CAMPOS_ESTATISTICA},
        "achados": [asdict(a) for a in ordenados],
    }
