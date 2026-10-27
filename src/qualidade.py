"""Lê o relatório de qualidade do pipeline para o dashboard avisar sobre dados fora do mapa."""

import json

from config import NOME_RELATORIO, PROCESSED_DIR
from formatacao import fmt_inteiro

CAMINHO_RELATORIO = PROCESSED_DIR / NOME_RELATORIO


def casos_sem_estado() -> int | None:
    """Casos sem UF (vazia ou inválida) do relatório de qualidade, ou None se ele faltar ou não estiver aprovado.

    Só vale com relatório aprovado: num relatório reprovado os CSVs exibidos são os da versão anterior,
    e o número do relatório não corresponderia a eles.
    """
    try:
        relatorio = json.loads(CAMINHO_RELATORIO.read_text(encoding="utf-8"))
        totais = relatorio["totais"]
        sem_uf = int(totais["sem_uf"]) + int(totais.get("uf_invalida", 0))
        aprovado = relatorio["aprovado"] is True
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return sem_uf if aprovado else None


def aviso_casos_sem_estado() -> str | None:
    """Texto do aviso de casos sem UF, ou None se não houver o que avisar."""
    sem_uf = casos_sem_estado()
    if not sem_uf or sem_uf <= 0:
        return None
    if sem_uf == 1:
        return "1 caso sem estado informado não entra no mapa."
    return f"{fmt_inteiro(sem_uf)} casos sem estado informado não entram no mapa."
