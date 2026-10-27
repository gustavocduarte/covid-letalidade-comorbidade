"""Números da página Linha do tempo e estados, calculados só a partir dos CSVs semanais versionados."""

import pandas as pd

from config import COR_ALERTA, COR_COM_COMORBIDADE, DATA_INICIO_VACINACAO, FRACAO_PICO_DA_CAUDA
from formatacao import fmt_inteiro
from indicadores import Kpi, juntar_nomes

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
        Kpi("Semana mais recente", fmt_inteiro(recente["casos"]), f"casos na semana de {recente['semana']:%d/%m/%Y}"),
    ]
