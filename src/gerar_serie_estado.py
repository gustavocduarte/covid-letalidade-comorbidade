"""Gera a série semanal de casos de COVID por estado, a partir do cache de casos
detalhados que já temos salvo — não precisa reprocessar os CSVs brutos nem baixar nada."""

import pandas as pd

from config import NOME_CACHE_DETALHADO, NOME_SEMANAL_ESTADO, PROCESSED_DIR
from load import salvar_csv
from transform import serie_semanal_por_estado

CAMINHO_CACHE = PROCESSED_DIR / NOME_CACHE_DETALHADO

if __name__ == "__main__":
    print("Lendo cache de casos detalhados (só as colunas DT_SIN_PRI e SG_UF)...")
    covid = pd.read_csv(CAMINHO_CACHE, usecols=["DT_SIN_PRI", "SG_UF"])
    print(f"{len(covid):,} casos carregados.")

    serie = serie_semanal_por_estado(covid)
    caminho = salvar_csv(serie, NOME_SEMANAL_ESTADO)
    print(f"Série semanal por estado ({len(serie)} linhas) salva em: {caminho}")
