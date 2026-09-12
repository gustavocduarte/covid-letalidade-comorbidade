"""Tratamento (T do ETL): filtra casos de COVID e prepara colunas para análise de letalidade."""

from pathlib import Path

import pandas as pd

# As 11 colunas de comorbidade do SIVEP-Gripe (confirmadas no dicionário de dados oficial).
# TABAG (Tabagismo) existe no formulário oficial, mas não entra aqui: checamos e o campo
# vem 100% vazio em todos os 7 anos (2020-2026) — o Ministério da Saúde não o preenche
# na prática, então não haveria dado real pra comparar.
COMORBIDADES = [
    "CARDIOPATI", "HEMATOLOGI", "SIND_DOWN", "HEPATICA", "ASMA",
    "DIABETES", "NEUROLOGIC", "PNEUMOPATI", "IMUNODEPRE", "RENAL", "OBESIDADE",
]

# Só carregamos do CSV gigante as colunas que realmente vamos usar.
# DT_SIN_PRI (data de início dos sintomas) alimenta o gráfico de linha do tempo;
# SG_UF (UF de residência do paciente) alimenta o mapa por estado.
COLUNAS_NECESSARIAS = ["CLASSI_FIN", "EVOLUCAO", "DT_SIN_PRI", "SG_UF"] + COMORBIDADES

# Nome por extenso de cada comorbidade, conforme o dicionário de dados oficial
# (docs/dicionario-de-dados-2019-a-2025.pdf), para uso em exibição/relatórios.
NOMES_COMORBIDADES = {
    "CARDIOPATI": "Doença Cardiovascular Crônica",
    "HEMATOLOGI": "Doença Hematológica Crônica",
    "SIND_DOWN": "Síndrome de Down",
    "HEPATICA": "Doença Hepática Crônica",
    "ASMA": "Asma",
    "DIABETES": "Diabetes Mellitus",
    "NEUROLOGIC": "Doença Neurológica Crônica",
    "PNEUMOPATI": "Outra Pneumopatia Crônica",
    "IMUNODEPRE": "Imunodeficiência ou Imunodepressão",
    "RENAL": "Doença Renal Crônica",
    "OBESIDADE": "Obesidade",
}


def carregar_casos_covid(caminho_csv: Path) -> pd.DataFrame:
    """Lê o CSV bruto de um ano usando só as colunas necessárias e filtra os casos de COVID (CLASSI_FIN == 5)."""
    df = pd.read_csv(caminho_csv, sep=";", encoding="latin1", usecols=COLUNAS_NECESSARIAS)
    covid = df[df["CLASSI_FIN"] == 5].copy()
    return covid


def contar_desfechos(df: pd.DataFrame) -> tuple[int, int]:
    """Conta óbitos e curas (os dois únicos desfechos "conhecidos") num grupo de casos."""
    obitos = int((df["EVOLUCAO"] == 2).sum())
    curas = int((df["EVOLUCAO"] == 1).sum())
    return obitos, curas


def letalidade_por_comorbidade(covid: pd.DataFrame) -> pd.DataFrame:
    """Para cada comorbidade, compara a taxa de letalidade entre quem tem (1) e quem não tem (2).

    Além da taxa já calculada, guarda também os óbitos e o total de casos com desfecho
    conhecido (óbitos + curas) separadamente — são o numerador e o denominador reais da
    taxa. Isso é o que permite, mais tarde, somar vários anos numa taxa agregada exata
    (soma de óbitos ÷ soma de desfechos conhecidos), em vez de fazer média das taxas.
    """
    linhas = []
    for comorbidade in COMORBIDADES:
        com = covid[covid[comorbidade] == 1]
        sem = covid[covid[comorbidade] == 2]

        obitos_com, curas_com = contar_desfechos(com)
        obitos_sem, curas_sem = contar_desfechos(sem)
        desfecho_com = obitos_com + curas_com
        desfecho_sem = obitos_sem + curas_sem

        # Se não houver nenhum caso com desfecho conhecido (0 óbitos + 0 curas), a taxa
        # fica indefinida (NaN) em vez de travar o programa com divisão por zero — é o
        # que aconteceu de verdade com TABAG, campo que existe no formulário mas nunca
        # é preenchido, deixando 0/0 pra calcular.
        taxa_com = obitos_com / desfecho_com if desfecho_com else float("nan")
        taxa_sem = obitos_sem / desfecho_sem if desfecho_sem else float("nan")

        linhas.append({
            "comorbidade": comorbidade,
            "casos_com": len(com),
            "obitos_com": obitos_com,
            "desfecho_conhecido_com": desfecho_com,
            "taxa_letalidade_com": taxa_com,
            "casos_sem": len(sem),
            "obitos_sem": obitos_sem,
            "desfecho_conhecido_sem": desfecho_sem,
            "taxa_letalidade_sem": taxa_sem,
        })
    resultado = pd.DataFrame(linhas).sort_values("taxa_letalidade_com", ascending=False)
    return resultado.reset_index(drop=True)


def serie_semanal_casos_covid(covid: pd.DataFrame) -> pd.DataFrame:
    """Conta casos de COVID por semana civil, a partir da data de início dos sintomas.

    Usa a data real (DT_SIN_PRI) em vez do número de semana epidemiológica do arquivo,
    pra evitar ambiguidade em casos na virada do ano (ex: sintomas no fim de dezembro,
    mas notificados só em janeiro, indo parar no arquivo do ano seguinte).
    """
    datas = pd.to_datetime(covid["DT_SIN_PRI"], errors="coerce")
    ignoradas = datas.isna().sum()
    semana = datas.dropna().dt.to_period("W").dt.start_time
    serie = semana.value_counts().sort_index().rename_axis("semana").reset_index(name="casos")
    if ignoradas:
        print(f"  (aviso: {ignoradas} casos com DT_SIN_PRI inválida/ausente, excluídos da série semanal)")
    return serie


def serie_semanal_por_comorbidade(covid: pd.DataFrame) -> pd.DataFrame:
    """Conta casos de COVID por semana, separado por comorbidade (só quem tem = 1).

    Formato "longo": uma linha por combinação de semana + comorbidade, com a
    coluna "casos". Cada comorbidade é contada de forma independente — um caso
    com duas comorbidades entra na contagem semanal de cada uma delas.
    """
    datas = pd.to_datetime(covid["DT_SIN_PRI"], errors="coerce")
    semana = datas.dt.to_period("W").dt.start_time

    blocos = []
    for comorbidade in COMORBIDADES:
        tem_comorbidade = (covid[comorbidade] == 1) & semana.notna()
        contagem = semana[tem_comorbidade].value_counts().sort_index()
        bloco = contagem.rename_axis("semana").reset_index(name="casos")
        bloco["comorbidade"] = comorbidade
        blocos.append(bloco)
    return pd.concat(blocos, ignore_index=True)


def serie_semanal_por_estado(covid: pd.DataFrame) -> pd.DataFrame:
    """Conta casos de COVID por semana, separado por estado (SG_UF — UF de residência).

    Formato "longo": uma linha por combinação de semana + sigla, com a coluna "casos".
    """
    datas = pd.to_datetime(covid["DT_SIN_PRI"], errors="coerce")
    semana = datas.dt.to_period("W").dt.start_time
    valido = semana.notna() & covid["SG_UF"].notna()

    tabela = pd.DataFrame({"semana": semana[valido], "sigla": covid.loc[valido, "SG_UF"]})
    return tabela.groupby(["semana", "sigla"], as_index=False).size().rename(columns={"size": "casos"})


def letalidade_por_estado(covid: pd.DataFrame) -> pd.DataFrame:
    """Calcula casos, óbitos e taxa de letalidade de COVID (geral, sem separar por
    comorbidade) para cada estado (SG_UF — UF de residência do paciente).
    """
    linhas = []
    for sigla, grupo in covid.groupby("SG_UF"):
        obitos, curas = contar_desfechos(grupo)
        desfecho = obitos + curas
        taxa = obitos / desfecho if desfecho else float("nan")
        linhas.append({
            "sigla": sigla,
            "casos": len(grupo),
            "obitos": obitos,
            "desfecho_conhecido": desfecho,
            "taxa_letalidade": taxa,
        })
    return pd.DataFrame(linhas).sort_values("sigla").reset_index(drop=True)


def agregar_estados_todos_anos(tabelas: list[pd.DataFrame]) -> pd.DataFrame:
    """Combina as tabelas de vários anos numa taxa de letalidade agregada por estado,
    somando óbitos e desfechos conhecidos antes de dividir (mesmo raciocínio de
    `agregar_todos_anos`, mas por estado em vez de por comorbidade).
    """
    todos = pd.concat(tabelas, ignore_index=True)
    agregado = todos.groupby("sigla", as_index=False).agg(
        casos=("casos", "sum"),
        obitos=("obitos", "sum"),
        desfecho_conhecido=("desfecho_conhecido", "sum"),
    )
    agregado["taxa_letalidade"] = agregado["obitos"] / agregado["desfecho_conhecido"]
    return agregado.sort_values("taxa_letalidade", ascending=False).reset_index(drop=True)


def agregar_todos_anos(tabelas: list[pd.DataFrame]) -> pd.DataFrame:
    """Combina as tabelas de vários anos numa taxa de letalidade agregada por comorbidade.

    Soma óbitos e desfechos conhecidos de todos os anos e só então divide — o jeito
    matematicamente correto de agregar taxas, diferente de tirar a média das taxas
    anuais (que trataria um ano com 100 casos igual a um ano com 1 milhão de casos).
    """
    todos = pd.concat(tabelas, ignore_index=True)
    agregado = todos.groupby("comorbidade", as_index=False).agg(
        casos_com=("casos_com", "sum"),
        obitos_com=("obitos_com", "sum"),
        desfecho_conhecido_com=("desfecho_conhecido_com", "sum"),
        casos_sem=("casos_sem", "sum"),
        obitos_sem=("obitos_sem", "sum"),
        desfecho_conhecido_sem=("desfecho_conhecido_sem", "sum"),
    )
    agregado["taxa_letalidade_com"] = agregado["obitos_com"] / agregado["desfecho_conhecido_com"]
    agregado["taxa_letalidade_sem"] = agregado["obitos_sem"] / agregado["desfecho_conhecido_sem"]
    return agregado.sort_values("taxa_letalidade_com", ascending=False).reset_index(drop=True)
