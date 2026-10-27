"""Lê o relatório de qualidade do pipeline para o dashboard avisar sobre dados fora do mapa."""

import json

from config import NOME_RELATORIO, PROCESSED_DIR

CAMINHO_RELATORIO = PROCESSED_DIR / NOME_RELATORIO


def aviso_casos_sem_estado() -> str | None:
    """Texto do aviso de casos sem UF (vazia ou inválida), ou None se não houver o que avisar.

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
    if not aprovado or sem_uf <= 0:
        return None
    numero = f"{sem_uf:,}".replace(",", ".")
    if sem_uf == 1:
        return "1 caso sem estado informado não entra no mapa."
    return f"{numero} casos sem estado informado não entram no mapa."
