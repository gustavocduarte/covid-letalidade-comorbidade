"""Dashboard: visualiza a taxa de letalidade de COVID-19 por comorbidade."""

import json
from pathlib import Path

import altair as alt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from transform import NOMES_COMORBIDADES

CAMINHO_DADOS = Path(__file__).resolve().parent.parent / "data" / "processed" / "letalidade_por_comorbidade_agregado.csv"
CAMINHO_SEMANAL = Path(__file__).resolve().parent.parent / "data" / "processed" / "casos_covid_por_semana.csv"
CAMINHO_SEMANAL_COMORBIDADE = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "casos_covid_semanal_por_comorbidade.csv"
)
CAMINHO_ESTADO = Path(__file__).resolve().parent.parent / "data" / "processed" / "letalidade_por_estado_agregado.csv"
CAMINHO_SEMANAL_ESTADO = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "casos_covid_por_semana_estado.csv"
)
CAMINHO_GEOJSON = Path(__file__).resolve().parent.parent / "data" / "geo" / "brasil_estados.geojson"

# Data de início da vacinação contra COVID-19 no Brasil — usada só como referência
# temporal no gráfico de linha do tempo, sem implicar relação de causa e efeito.
DATA_INICIO_VACINACAO = pd.Timestamp("2021-01-17")

# Paleta do tema (tons de saúde): azul forte para o grupo de maior risco,
# azul claro para o grupo de referência, cinza bem escuro para texto.
COR_COM_COMORBIDADE = "#0D47A1"
COR_SEM_COMORBIDADE = "#90CAF9"
COR_TEXTO = "#212121"
COR_GRADE = "#E9ECEF"
COR_LINHA_GERAL = "#9AA5B1"  # cinza neutro, linha de referência no gráfico de linha do tempo


def _area_e_centroide_anel(anel: list[list[float]]) -> tuple[float, tuple[float, float]]:
    """Área (com sinal) e centroide de um anel de polígono, pela fórmula padrão de
    centroide de polígono — só soma/multiplicação, sem nenhuma biblioteca geoespacial
    (evitamos shapely/geopandas de propósito, essa máquina tem pouca memória livre)."""
    area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(anel)
    for i in range(n - 1):  # o último ponto do anel repete o primeiro, no padrão GeoJSON
        x0, y0 = anel[i]
        x1, y1 = anel[i + 1]
        cruz = x0 * y1 - x1 * y0
        area += cruz
        cx += (x0 + x1) * cruz
        cy += (y0 + y1) * cruz
    area /= 2.0
    if area == 0:
        xs = [p[0] for p in anel]
        ys = [p[1] for p in anel]
        return 0.0, (sum(xs) / len(xs), sum(ys) / len(ys))
    cx /= 6 * area
    cy /= 6 * area
    return abs(area), (cx, cy)


def centro_aproximado(geometria: dict) -> tuple[float, float]:
    """Centro aproximado (lon, lat) de um Polygon/MultiPolygon: usa o maior anel externo,
    pra ilhas distantes (ex: Fernando de Noronha, em Pernambuco) não puxarem o centro
    do rótulo pra longe do corpo principal do estado."""
    if geometria["type"] == "Polygon":
        aneis = [geometria["coordinates"][0]]
    else:
        aneis = [poligono[0] for poligono in geometria["coordinates"]]

    maior_area = -1.0
    melhor_centro = None
    for anel in aneis:
        area, centro = _area_e_centroide_anel(anel)
        if area > maior_area:
            maior_area = area
            melhor_centro = centro
    return melhor_centro


def _hex_para_rgb(hex_cor: str) -> tuple[int, int, int]:
    """Converte uma cor hexadecimal (`#RRGGBB`) numa tupla RGB (0-255)."""
    hex_cor = hex_cor.lstrip("#")
    return tuple(int(hex_cor[i:i + 2], 16) for i in (0, 2, 4))


def cor_texto_contraste(valor: float, minimo: float, maximo: float) -> str:
    """Escolhe branco ou cinza escuro pro rótulo, conforme o tom de azul de fundo naquele
    valor (interpolando entre as duas cores da escala do mapa)."""
    t = 0.5 if maximo == minimo else (valor - minimo) / (maximo - minimo)
    r0, g0, b0 = _hex_para_rgb(COR_SEM_COMORBIDADE)
    r1, g1, b1 = _hex_para_rgb(COR_COM_COMORBIDADE)
    r = r0 + t * (r1 - r0)
    g = g0 + t * (g1 - g0)
    b = b0 + t * (b1 - b0)
    luminancia = 0.299 * r + 0.587 * g + 0.114 * b
    return "#FFFFFF" if luminancia < 140 else COR_TEXTO


st.set_page_config(page_title="Letalidade por Comorbidade - COVID-19 Brasil", layout="wide")

st.title("Letalidade de COVID-19 por Comorbidade — Brasil, 2020–2026")
st.info(
    "**Fonte:** SIVEP-Gripe (SRAG) / Ministério da Saúde, via OpenDataSUS. "
    "Taxa de letalidade = óbitos / (óbitos + curas), entre casos com desfecho conhecido.\n\n"
    "Cada par de barras compara dois grupos separados de pacientes — quem tinha a comorbidade "
    "e quem não tinha. As duas taxas não somam entre si; são percentuais independentes.\n\n"
    "Os números abaixo somam os 7 anos (2020–2026). **2026 é um ano parcial** (dados só até o "
    "mês mais recente coletado pelo Ministério da Saúde), mas já está incluído nesse total."
)

st.markdown(
    f'<div style="height:4px;border-radius:2px;margin:1.5rem 0 1rem 0;'
    f'background:linear-gradient(to right, {COR_COM_COMORBIDADE}, {COR_SEM_COMORBIDADE});"></div>',
    unsafe_allow_html=True,
)

df = pd.read_csv(CAMINHO_DADOS)
df["comorbidade"] = df["comorbidade"].map(NOMES_COMORBIDADES)

# O CSV guarda a taxa em fração (0.571). Convertemos pra porcentagem uma única vez,
# aqui na camada de apresentação — o arquivo em disco continua em fração.
df["taxa_letalidade_com"] = df["taxa_letalidade_com"] * 100
df["taxa_letalidade_sem"] = df["taxa_letalidade_sem"] * 100

df = df.sort_values("taxa_letalidade_com", ascending=False)

with st.container(border=True):
    st.subheader("Taxa de letalidade: com a comorbidade vs. sem")

    # Ordem das comorbidades no eixo (mesma ordem em que o DataFrame já está: maior -> menor).
    ordem_comorbidades = df["comorbidade"].tolist()

    # st.bar_chart não dá controle suficiente sobre orientação horizontal + rótulos de valor
    # + cores de eixo/grade ao mesmo tempo, então aqui usamos o Altair diretamente (biblioteca
    # que o próprio Streamlit usa por baixo dos panos). Isso exige os dados em formato "longo":
    # uma linha por combinação de comorbidade + grupo (com/sem), em vez de uma coluna por grupo.
    df_grafico = df.melt(
        id_vars="comorbidade",
        value_vars=["taxa_letalidade_com", "taxa_letalidade_sem"],
        var_name="grupo",
        value_name="taxa",
    )
    df_grafico["grupo"] = df_grafico["grupo"].map({
        "taxa_letalidade_com": "Com a comorbidade",
        "taxa_letalidade_sem": "Sem a comorbidade",
    })

    base = alt.Chart(df_grafico).encode(
        y=alt.Y("comorbidade:N", sort=ordem_comorbidades, title=None,
                axis=alt.Axis(labelColor=COR_TEXTO, labelLimit=280, labelFontSize=12)),
        yOffset=alt.YOffset("grupo:N", sort=["Com a comorbidade", "Sem a comorbidade"]),
        x=alt.X("taxa:Q", title="Taxa de letalidade (%)",
                axis=alt.Axis(labelColor=COR_TEXTO, titleColor=COR_TEXTO, gridColor=COR_GRADE)),
        color=alt.Color(
            "grupo:N",
            scale=alt.Scale(domain=["Com a comorbidade", "Sem a comorbidade"],
                             range=[COR_COM_COMORBIDADE, COR_SEM_COMORBIDADE]),
            legend=alt.Legend(title=None, labelColor=COR_TEXTO, orient="top"),
        ),
    )
    barras = base.mark_bar()
    rotulos = base.mark_text(align="left", dx=4, color=COR_TEXTO, fontSize=11).encode(
        text=alt.Text("taxa:Q", format=".1f")
    )

    grafico_final = (
        (barras + rotulos)
        .properties(height=480, background="transparent")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(grafico_final, use_container_width=True)

st.subheader("Tabela completa")
# Seleciona só as colunas de exibição — o df também carrega obitos_com/desfecho_conhecido_com
# etc., usados internamente pra agregar os anos com exatidão, mas que não aparecem na tela.
df_tabela = df[["comorbidade", "casos_com", "taxa_letalidade_com", "casos_sem", "taxa_letalidade_sem"]].copy()
df_tabela["casos_com"] = df_tabela["casos_com"].apply(lambda x: f"{x:,}".replace(",", "."))
df_tabela["casos_sem"] = df_tabela["casos_sem"].apply(lambda x: f"{x:,}".replace(",", "."))
st.dataframe(
    df_tabela,
    hide_index=True,
    column_config={
        "comorbidade": st.column_config.TextColumn("Comorbidade"),
        "casos_com": st.column_config.TextColumn("Casos (com)"),
        "taxa_letalidade_com": st.column_config.NumberColumn("Taxa de Letalidade % (com)", format="%.1f"),
        "casos_sem": st.column_config.TextColumn("Casos (sem)"),
        "taxa_letalidade_sem": st.column_config.NumberColumn("Taxa de Letalidade % (sem)", format="%.1f"),
    },
)

with st.container(border=True):
    st.subheader("Casos de COVID ao longo do tempo")
    st.caption(
        "A linha pontilhada marca o início da vacinação no Brasil, só como referência "
        "temporal — não indica relação direta de causa e efeito com a curva de casos."
    )

    df_semanal = pd.read_csv(CAMINHO_SEMANAL, parse_dates=["semana"])

    df_semanal_comorbidade = pd.read_csv(CAMINHO_SEMANAL_COMORBIDADE, parse_dates=["semana"])
    df_semanal_comorbidade["comorbidade"] = df_semanal_comorbidade["comorbidade"].map(NOMES_COMORBIDADES)

    comorbidades_selecionadas = st.pills(
        "Sobrepor comorbidades:",
        options=sorted(NOMES_COMORBIDADES.values()),
        selection_mode="multi",
        default=[],
    )

    # A linha geral (cinza) fica sempre visível, como referência de fundo.
    linha_geral = alt.Chart(df_semanal).mark_line(color=COR_LINHA_GERAL, strokeWidth=2).encode(
        x=alt.X("semana:T", title=None,
                axis=alt.Axis(labelColor=COR_TEXTO, titleColor=COR_TEXTO, gridColor=COR_GRADE)),
        y=alt.Y("casos:Q", title="Casos de COVID (SRAG) por semana",
                axis=alt.Axis(labelColor=COR_TEXTO, titleColor=COR_TEXTO, gridColor=COR_GRADE)),
        tooltip=[
            alt.Tooltip("semana:T", title="Semana"),
            alt.Tooltip("casos:Q", title="Total (todas as comorbidades)", format=","),
        ],
    )
    camadas = [linha_geral]

    # Cada comorbidade marcada vira uma linha colorida sobreposta — desmarcar tira a linha.
    if comorbidades_selecionadas:
        df_filtrado = df_semanal_comorbidade[df_semanal_comorbidade["comorbidade"].isin(comorbidades_selecionadas)]
        linhas_comorbidade = alt.Chart(df_filtrado).mark_line(strokeWidth=2).encode(
            x="semana:T",
            y="casos:Q",
            color=alt.Color(
                "comorbidade:N",
                scale=alt.Scale(scheme="tableau10"),
                legend=alt.Legend(title=None, labelColor=COR_TEXTO, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("comorbidade:N", title="Comorbidade"),
                alt.Tooltip("semana:T", title="Semana"),
                alt.Tooltip("casos:Q", title="Casos", format=","),
            ],
        )
        camadas.append(linhas_comorbidade)

    df_vacina = pd.DataFrame({"data": [DATA_INICIO_VACINACAO]})
    marcador_vacina = alt.Chart(df_vacina).mark_rule(
        strokeDash=[5, 5], color=COR_TEXTO, strokeWidth=1.5
    ).encode(x="data:T")
    rotulo_vacina = alt.Chart(df_vacina).mark_text(
        align="left", baseline="top", dx=6, dy=4, color=COR_TEXTO, fontSize=11, fontStyle="italic"
    ).encode(x="data:T", y=alt.value(4), text=alt.value("Início da vacinação no Brasil"))
    camadas += [marcador_vacina, rotulo_vacina]

    grafico_tempo = (
        alt.layer(*camadas)
        .properties(height=380, background="transparent")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(grafico_tempo, use_container_width=True)

with st.container(border=True):
    st.subheader("Letalidade de COVID por estado")
    st.caption(
        "Estados com poucos casos podem ter taxa de letalidade instável por causa da "
        "amostra pequena — o número de casos fica sempre visível sobre cada estado (e "
        "também no texto ao passar o mouse), de propósito, pra essa instabilidade não "
        "ficar escondida atrás da cor."
    )

    # Trocamos o Altair/Vega-Lite pelo Plotly nesse mapa, e dentro do Plotly usamos
    # especificamente `choropleth_map` (WebGL/MapLibre) em vez de `choropleth` (SVG).
    # Diagnosticamos que essa máquina tem algum problema de renderização SVG geográfica
    # complexa: tanto o Altair quanto o `px.choropleth` desenhavam todo estado na mesma
    # caixa delimitadora (um em cima do outro), mesmo com geometria e lookup corretos —
    # confirmamos isso testando o GeoJSON num visualizador externo (geojson.io), que
    # renderizou perfeitamente. Só a versão WebGL (`choropleth_map`) funciona aqui.
    with open(CAMINHO_GEOJSON, encoding="utf-8") as arquivo_geojson:
        geojson_brasil = json.load(arquivo_geojson)
    nomes_estados = {f["properties"]["sigla"]: f["properties"]["nome"] for f in geojson_brasil["features"]}

    df_estado = pd.read_csv(CAMINHO_ESTADO)
    df_estado["taxa_letalidade"] = df_estado["taxa_letalidade"] * 100
    df_estado["casos_fmt"] = df_estado["casos"].apply(lambda x: f"{x:,}".replace(",", "."))
    df_estado["nome"] = df_estado["sigla"].map(nomes_estados)

    # Centro aproximado de cada estado (aritmética simples, sem shapely/geopandas — ver
    # centro_aproximado() no topo do arquivo), pra posicionar o número de casos fixo no mapa.
    geometria_por_sigla = {f["properties"]["sigla"]: f["geometry"] for f in geojson_brasil["features"]}
    centros = df_estado["sigla"].map(lambda s: centro_aproximado(geometria_por_sigla[s]))
    df_estado["lon_centro"] = centros.map(lambda c: c[0])
    df_estado["lat_centro"] = centros.map(lambda c: c[1])

    minimo_taxa = df_estado["taxa_letalidade"].min()
    maximo_taxa = df_estado["taxa_letalidade"].max()
    df_estado["cor_rotulo"] = df_estado["taxa_letalidade"].apply(
        lambda v: cor_texto_contraste(v, minimo_taxa, maximo_taxa)
    )

    mapa = px.choropleth_map(
        df_estado,
        geojson=geojson_brasil,
        locations="sigla",
        featureidkey="properties.sigla",
        color="taxa_letalidade",
        color_continuous_scale=[COR_SEM_COMORBIDADE, COR_COM_COMORBIDADE],
        hover_name="nome",
        hover_data={"sigla": False, "taxa_letalidade": ":.1f", "casos_fmt": True},
        labels={"taxa_letalidade": "Taxa de letalidade (%)", "casos_fmt": "Casos de COVID"},
        map_style="carto-positron",
        center={"lat": -14.2, "lon": -51.9},
        zoom=2.7,
        opacity=0.8,
    )
    # Número de casos sempre visível sobre cada estado. textfont.color do Scattermap só
    # aceita uma cor por camada (não uma lista por ponto) — por isso separamos os estados
    # em dois grupos (rótulo branco / rótulo escuro) em vez de uma camada só.
    for cor, grupo in df_estado.groupby("cor_rotulo"):
        mapa.add_trace(go.Scattermap(
            lat=grupo["lat_centro"],
            lon=grupo["lon_centro"],
            mode="text",
            text=grupo["casos_fmt"],
            textfont={"size": 8, "color": cor},
            hoverinfo="skip",
            showlegend=False,
        ))

    mapa.update_layout(
        height=520,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=COR_TEXTO,
    )
    st.plotly_chart(mapa, use_container_width=True)

with st.container(border=True):
    st.subheader("Casos de COVID por estado ao longo do tempo")
    st.caption(
        "Cada linha é normalizada em relação ao próprio pico do estado (0% a 100%) — "
        "assim dá pra comparar o formato/tempo da curva entre estados, sem o volume "
        "bruto (que sempre favoreceria estados mais populosos, como São Paulo)."
    )

    df_semanal_estado = pd.read_csv(CAMINHO_SEMANAL_ESTADO, parse_dates=["semana"])
    df_semanal_estado["nome"] = df_semanal_estado["sigla"].map(nomes_estados)

    # Normaliza cada estado em relação ao seu próprio pico (0-100%), não ao volume bruto.
    picos_por_estado = df_semanal_estado.groupby("sigla")["casos"].transform("max")
    df_semanal_estado["casos_pct_pico"] = df_semanal_estado["casos"] / picos_por_estado * 100

    nomes_para_sigla = {v: k for k, v in nomes_estados.items()}

    # Começa com os 3 estados de mais casos já marcados, pra não abrir com o gráfico vazio.
    top3_siglas = df_estado.sort_values("casos", ascending=False)["sigla"].head(3).tolist()
    default_nomes = [nomes_estados[sigla] for sigla in top3_siglas]

    estados_selecionados = st.pills(
        "Comparar estados:",
        options=sorted(nomes_estados.values()),
        selection_mode="multi",
        default=default_nomes,
        key="pills_estados_tempo",
    )

    if estados_selecionados:
        siglas_selecionadas = [nomes_para_sigla[nome] for nome in estados_selecionados]
        df_filtrado_estado = df_semanal_estado[df_semanal_estado["sigla"].isin(siglas_selecionadas)]

        linhas_estado = alt.Chart(df_filtrado_estado).mark_line(strokeWidth=2).encode(
            x=alt.X("semana:T", title=None,
                    axis=alt.Axis(labelColor=COR_TEXTO, titleColor=COR_TEXTO, gridColor=COR_GRADE)),
            y=alt.Y("casos_pct_pico:Q", title="% do pico do próprio estado",
                    axis=alt.Axis(labelColor=COR_TEXTO, titleColor=COR_TEXTO, gridColor=COR_GRADE)),
            color=alt.Color(
                "nome:N",
                scale=alt.Scale(scheme="tableau10"),
                legend=alt.Legend(title=None, labelColor=COR_TEXTO, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("nome:N", title="Estado"),
                alt.Tooltip("semana:T", title="Semana"),
                alt.Tooltip("casos:Q", title="Casos", format=","),
                alt.Tooltip("casos_pct_pico:Q", title="% do pico", format=".0f"),
            ],
        )
        grafico_estado_tempo = (
            linhas_estado
            .properties(height=380, background="transparent")
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(grafico_estado_tempo, use_container_width=True)
    else:
        st.info("Selecione pelo menos um estado pra ver o gráfico.")

    st.markdown("**Pico e duração da cauda, por estado**")
    st.caption(
        "\"Semanas até cair pra <10% do pico\" conta quantas semanas, depois do pico, o "
        "estado levou até os casos semanais caírem abaixo de 10% do valor máximo — um "
        "número maior indica uma cauda mais longa (queda mais lenta pra depois do pico)."
    )

    linhas_resumo = []
    for sigla, grupo in df_semanal_estado.groupby("sigla"):
        grupo = grupo.sort_values("semana").reset_index(drop=True)
        idx_pico = grupo["casos"].idxmax()
        pico = grupo.loc[idx_pico, "casos"]
        semana_pico = grupo.loc[idx_pico, "semana"]
        limiar = pico * 0.10
        depois_pico = grupo.loc[idx_pico:]
        abaixo_do_limiar = depois_pico[depois_pico["casos"] < limiar]
        if len(abaixo_do_limiar) > 0:
            semanas_cauda = int((abaixo_do_limiar.iloc[0]["semana"] - semana_pico).days // 7)
        else:
            semanas_cauda = None
        linhas_resumo.append({
            "nome": nomes_estados[sigla],
            "semana_pico": semana_pico,
            "semanas_ate_10pct": semanas_cauda,
        })

    df_resumo_estado = pd.DataFrame(linhas_resumo).sort_values(
        "semanas_ate_10pct", ascending=False, na_position="last"
    )
    st.dataframe(
        df_resumo_estado,
        hide_index=True,
        column_config={
            "nome": st.column_config.TextColumn("Estado"),
            "semana_pico": st.column_config.DateColumn("Semana do pico", format="DD/MM/YYYY"),
            "semanas_ate_10pct": st.column_config.NumberColumn("Semanas até cair p/ <10% do pico", format="%d"),
        },
    )

st.divider()

st.subheader("Explorar uma comorbidade")
comorbidade_escolhida = st.selectbox("Escolha uma comorbidade:", df["comorbidade"])
linha = df[df["comorbidade"] == comorbidade_escolhida].iloc[0]

# Acento de cor nos dois primeiros cartões, ecoando a paleta do gráfico.
# `key=` no container gera uma classe CSS "st-key-<nome>" exclusiva, que dá
# pra mirar com CSS customizado sem afetar o cartão "Casos" (sem key/cor).
st.markdown(
    f"""
    <style>
    div[class*="st-key-card_com"] {{
        border-color: {COR_COM_COMORBIDADE} !important;
        border-width: 2px !important;
    }}
    div[class*="st-key-card_sem"] {{
        border-color: {COR_SEM_COMORBIDADE} !important;
        border-width: 2px !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(3)
with c1.container(border=True, key="card_com"):
    st.metric(
        "Letalidade COM a comorbidade", f"{linha['taxa_letalidade_com']:.1f}%",
        delta=f"{linha['taxa_letalidade_com'] - linha['taxa_letalidade_sem']:.1f} p.p.", delta_color="inverse",
    )
with c2.container(border=True, key="card_sem"):
    st.metric("Letalidade SEM a comorbidade", f"{linha['taxa_letalidade_sem']:.1f}%")
with c3.container(border=True):
    st.metric("Casos com essa comorbidade", f"{linha['casos_com']:,}".replace(",", "."))

st.divider()

st.markdown(
    f"""
    <div style="background:{COR_SEM_COMORBIDADE}26; border-left:4px solid {COR_COM_COMORBIDADE};
                border-radius:6px; padding:1rem 1.25rem; margin-bottom:1.25rem;">
        <div style="font-weight:600; font-size:1.05rem; margin-bottom:0.6rem; color:{COR_TEXTO};">
            Principais achados
        </div>
        <p style="color:{COR_TEXTO}; margin:0 0 0.75rem 0; line-height:1.55;">
            Das 11 comorbidades analisadas, a <strong>Doença Renal Crônica</strong> aparece com o
            maior risco: pacientes com essa condição têm uma taxa de letalidade de COVID-19
            quase <strong>1,5 vez maior</strong> do que pacientes sem ela (53% contra 37%, somando
            os 7 anos de dados). Doença Neurológica e Pneumopatia aparecem logo atrás, numa faixa
            de risco parecida.
        </p>
        <p style="color:{COR_TEXTO}; margin:0 0 0.75rem 0; line-height:1.55;">
            O número de casos caiu de forma acentuada depois do início da vacinação no Brasil
            (17/01/2021), como fica visível no gráfico de linha do tempo mais abaixo. É importante
            não interpretar isso como uma prova direta de causa e efeito: no mesmo período, outros
            fatores — como isolamento social e a evolução natural da pandemia — também
            influenciaram essa queda. A vacinação está marcada no gráfico só como referência
            temporal.
        </p>
        <p style="color:{COR_TEXTO}; margin:0; line-height:1.55;">
            Um ponto de atenção importante: como muitos pacientes têm mais de uma comorbidade ao
            mesmo tempo, o grupo "sem" determinada condição não representa pessoas saudáveis — só
            pessoas sem aquela condição específica, que podem ter outras. É por isso, por exemplo,
            que <strong>Asma</strong> e <strong>Obesidade</strong> aparecem com letalidade menor que
            a média geral: não é porque essas condições protegem contra COVID-19, e sim,
            provavelmente, porque pacientes com essas comorbidades tendem a ser mais jovens em
            média — e a idade em si é um forte fator de risco separado.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Sobre este projeto / Metodologia"):
    st.markdown(
        """
**Fonte dos dados**
SIVEP-Gripe (Sistema de Informação da Vigilância Epidemiológica da Gripe), que registra
casos de Síndrome Respiratória Aguda Grave (SRAG) no Brasil. Dado bruto disponibilizado
pelo Ministério da Saúde através do OpenDataSUS.

**Período coberto**
2020 a 2026. **2026 é um ano parcial** — os dados só vão até o mês mais recente
disponibilizado pelo Ministério da Saúde no momento da extração, não um ano fechado.

**Definição da taxa de letalidade**
Óbitos ÷ (óbitos + curas), considerando **apenas casos com desfecho conhecido**. Casos
ignorados, em aberto (sem desfecho registrado ainda) ou óbito por outra causa são
excluídos do cálculo — tanto do numerador quanto do denominador.

**Limitações metodológicas identificadas**
- *Confundimento por comorbidades múltiplas*: pacientes podem ter mais de uma comorbidade
  registrada ao mesmo tempo. Isso faz os grupos de comparação "com" e "sem" cada condição
  se sobreporem parcialmente entre si — por exemplo, parte do grupo "sem Diabetes" pode ter
  Doença Cardiovascular Crônica, e vice-versa. As taxas aqui não isolam o efeito de uma
  única comorbidade de forma independente das demais.
- *Comorbidades raras têm amostra pequena*: condições com poucos casos registrados na base
  (como Síndrome de Down) têm taxas de letalidade estatisticamente menos confiáveis — um
  punhado de casos a mais ou a menos muda a taxa de forma desproporcional. O mapa por
  estado tem o mesmo problema para estados com poucos casos.
- *Tabagismo (TABAG) não incluído*: esse campo existe no formulário oficial do SIVEP-Gripe,
  mas checamos e ele não é preenchido na prática pelos postos de saúde (100% vazio em
  todos os 7 anos) — por isso foi excluído da análise, em vez de mostrar uma comorbidade
  sem dado real por trás.
        """
    )
