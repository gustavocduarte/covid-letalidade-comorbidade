# Letalidade de COVID-19 por Comorbidade — Brasil

![Testes](https://github.com/gustavocduarte/covid-letalidade-comorbidade/actions/workflows/tests.yml/badge.svg)

**[🔴 Ver o dashboard ao vivo](https://letalidade-covid-brasil.streamlit.app/)**

Pipeline de ETL (extração, tratamento e carga) e dashboard interativo que analisa a
**taxa de letalidade de COVID-19 por comorbidade, por estado e ao longo do tempo no
Brasil**, usando dados reais do SIVEP-Gripe (Ministério da Saúde).

## Print do dashboard

![Taxa de letalidade por comorbidade](docs/screenshot-comorbidades.png)
Taxa de letalidade por comorbidade — comparação entre quem tem e quem não tem cada condição.

![Mapa de letalidade por estado](docs/screenshot-mapa.png)
Mapa coroplético do Brasil com a taxa de letalidade de COVID-19 por estado.

![Casos por estado ao longo do tempo](docs/screenshot-linha-tempo.png)
Comparação da curva de casos entre estados ao longo do tempo, normalizada pelo pico de cada um.

## O que este projeto faz

- Baixa os bancos de dados oficiais do SIVEP-Gripe (2020 a 2026) direto do OpenDataSUS.
- Filtra só os casos confirmados de COVID-19 dentro do banco de SRAG (Síndrome
  Respiratória Aguda Grave, que inclui outras causas além de COVID).
- Calcula a taxa de letalidade (óbitos ÷ (óbitos + curas), entre casos com desfecho
  conhecido) para 11 comorbidades, comparando quem tinha a condição com quem não tinha.
- Calcula a mesma taxa por estado e ao longo do tempo (semanal).
- Converte cada ano em Parquet (DuckDB) e gera as tabelas com consultas SQL sobre eles, com
  memória limitada a 400 MB.
- Apresenta tudo num dashboard interativo (Streamlit): gráficos de barras, linha do
  tempo, mapa coroplético do Brasil por estado, e uma tabela explorável por comorbidade.

## Fonte dos dados

**SIVEP-Gripe** (Sistema de Informação da Vigilância Epidemiológica da Gripe), que
registra casos de Síndrome Respiratória Aguda Grave (SRAG) no Brasil. Dado bruto
disponibilizado pelo Ministério da Saúde através do
[OpenDataSUS](https://opendatasus.saude.gov.br/). Período coberto: 2020 a 2026 (2026 é
um ano parcial). Os contornos geográficos dos estados vêm da
[API oficial do IBGE](https://servicodados.ibge.gov.br/).

A metodologia completa (definição exata da taxa de letalidade e as limitações
identificadas) está documentada dentro do próprio dashboard, na seção
"Sobre este projeto / Metodologia".

## Como instalar e rodar

Estas instruções assumem que você nunca viu este projeto antes e está começando do zero.

> **Só quer ver o dashboard funcionando?** Os passos 5, 6 e 7 são **opcionais**.
> Os dados já processados (e o contorno geográfico dos estados) vêm prontos dentro
> do repositório, então você pode pular direto do passo 4 pro passo 8. Esses três
> passos só são necessários se você quiser gerar os dados novamente do zero — o que
> baixa ~4,9 GB de dados brutos do SIVEP-Gripe e pode demorar bastante.

### 1. Pré-requisitos

- Python 3.12 ou mais recente instalado ([python.org](https://www.python.org/downloads/)).
- Uns 6 GB de espaço livre em disco (os dados brutos baixados somam ~4,9 GB).

### 2. Baixar o projeto e entrar na pasta

```bash
git clone https://github.com/gustavocduarte/covid-letalidade-comorbidade.git
cd covid-letalidade-comorbidade
```

### 3. Criar e ativar um ambiente virtual

Um ambiente virtual isola as bibliotecas deste projeto do resto do seu sistema.

```bash
python -m venv .venv
```

Ativar (escolha o comando do seu sistema):

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (Git Bash) / Linux / macOS
source .venv/Scripts/activate   # Git Bash no Windows
source .venv/bin/activate       # Linux / macOS
```

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 5. Rodar o pipeline de dados (extração + tratamento + carga) — opcional

*Pule para o passo 8 se você só quer ver o dashboard funcionando com os dados que já
vêm prontos no repositório.*

Isso baixa os 7 anos de dados brutos do SIVEP-Gripe (~4,9 GB no total — pode demorar
dependendo da sua internet) e gera os arquivos processados usados pelo dashboard. Os
CSVs brutos ficam salvos permanentemente em `data/raw/`, então esse download só
acontece uma vez. Cada ano também vira um Parquet em `data/processed/detalhado/`
(`ano=AAAA/casos.parquet`, só os casos de COVID e as colunas usadas; fora do git).

O pipeline usa DuckDB e requests, que o `requirements.txt` do dashboard não traz:

```bash
pip install -e .
python src/pipeline.py
```

### 6. Baixar o contorno geográfico dos estados (pro mapa) — opcional

```bash
python src/baixar_geojson.py
```

### 7. Regerar só a série semanal de casos por estado — opcional

O `pipeline.py` já gera essa série. Este script a regera a partir dos Parquets, sem baixar
nem converter nada:

```bash
python src/gerar_serie_estado.py
```

### 8. Rodar o dashboard

```bash
streamlit run src/dashboard.py
```

Abra **http://localhost:8501** no navegador.

### Rodar os testes automatizados (opcional)

`requirements.txt` traz só o que o dashboard precisa. Para rodar o pipeline e os testes,
instale também as dependências do pipeline e as de desenvolvimento (pytest e ruff), que
estão declaradas no `pyproject.toml`:

```bash
pip install -r requirements.txt -e ".[dev]"
pytest
ruff check .
```

O teste de regressão "dourado" (`pytest -m golden`) roda o pipeline completo sobre os
dados brutos de `data/raw/` (~4,8 GB, uns 3 minutos) e compara com os CSVs versionados.
Ele fica fora da execução padrão e só roda sob demanda, localmente. Além dos CSVs, confere
que os Parquets batem com o resumo versionado em `tests/golden/detalhado_resumo.json`
(linhas, óbitos, curas, casos por UF e contagem de valores de cada coluna, por ano).

## Como o pipeline funciona

```
data/raw/INFLUDaa.csv ──► Parquet por ano ──► consultas SQL (DuckDB) ──► CSVs em data/processed/ ──► dashboard
   (194 colunas)          data/processed/       src/consultas.py          (pequenos, versionados)
                          detalhado/ano=AAAA/
                          (casos de COVID,
                           14 colunas)
```

1. `conversao.py` lê o CSV bruto com DuckDB, fica só com `CLASSI_FIN = 5` e as colunas
   usadas, com tipos (datas como DATE, códigos como inteiros), e grava um Parquet zstd.
2. `consultas.py` calcula letalidade por comorbidade e por estado e as séries semanais
   direto nos Parquets (uma view `casos` sobre `ano=*/`).
3. `pipeline.py` orquestra os dois passos e grava os CSVs com `load.py`.

**Memória e tamanho.** A conversão e as consultas rodam com o DuckDB limitado a 400 MB
(o excedente iria para disco temporário). Medido com o pandas como referência:

| | pandas | DuckDB (limite de 400 MB) |
|---|---|---|
| Ano 2021 (1,8 GB de CSV, 1,2 milhão de casos): pico de memória / tempo | 0,74 GiB / 24 s | 0,21 GiB / 12 s |
| Pipeline completo (7 anos): pico de memória / tempo | 0,74 GiB / 71 s | 0,19 GiB / 43 s |
| Casos de COVID de 2021 em disco | 71,1 MiB (CSV) | 4,3 a 5,0 MiB (Parquet zstd) |

Os Parquets dos 7 anos somam 8,4 MiB, contra 141 MB do cache em CSV que o pipeline gerava
antes.

## Estrutura de pastas

```
covid-letalidade-comorbidade/
├── data/
│   ├── raw/          # CSVs brutos do SIVEP-Gripe, um por ano (gerado pelo passo 5)
│   ├── processed/    # Dados já tratados, usados pelo dashboard (gerado pelos passos 5-7)
│   │   └── detalhado/  # Parquets por ano (ano=AAAA/casos.parquet), fora do git
│   └── geo/          # Contorno geográfico dos estados em GeoJSON (gerado pelo passo 6)
├── docs/             # Dicionário de dados oficial do SIVEP-Gripe (PDF) e texto extraído
├── src/
│   ├── extract.py              # E do ETL: baixa os CSVs brutos do OpenDataSUS
│   ├── conversao.py            # T do ETL: CSV bruto -> Parquet só com casos de COVID (DuckDB)
│   ├── consultas.py            # T do ETL: taxas de letalidade e séries semanais em SQL (DuckDB)
│   ├── transform.py            # Versão pandas das mesmas contas, mantida como referência dos testes
│   ├── load.py                 # L do ETL: salva os resultados em data/processed/
│   ├── config.py               # Caminhos, URLs, colunas e códigos de domínio
│   ├── pipeline.py             # Orquestra E-T-L pros 7 anos, um de cada vez
│   ├── baixar_geojson.py       # Baixa e verifica o contorno dos 27 estados (API do IBGE)
│   ├── gerar_serie_estado.py   # Gera a série semanal de casos por estado
│   └── dashboard.py            # O dashboard Streamlit em si
├── tests/
│   ├── test_transform.py       # Testes da lógica de transformação (versão pandas)
│   ├── test_conversao.py       # CSV bruto -> Parquet sobre a amostra sintética
│   ├── test_consultas.py       # Consultas SQL contra o pandas e contra valores calculados à mão
│   ├── test_travas.py          # As travas de teste: sem rede e sem escrita em data/
│   ├── test_pipeline_e2e.py    # Pipeline de ponta a ponta sobre uma amostra sintética
│   ├── test_golden.py          # Regressão: pipeline completo vs. CSVs versionados (só local)
│   ├── golden/                 # Resumo versionado dos Parquets (referência do teste golden)
│   └── fixtures/               # Amostra sintética do SIVEP-Gripe usada nos testes
├── pyproject.toml              # Dependências por grupo, Python mínimo e config do pytest/Ruff
├── requirements.txt            # Dependências do dashboard, com versões fixas (Streamlit Cloud)
├── CLAUDE.md                   # Regras de trabalho do projeto
└── README.md
```

## Notas técnicas

- O mapa por estado usa `plotly.express.choropleth_map` (renderização via WebGL/MapLibre)
  em vez de `choropleth` (SVG) ou do Altair — foi a solução encontrada pra um problema de
  renderização de mapas SVG complexos identificado durante o desenvolvimento neste
  ambiente específico.
- O campo de tabagismo (`TABAG`) existe no formulário oficial do SIVEP-Gripe, mas não é
  preenchido na prática pelos postos de saúde — por isso não entra na análise.
- Ferramentas de desenvolvimento (Ruff para lint, pytest para testes) ficam no extra `dev`
  do `pyproject.toml`, fora do `requirements.txt`, que o Streamlit Cloud lê para instalar
  só o dashboard: `pip install -r requirements.txt -e ".[dev]"`.
