"""Formatação de números no padrão brasileiro."""

import math

import pytest

from formatacao import fmt_decimal, fmt_inteiro, fmt_percentual, fmt_pontos, fmt_razao


@pytest.mark.parametrize(("valor", "esperado"), [(0, "0"), (999, "999"), (78513, "78.513"), (2146582, "2.146.582")])
def test_inteiro_com_ponto_nos_milhares(valor, esperado):
    assert fmt_inteiro(valor) == esperado


def test_decimal_com_virgula_e_ponto_nos_milhares():
    assert fmt_decimal(53.316) == "53,3"
    assert fmt_decimal(1234.5, 2) == "1.234,50"


@pytest.mark.parametrize(("fracao", "esperado"), [(0.5331637, "53,3%"), (0, "0,0%"), (1, "100,0%")])
def test_percentual(fracao, esperado):
    assert fmt_percentual(fracao) == esperado


def test_percentual_ausente_vira_travessao():
    assert fmt_percentual(math.nan) == "—"
    assert fmt_percentual(None) == "—"


@pytest.mark.parametrize(("pontos", "esperado"), [
    (16.36, "+16,4 p.p."), (-11.2, "-11,2 p.p."), (0.0, "0,0 p.p."), (0.04, "0,0 p.p."), (1.3, "+1,3 p.p."),
])
def test_pontos_percentuais_com_sinal(pontos, esperado):
    assert fmt_pontos(pontos) == esperado


def test_razao():
    assert fmt_razao(1.444) == "1,4 vez maior"
    assert fmt_razao(0.7) == "0,7 vez a taxa"
    assert fmt_razao(math.nan) == "—"
