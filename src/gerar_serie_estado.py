"""Gera a série semanal de casos de COVID por estado a partir dos Parquets de casos já
convertidos — não precisa reprocessar os CSVs brutos nem baixar nada."""

from config import NOME_SEMANAL_ESTADO, PASTA_DETALHADO, URLS_SRAG
from consultas import abrir_casos, serie_semanal_por_estado
from load import salvar_csv

if __name__ == "__main__":
    with abrir_casos(PASTA_DETALHADO, anos=URLS_SRAG) as con:
        serie = serie_semanal_por_estado(con)
    caminho = salvar_csv(serie, NOME_SEMANAL_ESTADO)
    print(f"Série semanal por estado ({len(serie)} linhas) salva em: {caminho}")
