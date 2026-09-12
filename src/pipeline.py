"""Orquestra o pipeline completo (E-T-L) para vários anos do SIVEP-Gripe.

Processa um ano de cada vez: baixa o CSV bruto (pula o download se ele já
estiver em data/raw/) e calcula a letalidade por comorbidade. Os CSVs brutos
ficam salvos permanentemente — não são mais apagados no final.
"""

from datetime import date

import pandas as pd

from extract import PASTA_RAW, URLS_SRAG, baixar_arquivo
from load import anexar_csv, salvar_csv
from transform import (
    agregar_estados_todos_anos,
    agregar_todos_anos,
    carregar_casos_covid,
    letalidade_por_comorbidade,
    letalidade_por_estado,
    serie_semanal_casos_covid,
    serie_semanal_por_comorbidade,
)

NOME_CACHE_DETALHADO = "casos_covid_detalhado.csv"

# O ano corrente ainda está em andamento (banco "vivo", atualizado toda semana),
# então seus dados são parciais e não devem ser comparados como se fosse um ano cheio.
ANO_ATUAL = date.today().year


def processar_ano(ano: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Baixa (se ainda não tiver) e processa o CSV bruto de um único ano. O CSV bruto
    fica salvo em data/raw/ — não é mais apagado no final.

    Retorna (tabela de letalidade por comorbidade, série semanal geral,
    série semanal por comorbidade, tabela de letalidade por estado). Também
    acrescenta os casos desse ano (só as colunas que usamos, não as 194
    originais) a um cache permanente em data/processed/, pra futuros
    recortes não precisarem baixar tudo de novo.
    """
    url = URLS_SRAG[ano]
    nome_arquivo = url.split("/")[-1]
    caminho_csv = PASTA_RAW / nome_arquivo

    if caminho_csv.exists():
        print(f"[{ano}] CSV já está em disco, pulando download.")
    else:
        print(f"[{ano}] Baixando...")
        caminho_csv = baixar_arquivo(url, PASTA_RAW)

    print(f"[{ano}] Filtrando casos de COVID e calculando letalidade por comorbidade...")
    covid = carregar_casos_covid(caminho_csv)
    tabela = letalidade_por_comorbidade(covid)
    tabela["ano"] = ano
    tabela["ano_completo"] = ano != ANO_ATUAL

    print(f"[{ano}] Calculando séries semanais (geral e por comorbidade)...")
    semanal = serie_semanal_casos_covid(covid)
    semanal_comorbidade = serie_semanal_por_comorbidade(covid)

    print(f"[{ano}] Calculando letalidade por estado...")
    tabela_estado = letalidade_por_estado(covid)

    print(f"[{ano}] Gravando no cache de casos detalhados...")
    covid_cache = covid.drop(columns=["CLASSI_FIN"]).copy()  # CLASSI_FIN já é sempre 5 aqui
    covid_cache["ano"] = ano
    anexar_csv(covid_cache, NOME_CACHE_DETALHADO, primeiro_bloco=(ano == min(URLS_SRAG)))

    tamanho_gb = caminho_csv.stat().st_size / 1e9
    print(f"[{ano}] OK — {len(covid):,} casos de COVID. CSV bruto ({tamanho_gb:.2f} GB) mantido em {caminho_csv}.")

    return tabela, semanal, semanal_comorbidade, tabela_estado


if __name__ == "__main__":
    resultados = [processar_ano(ano) for ano in sorted(URLS_SRAG)]
    tabelas = [tabela for tabela, _, _, _ in resultados]
    series_semanais = [semanal for _, semanal, _, _ in resultados]
    series_semanais_comorbidade = [semanal_com for _, _, semanal_com, _ in resultados]
    tabelas_estado = [tabela_estado for _, _, _, tabela_estado in resultados]

    consolidado = pd.concat(tabelas, ignore_index=True)
    colunas_ordem = ["ano", "ano_completo", "comorbidade", "casos_com", "obitos_com",
                      "desfecho_conhecido_com", "taxa_letalidade_com", "casos_sem",
                      "obitos_sem", "desfecho_conhecido_sem", "taxa_letalidade_sem"]
    consolidado = consolidado[colunas_ordem]

    caminho = salvar_csv(consolidado, "letalidade_por_comorbidade_todos_anos.csv")
    print(f"\nConsolidado de {len(URLS_SRAG)} anos salvo em: {caminho}")
    print(f"Total de linhas: {len(consolidado)} (deveria ser {len(URLS_SRAG)} anos x 11 comorbidades = {len(URLS_SRAG) * 11})")

    # Agregado: soma óbitos e desfechos conhecidos de todos os anos (2020-2026, incluindo
    # o ano corrente parcial) numa única taxa por comorbidade. É o que o dashboard usa hoje,
    # antes de existir o filtro de ano.
    agregado = agregar_todos_anos(tabelas)
    caminho_agregado = salvar_csv(agregado, "letalidade_por_comorbidade_agregado.csv")
    print(f"Agregado (todos os anos somados) salvo em: {caminho_agregado}")

    # Semanas na virada do ano podem ter casos espalhados entre dois arquivos anuais
    # (ex: sintomas em 30/dez/2020, mas notificado só em jan/2021 -> vai pro arquivo de
    # 2021). Por isso agrupamos de novo por semana depois de juntar tudo, somando os
    # dois pedaços da mesma semana em vez de deixá-los como linhas duplicadas.
    serie_semanal = (
        pd.concat(series_semanais, ignore_index=True)
        .groupby("semana", as_index=False)["casos"]
        .sum()
        .sort_values("semana")
        .reset_index(drop=True)
    )
    caminho_semanal = salvar_csv(serie_semanal, "casos_covid_por_semana.csv")
    print(f"Série semanal ({len(serie_semanal)} semanas) salva em: {caminho_semanal}")

    # Mesmo raciocínio de juntar semanas na virada do ano, mas agora agrupando também
    # por comorbidade (cada combinação semana+comorbidade pode ter pedaços em dois anos).
    serie_semanal_comorbidade = (
        pd.concat(series_semanais_comorbidade, ignore_index=True)
        .groupby(["semana", "comorbidade"], as_index=False)["casos"]
        .sum()
        .sort_values(["comorbidade", "semana"])
        .reset_index(drop=True)
    )
    caminho_semanal_comorbidade = salvar_csv(serie_semanal_comorbidade, "casos_covid_semanal_por_comorbidade.csv")
    print(f"Série semanal por comorbidade ({len(serie_semanal_comorbidade)} linhas) salva em: {caminho_semanal_comorbidade}")

    print(f"\nCache de casos detalhados (uso futuro, sem precisar rebaixar) em: "
          f"data/processed/{NOME_CACHE_DETALHADO}")

    agregado_estado = agregar_estados_todos_anos(tabelas_estado)
    caminho_estado = salvar_csv(agregado_estado, "letalidade_por_estado_agregado.csv")
    print(f"Letalidade por estado (todos os anos somados, {len(agregado_estado)} estados) salva em: {caminho_estado}")
