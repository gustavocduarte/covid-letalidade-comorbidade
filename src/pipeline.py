"""Orquestra o pipeline completo (E-T-L) para vários anos do SIVEP-Gripe.

Para cada ano: baixa o CSV bruto (pula o download se ele já estiver em data/raw/) e o converte
em Parquet só com os casos de COVID e as colunas usadas (DuckDB). As tabelas de saída saem de
consultas SQL sobre esses Parquets. Os CSVs brutos ficam salvos permanentemente.
"""

import sys
from datetime import UTC, datetime

from config import (
    NOME_AGREGADO,
    NOME_ESTADO,
    NOME_PARQUET_ANO,
    NOME_RELATORIO,
    NOME_SEMANAL,
    NOME_SEMANAL_COMORBIDADE,
    NOME_SEMANAL_ESTADO,
    NOME_TODOS_ANOS,
    PASTA_DETALHADO,
    PASTA_RAW,
    URLS_SRAG,
)
from consultas import (
    abrir_casos,
    letalidade_por_comorbidade_agregado,
    letalidade_por_comorbidade_por_ano,
    letalidade_por_estado_agregado,
    serie_semanal_casos,
    serie_semanal_por_comorbidade,
    serie_semanal_por_estado,
)
from conversao import csv_para_parquet
from extract import baixar_arquivo
from load import salvar_csv, salvar_json
from validacao import (
    ERRO,
    ErroDeValidacao,
    estatisticas_por_ano,
    montar_relatorio,
    validar_casos,
    validar_saidas,
)

# O ano corrente ainda está em andamento (banco "vivo", atualizado toda semana),
# então seus dados são parciais e não devem ser comparados como se fosse um ano cheio.
ANO_ATUAL = datetime.now(tz=UTC).date().year


def processar_ano(ano: int) -> int:
    """Baixa (se ainda não tiver) o CSV bruto de um ano e o converte em Parquet.

    O CSV bruto fica salvo em data/raw/. Devolve quantos casos de COVID o Parquet do ano guarda.
    """
    url = URLS_SRAG[ano]
    nome_arquivo = url.split("/")[-1]
    caminho_csv = PASTA_RAW / nome_arquivo

    if caminho_csv.exists():
        print(f"[{ano}] CSV já está em disco, pulando download.")
    else:
        print(f"[{ano}] Baixando...")
        caminho_csv = baixar_arquivo(url, PASTA_RAW)

    print(f"[{ano}] Filtrando casos de COVID e gravando o Parquet...")
    casos = csv_para_parquet(caminho_csv, PASTA_DETALHADO / f"ano={ano}" / NOME_PARQUET_ANO)

    tamanho_gb = caminho_csv.stat().st_size / 1e9
    print(f"[{ano}] OK — {casos:,} casos de COVID. CSV bruto ({tamanho_gb:.2f} GB) mantido em {caminho_csv}.")
    return casos


def executar_pipeline() -> None:
    """Roda o ETL completo para todos os anos de URLS_SRAG.

    Calcula todas as tabelas, valida e grava o relatório de qualidade; só grava os CSVs de saída se não
    houver erro de validação (senão levanta ErroDeValidacao e os CSVs anteriores ficam como estavam).
    """
    for ano in sorted(URLS_SRAG):
        processar_ano(ano)

    with abrir_casos(PASTA_DETALHADO, anos=URLS_SRAG) as con:
        estatisticas = estatisticas_por_ano(con)
        por_ano = letalidade_por_comorbidade_por_ano(con)
        por_ano.insert(1, "ano_completo", por_ano["ano"] != ANO_ATUAL)
        agregado = letalidade_por_comorbidade_agregado(con)
        # As séries somam os anos direto, então os dois pedaços de uma semana na virada do ano
        # (sintomas em 30/dez, notificação em jan, arquivo do ano seguinte) saem juntos.
        serie_semanal = serie_semanal_casos(con)
        serie_comorbidade = serie_semanal_por_comorbidade(con)
        serie_estado = serie_semanal_por_estado(con)
        agregado_estado = letalidade_por_estado_agregado(con)

    achados = validar_casos(estatisticas) + validar_saidas(
        estatisticas, por_ano=por_ano, agregado=agregado, estado=agregado_estado,
        serie_semanal=serie_semanal, serie_comorbidade=serie_comorbidade, serie_estado=serie_estado,
    )
    relatorio = montar_relatorio(estatisticas, achados)
    print(f"\nRelatório de qualidade salvo em: {salvar_json(relatorio, NOME_RELATORIO)}")
    for achado in achados:
        print(f"  [{achado.nivel.upper()}] {achado.mensagem}")
    erros = [a for a in achados if a.nivel == ERRO]
    if erros:
        raise ErroDeValidacao(erros)

    caminho = salvar_csv(por_ano, NOME_TODOS_ANOS)
    print(f"\nConsolidado de {len(URLS_SRAG)} anos salvo em: {caminho}")
    print(f"Total de linhas: {len(por_ano)} (deveria ser {len(URLS_SRAG)} anos x 11 comorbidades = {len(URLS_SRAG) * 11})")
    # Agregado: soma óbitos e desfechos conhecidos de todos os anos (2020-2026, incluindo
    # o ano corrente parcial) numa única taxa por comorbidade. É o que o dashboard usa hoje,
    # antes de existir o filtro de ano.
    print(f"Agregado (todos os anos somados) salvo em: {salvar_csv(agregado, NOME_AGREGADO)}")
    print(f"Série semanal ({len(serie_semanal)} semanas) salva em: {salvar_csv(serie_semanal, NOME_SEMANAL)}")
    print(f"Série semanal por comorbidade ({len(serie_comorbidade)} linhas) salva em: "
          f"{salvar_csv(serie_comorbidade, NOME_SEMANAL_COMORBIDADE)}")
    print(f"Série semanal por estado ({len(serie_estado)} linhas) salva em: "
          f"{salvar_csv(serie_estado, NOME_SEMANAL_ESTADO)}")
    print(f"Letalidade por estado (todos os anos somados, {len(agregado_estado)} estados) salva em: "
          f"{salvar_csv(agregado_estado, NOME_ESTADO)}")
    print(f"\nCasos de COVID por ano (Parquet, uso futuro, sem precisar rebaixar) em: {PASTA_DETALHADO}")


if __name__ == "__main__":
    try:
        executar_pipeline()
    except ErroDeValidacao as erro:
        print(f"\nValidação falhou, nenhum CSV de saída foi gravado:\n{erro}", file=sys.stderr)
        sys.exit(1)
