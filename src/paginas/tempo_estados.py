"""Página Linha do tempo e estados: casos semanais, letalidade por estado e curvas por estado."""

import json

import altair as alt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from componentes import aplicar_template_grafico, html_kpi
from config import (
    ALTURA_MAPA_PX,
    CAMINHO_ESTADO,
    CAMINHO_GEOJSON,
    CAMINHO_SEMANAL,
    CAMINHO_SEMANAL_COMORBIDADE,
    CAMINHO_SEMANAL_ESTADO,
    COR_FUNDO_PAGINA,
    COR_GRADE,
    COR_SEM_COMORBIDADE,
    COR_TEXTO,
    DATA_INICIO_VACINACAO,
    ESCALA_LETALIDADE,
    ESTILO_MAPA,
    LARGURA_REFERENCIA_MAPA_PX,
    NOMES_COMORBIDADES,
)
from indicadores_tempo import kpis_tempo, resumo_por_estado
from mapa import (
    centro_aproximado,
    cor_texto_contraste,
    enquadramento,
    limites_do_geojson,
    siglas_com_rotulo,
)
from qualidade import aviso_casos_sem_estado

# Referência temporal no gráfico da linha do tempo, sem implicar relação de causa e efeito.
DATA_INICIO_VACINACAO = pd.Timestamp(DATA_INICIO_VACINACAO)
COR_LINHA_GERAL = COR_SEM_COMORBIDADE  # linha de referência no gráfico de linha do tempo

with open(CAMINHO_GEOJSON, encoding="utf-8") as arquivo_geojson:
    geojson_brasil = json.load(arquivo_geojson)
nomes_estados = {f["properties"]["sigla"]: f["properties"]["nome"] for f in geojson_brasil["features"]}

df_semanal_estado = pd.read_csv(CAMINHO_SEMANAL_ESTADO, parse_dates=["semana"])
resumo_estados = resumo_por_estado(df_semanal_estado, nomes_estados)
st.html('<div class="cv-kpis">' + "".join(
    html_kpi(k.rotulo, k.valor, k.linha, k.cor, k.ajuda)
    for k in kpis_tempo(pd.read_csv(CAMINHO_SEMANAL, parse_dates=["semana"]), resumo_estados)
) + "</div>")

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
    st.altair_chart(grafico_tempo, width="stretch")

with st.container(border=True):
    st.subheader("Letalidade de COVID por estado")
    st.caption(
        "Estados com poucos casos podem ter taxa de letalidade instável por causa da "
        "amostra pequena — por isso o número de casos aparece sobre os estados em que "
        "cabe e, em todos, no texto ao passar o mouse, pra essa instabilidade não "
        "ficar escondida atrás da cor."
    )
    aviso_sem_estado = aviso_casos_sem_estado()
    if aviso_sem_estado:
        st.info(aviso_sem_estado)

    # Trocamos o Altair/Vega-Lite pelo Plotly nesse mapa, e dentro do Plotly usamos
    # especificamente `choropleth_map` (WebGL/MapLibre) em vez de `choropleth` (SVG).
    # Diagnosticamos que essa máquina tem algum problema de renderização SVG geográfica
    # complexa: tanto o Altair quanto o `px.choropleth` desenhavam todo estado na mesma
    # caixa delimitadora (um em cima do outro), mesmo com geometria e lookup corretos —
    # confirmamos isso testando o GeoJSON num visualizador externo (geojson.io), que
    # renderizou perfeitamente. Só a versão WebGL (`choropleth_map`) funciona aqui.
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
        lambda v: cor_texto_contraste(v, minimo_taxa, maximo_taxa, ESCALA_LETALIDADE, "#FFFFFF", COR_FUNDO_PAGINA)
    )

    centro_mapa, zoom_mapa = enquadramento(
        limites_do_geojson(geojson_brasil), LARGURA_REFERENCIA_MAPA_PX, ALTURA_MAPA_PX
    )
    mapa = px.choropleth_map(
        df_estado,
        geojson=geojson_brasil,
        locations="sigla",
        featureidkey="properties.sigla",
        color="taxa_letalidade",
        color_continuous_scale=list(ESCALA_LETALIDADE),
        hover_name="nome",
        hover_data={"sigla": False, "taxa_letalidade": ":.1f", "casos_fmt": True},
        labels={"taxa_letalidade": "Taxa de letalidade (%)", "casos_fmt": "Casos de COVID"},
        map_style=ESTILO_MAPA,  # sem mapa-base externo
        center=centro_mapa,
        zoom=zoom_mapa,
        opacity=1,
    )
    # Número de casos sobre cada estado. textfont.color do Scattermap só
    # aceita uma cor por camada (não uma lista por ponto) — por isso separamos os estados
    # em dois grupos (rótulo branco / rótulo escuro) em vez de uma camada só.
    # O número só aparece onde cabe no estado; nos pequenos (litoral do Nordeste, ES, RJ...) fica no hover.
    com_rotulo = siglas_com_rotulo(
        geojson_brasil, zoom_mapa, dict(zip(df_estado["sigla"], df_estado["casos_fmt"], strict=True)),
        dict(zip(df_estado["sigla"], zip(df_estado["lon_centro"], df_estado["lat_centro"], strict=True), strict=True)),
    )
    for cor, grupo in df_estado[df_estado["sigla"].isin(com_rotulo)].groupby("cor_rotulo"):
        mapa.add_trace(go.Scattermap(
            lat=grupo["lat_centro"],
            lon=grupo["lon_centro"],
            mode="text",
            text=grupo["casos_fmt"],
            textfont={"size": 8, "color": cor},
            hoverinfo="skip",
            showlegend=False,
        ))

    aplicar_template_grafico(mapa)
    mapa.update_traces(marker_line_color=COR_FUNDO_PAGINA, marker_line_width=0.8, selector={"type": "choroplethmap"})
    mapa.update_layout(
        height=ALTURA_MAPA_PX,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
    )
    st.plotly_chart(mapa, width="stretch")

with st.container(border=True):
    st.subheader("Casos de COVID por estado ao longo do tempo")
    st.caption(
        "Cada linha é normalizada em relação ao próprio pico do estado (0% a 100%) — "
        "assim dá pra comparar o formato/tempo da curva entre estados, sem o volume "
        "bruto (que sempre favoreceria estados mais populosos, como São Paulo)."
    )

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
        st.altair_chart(grafico_estado_tempo, width="stretch")
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
