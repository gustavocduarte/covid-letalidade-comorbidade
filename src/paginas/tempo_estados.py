"""Página Linha do tempo e estados: casos semanais, letalidade por estado e curvas por estado."""

import json

import altair as alt
import pandas as pd
import streamlit as st

from componentes import exibir_grafico, html_kpi, titulo_painel
from config import (
    CAMINHO_ESTADO,
    CAMINHO_GEOJSON,
    CAMINHO_SEMANAL,
    CAMINHO_SEMANAL_COMORBIDADE,
    CAMINHO_SEMANAL_ESTADO,
    COMORBIDADES_SOBREPOSTAS_INICIAIS,
    COR_GRADE,
    COR_TEXTO,
    DATA_INICIO_VACINACAO,
    MAXIMO_COMORBIDADES_SOBREPOSTAS,
    NOMES_CURTOS_COMORBIDADES,
    TIPOS_DE_MAPA,
)
from graficos import ESCALAS_SERIE, figura_blocos_estados, figura_mapa_estados, figura_serie_semanal
from indicadores_tempo import kpis_tempo, preparar_estados, resumo_por_estado
from qualidade import aviso_casos_sem_estado

# Referência temporal no gráfico da linha do tempo, sem implicar relação de causa e efeito.
DATA_INICIO_VACINACAO = pd.Timestamp(DATA_INICIO_VACINACAO)

with open(CAMINHO_GEOJSON, encoding="utf-8") as arquivo_geojson:
    geojson_brasil = json.load(arquivo_geojson)
nomes_estados = {f["properties"]["sigla"]: f["properties"]["nome"] for f in geojson_brasil["features"]}

df_semanal_estado = pd.read_csv(CAMINHO_SEMANAL_ESTADO, parse_dates=["semana"])
resumo_estados = resumo_por_estado(df_semanal_estado, nomes_estados)
st.html('<div class="cv-kpis">' + "".join(
    html_kpi(k.rotulo, k.valor, k.linha, k.cor, k.ajuda)
    for k in kpis_tempo(pd.read_csv(CAMINHO_SEMANAL, parse_dates=["semana"]), resumo_estados)
) + "</div>")

_semanal = pd.read_csv(CAMINHO_SEMANAL, parse_dates=["semana"])
_semanal_comorbidade = pd.read_csv(CAMINHO_SEMANAL_COMORBIDADE, parse_dates=["semana"])
_semanal_comorbidade["nome"] = _semanal_comorbidade["comorbidade"].map(NOMES_CURTOS_COMORBIDADES)

with st.container(border=True, key="painel_serie"):
    _cabecalho, _escala = st.columns([3, 1])
    with _cabecalho:
        titulo_painel(
            "Casos por semana · Brasil",
            "A linha tracejada marca o início da vacinação no Brasil, só como referência temporal: "
            "não indica relação de causa e efeito com a curva de casos.",
        )
    escala = _escala.segmented_control(
        "Escala", ESCALAS_SERIE, default=ESCALAS_SERIE[0], key="escala_serie", label_visibility="collapsed",
    ) or ESCALAS_SERIE[0]
    comorbidades_marcadas = st.multiselect(
        "Sobrepor comorbidades",
        sorted(NOMES_CURTOS_COMORBIDADES.values()),
        default=sorted(NOMES_CURTOS_COMORBIDADES[c] for c in COMORBIDADES_SOBREPOSTAS_INICIAIS),
        max_selections=MAXIMO_COMORBIDADES_SOBREPOSTAS,
        placeholder="Escolha até 3 comorbidades",
    )
    exibir_grafico(figura_serie_semanal(
        _semanal, _semanal_comorbidade[_semanal_comorbidade["nome"].isin(comorbidades_marcadas)],
        DATA_INICIO_VACINACAO, escala,
    ))
    st.caption(
        "A escala logarítmica mostra as ondas recentes, achatadas na linear. "
        "2026 é ano parcial."
    )

_estados = preparar_estados(pd.read_csv(CAMINHO_ESTADO), geojson_brasil)

with st.container(border=True, key="painel_estados"):
    _cabecalho, _tipo = st.columns([3, 1])
    with _cabecalho:
        titulo_painel(
            "Letalidade por estado",
            "Estados com poucos casos têm taxa menos estável: o número de casos aparece sobre os estados em que "
            "cabe e, em todos, ao passar o mouse.",
        )
    tipo_de_mapa = _tipo.segmented_control(
        "Tipo de mapa", TIPOS_DE_MAPA, default=TIPOS_DE_MAPA[0], key="tipo_de_mapa", label_visibility="collapsed",
    ) or TIPOS_DE_MAPA[0]
    aviso_sem_estado = aviso_casos_sem_estado()
    if aviso_sem_estado:
        st.info(aviso_sem_estado)
    exibir_grafico(
        figura_mapa_estados(_estados, geojson_brasil) if tipo_de_mapa == TIPOS_DE_MAPA[0]
        else figura_blocos_estados(_estados)
    )
    st.caption(
        '"Mapa" mostra o formato real do Brasil; "Blocos" dá o mesmo tamanho a cada estado, com sigla e letalidade legíveis.'
    )

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
    top3_siglas = _estados.sort_values("casos", ascending=False)["sigla"].head(3).tolist()
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
