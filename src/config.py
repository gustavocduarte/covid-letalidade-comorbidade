"""Constantes do projeto: caminhos, fontes de dados, colunas e códigos do SIVEP-Gripe."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_RAW = RAIZ / "data" / "raw"
PROCESSED_DIR = RAIZ / "data" / "processed"
PASTA_GEO = RAIZ / "data" / "geo"
# Um Parquet por ano (ano=AAAA/casos.parquet), só com os casos de COVID e as colunas usadas.
PASTA_DETALHADO = PROCESSED_DIR / "detalhado"
NOME_PARQUET_ANO = "casos.parquet"
# O que já foi convertido em cada ano (fica ao lado dos Parquets, fora do git).
NOME_ESTADO_PIPELINE = "estado.json"
# Sobe quando muda a conversão (colunas, filtro, tipos): força reconverter todos os anos.
VERSAO_CONVERSAO = 1
CAMINHO_GEOJSON = PASTA_GEO / "brasil_estados.geojson"
# Quadro do mapa: a altura é fixa; a largura é só a de referência para o enquadramento (o gráfico ocupa
# a largura do painel), então telas mais estreitas que ela cortam um pouco as bordas.
ALTURA_MAPA_PX = 600
LARGURA_REFERENCIA_MAPA_PX = 640

# URLs oficiais do banco de SRAG por ano, hospedadas pelo Ministério da Saúde (OpenDataSUS).
# Conferidas em 2026-09-11 (a URL de cada ano muda de tempos em tempos, porque inclui a
# data da última atualização do "banco vivo" daquele ano).
URLS_SRAG = {
    2020: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2020/INFLUD20-23-03-2026.csv",
    2021: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2021/INFLUD21-23-03-2026.csv",
    2022: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2022/INFLUD22-23-03-2026.csv",
    2023: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2023/INFLUD23-23-03-2026.csv",
    2024: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2024/INFLUD24-23-03-2026.csv",
    2025: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2025/INFLUD25-24-08-2026.csv",
    2026: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26-24-08-2026.csv",
}

# API de localidades e malhas do IBGE (contorno dos estados).
URL_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
URL_MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{sigla}?formato=application/vnd.geo+json"

# Os CSVs brutos do OpenDataSUS são UTF-8 (conferido linha a linha nos 7 anos). O DuckDB valida
# a codificação e rejeita latin-1/windows-1252 nesses arquivos.
ENCODING_CSV = "utf-8"
# Teto de memória do DuckDB na conversão (o excedente vai para disco temporário).
DUCKDB_LIMITE_MEMORIA = "400MB"

# Nomes dos arquivos gerados em data/processed/.
NOME_TODOS_ANOS = "letalidade_por_comorbidade_todos_anos.csv"
NOME_AGREGADO = "letalidade_por_comorbidade_agregado.csv"
NOME_SEMANAL = "casos_covid_por_semana.csv"
NOME_SEMANAL_COMORBIDADE = "casos_covid_semanal_por_comorbidade.csv"
NOME_ESTADO = "letalidade_por_estado_agregado.csv"
NOME_SEMANAL_ESTADO = "casos_covid_por_semana_estado.csv"
NOME_RELATORIO = "relatorio_qualidade.json"

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

# Códigos do dicionário de dados: CLASSI_FIN 5 = COVID-19; EVOLUCAO 1 = cura, 2 = óbito
# (os dois desfechos "conhecidos"); comorbidade 1 = sim, 2 = não.
CLASSI_FIN_COVID = 5
EVOLUCAO_CURA = 1
EVOLUCAO_OBITO = 2
COMORBIDADE_SIM = 1
COMORBIDADE_NAO = 2

# Validação dos dados (src/validacao.py).
UFS_VALIDAS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]
# Domínios do dicionário de dados: EVOLUCAO 1 cura, 2 óbito, 3 óbito por outras causas, 9 ignorado;
# comorbidade 1 sim, 2 não, 9 ignorado. Vazio (nulo) vale em todas.
EVOLUCAO_DOMINIO = (1, 2, 3, 9)
COMORBIDADE_DOMINIO = (1, 2, 9)
# Os arquivos anuais são cortados por semana epidemiológica, então as datas de início dos sintomas
# podem passar do ano civil por alguns dias (ex.: o arquivo de 2025 vai até 03/01/2026).
JANELA_DATA_DIAS = 7
# Fração de casos com data ausente ou fora da janela: acima disso é erro; até aí, só aviso.
LIMITE_DATA_INVALIDA = 0.01
# Fração de casos sem desfecho conhecido acima da qual se emite aviso.
LIMITE_SEM_DESFECHO = 0.20
