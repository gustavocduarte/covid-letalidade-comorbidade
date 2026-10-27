"""Números que o dashboard mostra, calculados só a partir dos CSVs versionados (sem consultar nada)."""

from dataclasses import dataclass

import pandas as pd

from config import (
    COR_COM_COMORBIDADE,
    COR_PRINCIPAL,
    FAIXA_NEUTRA_PP,
    LIMITE_AMOSTRA_PEQUENA,
    NOMES_COMORBIDADES,
)
from formatacao import fmt_inteiro, fmt_percentual, fmt_pontos


def preparar_agregado(agregado: pd.DataFrame) -> pd.DataFrame:
    """Agregado por comorbidade pronto para a tela, do maior ao menor risco (letalidade com a comorbidade).

    Acrescenta o nome legível, a diferença em pontos percentuais, a razão entre as taxas e se a amostra é pequena.
    """
    df = agregado.copy()
    df["nome"] = df["comorbidade"].map(NOMES_COMORBIDADES)
    df["diferenca_pp"] = (df["taxa_letalidade_com"] - df["taxa_letalidade_sem"]) * 100
    df["razao"] = df["taxa_letalidade_com"] / df["taxa_letalidade_sem"]
    df["amostra_pequena"] = df["casos_com"] < LIMITE_AMOSTRA_PEQUENA
    return df.sort_values("taxa_letalidade_com", ascending=False, kind="stable").reset_index(drop=True)


def classe_da_diferenca(pontos: float) -> str:
    """"alta" (a comorbidade piora), "baixa" (melhora) ou "neutra" (dentro da faixa de FAIXA_NEUTRA_PP, em módulo)."""
    if abs(pontos) < FAIXA_NEUTRA_PP:
        return "neutra"
    return "alta" if pontos > 0 else "baixa"


def totais_do_resumo(resumo: pd.DataFrame) -> dict:
    """Casos, óbitos, desfechos conhecidos, letalidade geral e o período, somando todos os anos do resumo."""
    desfecho = int(resumo["desfecho_conhecido"].sum())
    obitos = int(resumo["obitos"].sum())
    return {
        "casos": int(resumo["casos"].sum()),
        "obitos": obitos,
        "desfecho_conhecido": desfecho,
        "taxa_letalidade": obitos / desfecho if desfecho else float("nan"),
        "primeiro_ano": int(resumo["ano"].min()),
        "ultimo_ano": int(resumo["ano"].max()),
    }


def maior_risco(agregado_preparado: pd.DataFrame) -> pd.Series:
    """Linha da comorbidade com a maior diferença (em p.p.) entre quem tem e quem não tem."""
    return agregado_preparado.loc[agregado_preparado["diferenca_pp"].idxmax()]


@dataclass(frozen=True)
class Kpi:
    rotulo: str
    valor: str
    linha: str
    cor: str | None = None
    ajuda: str | None = None


def kpis_comorbidades(agregado_preparado: pd.DataFrame, resumo: pd.DataFrame) -> list[Kpi]:
    """Os quatro números do topo da página Comorbidades."""
    totais = totais_do_resumo(resumo)
    risco = maior_risco(agregado_preparado)
    periodo = f"{totais['primeiro_ano']}–{totais['ultimo_ano']}"
    return [
        Kpi("Casos com desfecho", fmt_inteiro(totais["desfecho_conhecido"]), f"COVID confirmada, {periodo}"),
        Kpi("Letalidade geral", fmt_percentual(totais["taxa_letalidade"]), "Todos os casos com desfecho",
            cor=COR_PRINCIPAL),
        Kpi("Maior risco", fmt_pontos(risco["diferenca_pp"]),
            f"{risco['nome']}: {fmt_percentual(risco['taxa_letalidade_com'])} contra "
            f"{fmt_percentual(risco['taxa_letalidade_sem'])}",
            cor=COR_COM_COMORBIDADE,
            ajuda="Maior diferença de letalidade entre quem tem e quem não tem a comorbidade"),
        Kpi("Comorbidades analisadas", str(len(agregado_preparado)), "Tabagismo fora: campo vazio na base"),
    ]
