"""Constantes do projeto: caminhos, fontes de dados, colunas e códigos do SIVEP-Gripe."""

from dataclasses import dataclass
from datetime import date
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
# Altura do mapa e dos blocos dos estados; a largura é a do painel.
ALTURA_MAPA_PX = 600

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
NOME_RESUMO_GERAL = "resumo_geral.csv"
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

# Tema escuro do dashboard (as mesmas cores de .streamlit/config.toml, que um teste confere).
COR_FUNDO_PAGINA = "#0B0F14"
COR_FUNDO_BARRA = "#0E131A"
COR_FUNDO_PAINEL = "#121820"
COR_BORDA = "#243040"
COR_LINHA_TABELA = "#1A2230"
COR_TEXTO = "#E6EDF3"
COR_TEXTO_SECUNDARIO = "#9AA7B8"
COR_EIXO = "#7C8A9C"
COR_GRADE = "#243040"
COR_PRINCIPAL = "#22D3EE"
COR_COM_COMORBIDADE = "#F472B6"
COR_SEM_COMORBIDADE = "#94A3B8"
COR_POSITIVO = "#34D399"
COR_ALERTA = "#FACC15"
SEQUENCIA_CORES_SERIES = ("#4C83F0", "#F3A268", "#C7A0EE", "#22D3EE", "#BEF264", "#FACC15")
# Escala sequencial da letalidade: do escuro ao brilhante, legível sobre o fundo escuro.
ESCALA_LETALIDADE = ("#134E5E", "#0E8FA8", "#22D3EE", "#A5F3FC")
CONFIG_PLOTLY = {"displayModeBar": False}

# CSVs de saída que o dashboard lê (só estes, o relatório e o GeoJSON).
CAMINHO_AGREGADO = PROCESSED_DIR / NOME_AGREGADO
CAMINHO_SEMANAL = PROCESSED_DIR / NOME_SEMANAL
CAMINHO_SEMANAL_COMORBIDADE = PROCESSED_DIR / NOME_SEMANAL_COMORBIDADE
CAMINHO_ESTADO = PROCESSED_DIR / NOME_ESTADO
CAMINHO_TODOS_ANOS = PROCESSED_DIR / NOME_TODOS_ANOS
CAMINHO_SEMANAL_ESTADO = PROCESSED_DIR / NOME_SEMANAL_ESTADO
CAMINHO_RESUMO_GERAL = PROCESSED_DIR / NOME_RESUMO_GERAL

# Início da vacinação contra COVID-19 no Brasil.
DATA_INICIO_VACINACAO = date(2021, 1, 17)

# Páginas do dashboard: `arquivo` é relativo a src/ (onde fica o dashboard.py); `url` vai no endereço.
TITULO_APP = "Letalidade de COVID-19 · SRAG"
URL_REPOSITORIO = "https://github.com/gustavocduarte/covid-letalidade-comorbidade"


@dataclass(frozen=True)
class PaginaApp:
    chave: str
    titulo: str
    arquivo: str
    url: str
    icone: str
    descricoes: tuple[str, ...]
    padrao: bool = False


PAGINAS = (
    PaginaApp(
        chave="comorbidades",
        titulo="Comorbidades",
        arquivo="paginas/comorbidades.py",
        url="comorbidades",
        icone=":material/format_list_bulleted:",
        descricoes=(
            "Taxa de letalidade de casos de COVID-19 hospitalizados (SRAG) com e sem cada comorbidade, 2020–2026",
            "Letalidade = óbitos ÷ (óbitos + curas), só casos com desfecho conhecido. 2026 é ano parcial.",
        ),
        padrao=True,
    ),
    PaginaApp(
        chave="tempo_estados",
        titulo="Linha do tempo e estados",
        arquivo="paginas/tempo_estados.py",
        url="tempo-e-estados",
        icone=":material/show_chart:",
        descricoes=("Casos semanais de COVID-19 hospitalizados (SRAG) no Brasil e por estado, 2020–2026",),
    ),
    PaginaApp(
        chave="metodologia",
        titulo="Metodologia",
        arquivo="paginas/metodologia.py",
        url="metodologia",
        icone=":material/info:",
        descricoes=("Como os números são calculados, de onde vêm os dados e o que eles não permitem concluir",),
    ),
)

# Comorbidade com menos casos que isto tem taxa pouco estável (aviso de "amostra pequena" no dashboard).
LIMITE_AMOSTRA_PEQUENA = 10_000
# Diferença de letalidade (em pontos percentuais, em módulo) abaixo da qual o dashboard a trata como neutra.
FAIXA_NEUTRA_PP = 2.0
# A "cauda" de um estado termina na primeira semana depois do pico com casos abaixo desta fração do pico.
FRACAO_PICO_DA_CAUDA = 0.10

# Nomes curtos para legendas e rótulos apertados (a legenda cortava "Doença Cardiovascul...").
NOMES_CURTOS_COMORBIDADES = {
    "CARDIOPATI": "Cardiovascular",
    "HEMATOLOGI": "Hematológica",
    "SIND_DOWN": "Síndrome de Down",
    "HEPATICA": "Hepática",
    "ASMA": "Asma",
    "DIABETES": "Diabetes",
    "NEUROLOGIC": "Neurológica",
    "PNEUMOPATI": "Pneumopatia",
    "IMUNODEPRE": "Imunodeficiência",
    "RENAL": "Renal",
    "OBESIDADE": "Obesidade",
}
# Linhas de comorbidade já marcadas ao abrir a série semanal, e o máximo que cabe legível no gráfico.
COMORBIDADES_SOBREPOSTAS_INICIAIS = ("DIABETES", "CARDIOPATI")
MAXIMO_COMORBIDADES_SOBREPOSTAS = 3

# Posição (coluna, linha) de cada estado na grade de blocos, que dá o mesmo tamanho a todos e mantém a geografia aproximada.
GRADE_ESTADOS = {
    "RR": (2, 0), "AP": (4, 0),
    "AM": (1, 1), "PA": (3, 1), "MA": (5, 1), "CE": (6, 1), "RN": (7, 1),
    "AC": (0, 2), "RO": (1, 2), "MT": (2, 2), "TO": (3, 2), "PI": (5, 2), "PB": (7, 2),
    "MS": (2, 3), "GO": (3, 3), "DF": (4, 3), "BA": (5, 3), "PE": (6, 3), "AL": (7, 3),
    "PR": (3, 4), "SP": (4, 4), "MG": (5, 4), "SE": (6, 4),
    "SC": (3, 5), "RJ": (5, 5), "ES": (6, 5),
    "RS": (3, 6),
}
TIPOS_DE_MAPA = ("Mapa", "Blocos")
# Estados já marcados ao comparar as curvas, e o máximo que cabe nas cores da paleta de séries.
ESTADOS_COMPARADOS_INICIAIS = ("MG", "RJ", "SP")
MAXIMO_ESTADOS_COMPARADOS = 6
# Estados pequenos, onde o número de casos tem fonte menor para não embolar sem zoom.
SIGLAS_DE_ESTADOS_PEQUENOS = ("RN", "PB", "PE", "AL", "SE", "ES", "RJ", "DF")
TAMANHO_ROTULO_ESTADO = 10
TAMANHO_ROTULO_ESTADO_PEQUENO = 9
# Números do mapa: sempre brancos, com sombra escura curta para ler sobre qualquer tom da escala.
COR_ROTULO_MAPA = "#FFFFFF"
SOMBRA_ROTULO_MAPA = "0 0 2px #000, 0 0 2px #000, 1px 1px 2px #000"
