"""Números que o dashboard mostra, calculados só a partir dos CSVs versionados (sem consultar nada)."""

from dataclasses import dataclass

import pandas as pd

from config import (
    COR_COM_COMORBIDADE,
    COR_POSITIVO,
    COR_PRINCIPAL,
    COR_TEXTO_SECUNDARIO,
    FAIXA_NEUTRA_PP,
    LIMITE_AMOSTRA_PEQUENA,
    NOMES_COMORBIDADES,
)
from formatacao import fmt_decimal, fmt_inteiro, fmt_percentual, fmt_pontos, fmt_razao

COR_DA_CLASSE = {"alta": COR_COM_COMORBIDADE, "neutra": COR_TEXTO_SECUNDARIO, "baixa": COR_POSITIVO}


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


def celulas_da_comorbidade(linha: pd.Series) -> list[Kpi]:
    """As três células da comorbidade escolhida: letalidade com, sem e a diferença entre as duas."""
    pontos = linha["diferenca_pp"]
    return [
        Kpi("Com a comorbidade", fmt_percentual(linha["taxa_letalidade_com"]), f"{fmt_inteiro(linha['casos_com'])} casos",
            cor=COR_COM_COMORBIDADE),
        Kpi("Sem a comorbidade", fmt_percentual(linha["taxa_letalidade_sem"]), f"{fmt_inteiro(linha['casos_sem'])} casos"),
        Kpi("Diferença", fmt_pontos(pontos), fmt_razao(linha["razao"]), cor=COR_DA_CLASSE[classe_da_diferenca(pontos)]),
    ]


@dataclass(frozen=True)
class Achado:
    """Um cartão de "Principais achados": `destaque` em negrito no começo, `texto` em seguida."""

    destaque: str
    texto: str
    atencao: bool = False


TEXTO_ATENCAO = (
    "o grupo \"sem\" não é de pessoas saudáveis, só de pessoas sem aquela condição, e muitos pacientes têm mais de uma "
    "comorbidade. As taxas não isolam o efeito de cada uma."
)


def juntar_nomes(nomes: list[str]) -> str:
    """["A", "B", "C"] -> "A, B e C"."""
    if len(nomes) <= 1:
        return "".join(nomes)
    return ", ".join(nomes[:-1]) + " e " + nomes[-1]


def _com_aviso_de_amostra(linha: pd.Series) -> str:
    return linha["nome"] + (" (amostra pequena)" if linha["amostra_pequena"] else "")


def achados_comorbidades(agregado_preparado: pd.DataFrame) -> list[Achado]:
    """Os cartões da página, escritos a partir dos números: o mais letal, quem fica abaixo ou perto de quem não tem e o aviso.

    Só descreve o que os dados mostram; a idade, por exemplo, não está na base, então só aparece como possibilidade.
    """
    df = agregado_preparado
    primeiro = df.iloc[0]
    seguintes = juntar_nomes(df["nome"].iloc[1:3].tolist())
    cartoes = [Achado(
        primeiro["nome"],
        f" tem a maior letalidade: {fmt_percentual(primeiro['taxa_letalidade_com'], 0)} contra "
        f"{fmt_percentual(primeiro['taxa_letalidade_sem'], 0)} de quem não tem ({fmt_razao(primeiro['razao'])}). "
        f"{seguintes} vêm logo atrás.",
    )]

    classes = df["diferenca_pp"].map(classe_da_diferenca)
    abaixo, perto = df[classes == "baixa"], df[classes == "neutra"]
    if len(abaixo):
        nomes = juntar_nomes([_com_aviso_de_amostra(linha) for _, linha in abaixo.iterrows()])
        texto = " aparece com letalidade menor que a de quem não tem a condição" if len(abaixo) == 1 else (
            " aparecem com letalidade menor que a de quem não tem a condição")
        texto += ". Isso pode refletir diferenças entre os grupos que estes dados não medem, como a idade (que não consta da base); não indica proteção."
        if len(perto):
            texto += (f" {juntar_nomes([_com_aviso_de_amostra(linha) for _, linha in perto.iterrows()])} "
                      f"ficam perto da taxa de quem não tem (diferença menor que {fmt_decimal(FAIXA_NEUTRA_PP, 0)} p.p.).")
        cartoes.append(Achado(nomes, texto))
    cartoes.append(Achado("Atenção:", " " + TEXTO_ATENCAO, atencao=True))
    return cartoes
