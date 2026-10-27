"""Formatação de números no padrão brasileiro (ponto nos milhares, vírgula nos decimais)."""

import math


def _trocar_separadores(texto: str) -> str:
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def fmt_inteiro(valor: float) -> str:
    """78513 -> "78.513"."""
    return _trocar_separadores(f"{round(valor):,}")


def fmt_decimal(valor: float, casas: int = 1) -> str:
    """53.316 -> "53,3"."""
    return _trocar_separadores(f"{valor:,.{casas}f}")


def fmt_percentual(fracao: float, casas: int = 1) -> str:
    """0.5332 -> "53,3%"; valor ausente vira "—"."""
    if fracao is None or math.isnan(fracao):
        return "—"
    return f"{fmt_decimal(fracao * 100, casas)}%"


def fmt_pontos(pontos: float, casas: int = 1) -> str:
    """Diferença em pontos percentuais, com sinal: 16.36 -> "+16,4 p.p."; -11.2 -> "-11,2 p.p."; 0 -> "0,0 p.p."."""
    texto = fmt_decimal(pontos, casas)
    if pontos > 0 and not texto.startswith("0,0"):
        texto = "+" + texto
    return f"{texto} p.p."


def fmt_razao(razao: float) -> str:
    """1.444 -> "1,4 vez maior"; abaixo de 1 -> "0,7 vez a taxa"; ausente vira "—"."""
    if razao is None or math.isnan(razao):
        return "—"
    return f"{fmt_decimal(razao, 1)} vez maior" if razao >= 1 else f"{fmt_decimal(razao, 1)} vez a taxa"
