"""Página Linha do tempo e estados: casos semanais, letalidade por estado e curvas por estado."""

import json

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
    DATA_INICIO_VACINACAO,
    ESTADOS_COMPARADOS_INICIAIS,
    FRACAO_PICO_DA_CAUDA,
    MAXIMO_COMORBIDADES_SOBREPOSTAS,
    MAXIMO_ESTADOS_COMPARADOS,
    NOMES_CURTOS_COMORBIDADES,
    TIPOS_DE_MAPA,
)
from graficos import (
    ESCALAS_SERIE,
    figura_blocos_estados,
    figura_curvas_estados,
    figura_mapa_estados,
    figura_serie_semanal,
)
from indicadores_tempo import kpis_tempo, normalizar_pelo_pico, preparar_estados, resumo_por_estado
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

_nome_para_sigla = {nome: sigla for sigla, nome in nomes_estados.items()}
_curvas = normalizar_pelo_pico(df_semanal_estado)

with st.container(border=True, key="painel_curvas"):
    titulo_painel(
        "Curva por estado · % do próprio pico",
        "Cada linha vai de 0% a 100% do pico do próprio estado, para comparar o formato e o momento das ondas "
        "sem o volume favorecer estados populosos.",
    )
    estados_marcados = st.multiselect(
        "Comparar estados",
        sorted(nomes_estados.values()),
        default=sorted(nomes_estados[s] for s in ESTADOS_COMPARADOS_INICIAIS),
        max_selections=MAXIMO_ESTADOS_COMPARADOS,
        placeholder="Escolha até 6 estados",
    )
    if estados_marcados:
        exibir_grafico(figura_curvas_estados(
            _curvas[_curvas["sigla"].isin(_nome_para_sigla[n] for n in estados_marcados)], nomes_estados,
        ))
    else:
        st.info("Selecione pelo menos um estado para ver o gráfico.")

with st.container(border=True, key="painel_cauda"):
    titulo_painel(
        "Pico e duração da cauda, por estado",
        "Semanas depois do pico até os casos semanais caírem abaixo de "
        f"{FRACAO_PICO_DA_CAUDA:.0%} do pico. Número maior = queda mais lenta.",
    )
    st.dataframe(
        resumo_estados[["nome", "semana_pico", "semanas_ate_cauda"]],
        hide_index=True,
        height="content",
        column_config={
            "nome": st.column_config.TextColumn("Estado"),
            "semana_pico": st.column_config.DateColumn("Semana do pico", format="DD/MM/YYYY"),
            "semanas_ate_cauda": st.column_config.ProgressColumn(
                "Semanas até cair abaixo de 10% do pico", format="%d", min_value=0,
                max_value=int(resumo_estados["semanas_ate_cauda"].max()),
            ),
        },
    )
    st.caption(f"{len(resumo_estados)} estados, ordenados pela cauda mais longa. Sem valor: o estado não caiu abaixo do limiar.")
