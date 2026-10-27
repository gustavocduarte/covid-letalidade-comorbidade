"""Números da página Linha do tempo e estados, calculados só a partir dos CSVs semanais versionados."""

import pandas as pd

from config import (
    COR_ALERTA,
    COR_COM_COMORBIDADE,
    COR_FUNDO_PAGINA,
    DATA_INICIO_VACINACAO,
    ESCALA_LETALIDADE,
    FRACAO_PICO_DA_CAUDA,
)
from formatacao import fmt_inteiro
from indicadores import Kpi, juntar_nomes
from mapa import centro_aproximado, cor_texto_contraste

LIMITE_ESTADOS_NO_KPI = 3


def resumo_por_estado(semanal_estado: pd.DataFrame, nomes_estados: dict[str, str]) -> pd.DataFrame:
    """Por estado: semana e tamanho do pico e semanas do pico até os casos caírem abaixo de FRACAO_PICO_DA_CAUDA do pico.

    `semanas_ate_cauda` fica ausente (<NA>) quando o estado nunca cai abaixo do limiar depois do pico.
    """
    linhas = []
    for sigla, grupo in semanal_estado.groupby("sigla"):
        grupo = grupo.sort_values("semana").reset_index(drop=True)
        posicao_pico = grupo["casos"].idxmax()
        pico, semana_pico = grupo.loc[posicao_pico, "casos"], grupo.loc[posicao_pico, "semana"]
        depois = grupo.loc[posicao_pico:]
        abaixo = depois[depois["casos"] < pico * FRACAO_PICO_DA_CAUDA]
        semanas = int((abaixo.iloc[0]["semana"] - semana_pico).days // 7) if len(abaixo) else None
        linhas.append({
            "sigla": sigla, "nome": nomes_estados[sigla], "semana_pico": semana_pico,
            "casos_pico": int(pico), "semanas_ate_cauda": semanas,
        })
    resumo = pd.DataFrame(linhas)
    resumo["semanas_ate_cauda"] = resumo["semanas_ate_cauda"].astype("Int64")
    return resumo.sort_values(["semanas_ate_cauda", "nome"], ascending=[False, True], na_position="last").reset_index(drop=True)


def _nomes_no_kpi(nomes: list[str]) -> str:
    if len(nomes) > LIMITE_ESTADOS_NO_KPI:
        return f"{len(nomes)} estados empatados"
    return juntar_nomes(nomes)


def kpis_tempo(semanal: pd.DataFrame, resumo_estados: pd.DataFrame) -> list[Kpi]:
    """Os quatro números do topo: pico semanal, início da vacinação, cauda mais longa e semana mais recente."""
    semanal = semanal.sort_values("semana")
    pico = semanal.loc[semanal["casos"].idxmax()]
    recente = semanal.iloc[-1]
    maior_cauda = resumo_estados["semanas_ate_cauda"].max()
    empatados = resumo_estados.loc[resumo_estados["semanas_ate_cauda"] == maior_cauda, "nome"].tolist()
    return [
        Kpi("Pico semanal", fmt_inteiro(pico["casos"]), f"casos na semana de {pico['semana']:%d/%m/%Y}",
            cor=COR_COM_COMORBIDADE),
        Kpi("Início da vacinação", f"{DATA_INICIO_VACINACAO:%d/%m/%Y}", "Referência temporal, não causa", cor=COR_ALERTA),
        Kpi("Cauda mais longa", f"{maior_cauda} semanas", _nomes_no_kpi(empatados),
            ajuda="Semanas, depois do pico, até os casos semanais caírem abaixo de "
                  f"{FRACAO_PICO_DA_CAUDA:.0%} do pico do estado"),
        Kpi("Semana mais recente", fmt_inteiro(recente["casos"]), f"casos na semana de {recente['semana']:%d/%m/%Y}, ainda em notificação"),
    ]


def preparar_estados(estado: pd.DataFrame, geojson: dict) -> pd.DataFrame:
    """Letalidade por estado pronta para o mapa e para os blocos: taxa em %, nome, casos formatados, centro do estado
    e a cor do rótulo (branca ou escura) que contrasta com a cor do estado na escala."""
    df = estado.copy()
    df["taxa_letalidade"] = df["taxa_letalidade"] * 100
    df["nome"] = df["sigla"].map({f["properties"]["sigla"]: f["properties"]["nome"] for f in geojson["features"]})
    df["casos_fmt"] = df["casos"].map(fmt_inteiro)
    geometrias = {f["properties"]["sigla"]: f["geometry"] for f in geojson["features"]}
    centros = df["sigla"].map(lambda sigla: centro_aproximado(geometrias[sigla]))
    df["lon_centro"] = centros.map(lambda c: c[0])
    df["lat_centro"] = centros.map(lambda c: c[1])
    menor, maior = df["taxa_letalidade"].min(), df["taxa_letalidade"].max()
    df["cor_rotulo"] = df["taxa_letalidade"].map(
        lambda v: cor_texto_contraste(v, menor, maior, ESCALA_LETALIDADE, "#FFFFFF", COR_FUNDO_PAGINA)
    )
    return df


def normalizar_pelo_pico(semanal_estado: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta `pct_do_pico`: os casos de cada semana em % do maior valor semanal do próprio estado (0 a 100)."""
    df = semanal_estado.copy()
    df["pct_do_pico"] = df["casos"] / df.groupby("sigla")["casos"].transform("max") * 100
    return df
