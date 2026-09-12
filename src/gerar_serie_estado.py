"""Gera a série semanal de casos de COVID por estado, a partir do cache de casos
detalhados que já temos salvo — não precisa reprocessar os CSVs brutos nem baixar nada."""

import pandas as pd

from load import PROCESSED_DIR, salvar_csv
from transform import serie_semanal_por_estado

CAMINHO_CACHE = PROCESSED_DIR / "casos_covid_detalhado.csv"

if __name__ == "__main__":
    print("Lendo cache de casos detalhados (só as colunas DT_SIN_PRI e SG_UF)...")
    covid = pd.read_csv(CAMINHO_CACHE, usecols=["DT_SIN_PRI", "SG_UF"])
    print(f"{len(covid):,} casos carregados.")

    serie = serie_semanal_por_estado(covid)
    caminho = salvar_csv(serie, "casos_covid_por_semana_estado.csv")
    print(f"Série semanal por estado ({len(serie)} linhas) salva em: {caminho}")
