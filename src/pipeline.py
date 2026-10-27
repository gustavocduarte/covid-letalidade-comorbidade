"""Orquestra o pipeline completo (E-T-L) para vários anos do SIVEP-Gripe.

Para cada ano: baixa o CSV bruto (pula o download se ele já estiver em data/raw/) e o converte
em Parquet só com os casos de COVID e as colunas usadas (DuckDB). As tabelas de saída saem de
consultas SQL sobre esses Parquets. Os CSVs brutos ficam salvos permanentemente.
"""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from config import (
    NOME_AGREGADO,
    NOME_ESTADO,
    NOME_PARQUET_ANO,
    NOME_RELATORIO,
    NOME_RESUMO_GERAL,
    NOME_SEMANAL,
    NOME_SEMANAL_COMORBIDADE,
    NOME_SEMANAL_ESTADO,
    NOME_TODOS_ANOS,
    PASTA_DETALHADO,
    PASTA_RAW,
    PROCESSED_DIR,
    URLS_SRAG,
)
from consultas import (
    abrir_casos,
    letalidade_por_comorbidade_agregado,
    letalidade_por_comorbidade_por_ano,
    letalidade_por_estado_agregado,
    resumo_geral_por_ano,
    serie_semanal_casos,
    serie_semanal_por_comorbidade,
    serie_semanal_por_estado,
)
from conversao import csv_para_parquet
from estado import ano_em_dia, assinatura_csv, gravar_estado, ler_estado, registro_do_ano
from extract import baixar_arquivo
from load import publicar_csvs, salvar_csv, salvar_json
from validacao import (
    ERRO,
    ErroDeValidacao,
    estatisticas_por_ano,
    montar_relatorio,
    validar_casos,
    validar_saidas,
)

logger = logging.getLogger(__name__)

# O ano corrente ainda está em andamento (banco "vivo", atualizado toda semana),
# então seus dados são parciais e não devem ser comparados como se fosse um ano cheio.
ANO_ATUAL = datetime.now(tz=UTC).date().year

# Resultado de processar_ano.
BAIXADO, CONVERTIDO, EM_DIA = "baixado", "convertido", "em_dia"


def processar_ano(ano: int, *, forcar: bool = False, rebaixar: bool = False) -> str:
    """Baixa (se preciso) o CSV bruto de um ano e o converte em Parquet (se preciso).

    O CSV só é baixado se não existir em data/raw/ (ou com `rebaixar`). A conversão é pulada quando o
    Parquet já veio deste mesmo CSV, na versão atual da conversão (ou refeita com `forcar`).
    Devolve BAIXADO (baixou e converteu), CONVERTIDO (só converteu) ou EM_DIA (nada a fazer).
    """
    url = URLS_SRAG[ano]
    nome_arquivo = url.split("/")[-1]
    caminho_csv = PASTA_RAW / nome_arquivo
    caminho_parquet = PASTA_DETALHADO / f"ano={ano}" / NOME_PARQUET_ANO
    registros = ler_estado(PASTA_DETALHADO)

    baixar = rebaixar or not caminho_csv.exists()
    if baixar:
        logger.info(f"[{ano}] Baixando...")
        caminho_csv = baixar_arquivo(url, PASTA_RAW)
    else:
        registro = registros.get(str(ano))
        if not forcar and ano_em_dia(registro, assinatura_csv(caminho_csv, url), caminho_parquet):
            logger.info(f"[{ano}] Em dia — {registro['casos']:,} casos de COVID no Parquet, nada a fazer.")
            return EM_DIA
        logger.info(f"[{ano}] CSV já está em disco, pulando download.")

    logger.info(f"[{ano}] Filtrando casos de COVID e gravando o Parquet...")
    casos = csv_para_parquet(caminho_csv, caminho_parquet)
    registros[str(ano)] = registro_do_ano(assinatura_csv(caminho_csv, url), casos)
    gravar_estado(PASTA_DETALHADO, registros)

    tamanho_gb = caminho_csv.stat().st_size / 1e9
    logger.info(f"[{ano}] OK — {casos:,} casos de COVID. CSV bruto ({tamanho_gb:.2f} GB) mantido em {caminho_csv}.")
    return BAIXADO if baixar else CONVERTIDO


def _anos_sem_parquet() -> list[int]:
    return [a for a in sorted(URLS_SRAG) if not (PASTA_DETALHADO / f"ano={a}" / NOME_PARQUET_ANO).exists()]


class ParquetsFaltando(Exception):
    """Falta o Parquet de algum ano: os CSVs de saída não podem ser calculados sem ele."""

    def __init__(self, anos: list[int]):
        self.anos = anos
        lista = " ".join(str(a) for a in anos)
        super().__init__(
            f"Faltam os Parquets dos anos: {lista}. Para gerá-los, rode: python src/cli.py pipeline --anos {lista}"
        )


def executar_pipeline(
    anos: Iterable[int] | None = None, *, forcar: bool = False, rebaixar: bool = False
) -> dict[int, str]:
    """Roda o ETL: atualiza os anos pedidos (todos, por padrão) e recalcula as saídas de todos os anos.

    Calcula todas as tabelas, valida e grava o relatório de qualidade; só grava os CSVs de saída se não
    houver erro de validação (senão levanta ErroDeValidacao e os CSVs anteriores ficam como estavam).
    Se faltar o Parquet de algum ano de URLS_SRAG, levanta ParquetsFaltando antes de gravar qualquer coisa.
    Devolve o status de cada ano processado (ver processar_ano).
    """
    escolhidos = sorted(URLS_SRAG if anos is None else set(anos))
    desconhecidos = [a for a in escolhidos if a not in URLS_SRAG]
    if desconhecidos:
        raise ValueError(f"Anos sem URL em URLS_SRAG: {desconhecidos}")
    status = {ano: processar_ano(ano, forcar=forcar, rebaixar=rebaixar) for ano in escolhidos}

    faltando = _anos_sem_parquet()
    if faltando:
        raise ParquetsFaltando(faltando)

    with abrir_casos(PASTA_DETALHADO, anos=URLS_SRAG) as con:
        estatisticas = estatisticas_por_ano(con)
        por_ano = letalidade_por_comorbidade_por_ano(con)
        por_ano.insert(1, "ano_completo", por_ano["ano"] != ANO_ATUAL)
        agregado = letalidade_por_comorbidade_agregado(con)
        resumo = resumo_geral_por_ano(con)
        resumo.insert(1, "ano_completo", resumo["ano"] != ANO_ATUAL)
        # As séries somam os anos direto, então os dois pedaços de uma semana na virada do ano
        # (sintomas em 30/dez, notificação em jan, arquivo do ano seguinte) saem juntos.
        serie_semanal = serie_semanal_casos(con)
        serie_comorbidade = serie_semanal_por_comorbidade(con)
        serie_estado = serie_semanal_por_estado(con)
        agregado_estado = letalidade_por_estado_agregado(con)

    achados = validar_casos(estatisticas) + validar_saidas(
        estatisticas, por_ano=por_ano, agregado=agregado, estado=agregado_estado,
        serie_semanal=serie_semanal, serie_comorbidade=serie_comorbidade, serie_estado=serie_estado, resumo=resumo,
    )
    relatorio = montar_relatorio(estatisticas, achados)
    for achado in achados:
        logger.info(f"  [{achado.nivel.upper()}] {achado.mensagem}")
    erros = [a for a in achados if a.nivel == ERRO]
    if erros:
        # Reprovado: o relatório é o único arquivo gravado; os CSVs anteriores ficam como estavam.
        logger.info(f"\nRelatório de qualidade salvo em: {salvar_json(relatorio, NOME_RELATORIO)}")
        raise ErroDeValidacao(erros)

    # Aprovado: os CSVs são publicados juntos (temporários + troca no fim) e o relatório, que o dashboard lê para
    # saber que os CSVs estão aprovados, é o último arquivo a ser gravado.
    publicar_csvs({
        NOME_TODOS_ANOS: por_ano, NOME_AGREGADO: agregado, NOME_SEMANAL: serie_semanal,
        NOME_SEMANAL_COMORBIDADE: serie_comorbidade, NOME_SEMANAL_ESTADO: serie_estado, NOME_RESUMO_GERAL: resumo,
        NOME_ESTADO: agregado_estado,
    })
    logger.info(f"\nConsolidado de {len(URLS_SRAG)} anos salvo em: {PROCESSED_DIR / NOME_TODOS_ANOS}")
    logger.info(f"Total de linhas: {len(por_ano)} (deveria ser {len(URLS_SRAG)} anos x 11 comorbidades = {len(URLS_SRAG) * 11})")
    # Agregado: soma óbitos e desfechos conhecidos de todos os anos (2020-2026, incluindo
    # o ano corrente parcial) numa única taxa por comorbidade.
    logger.info(f"Agregado (todos os anos somados) salvo em: {PROCESSED_DIR / NOME_AGREGADO}")
    logger.info(f"Série semanal ({len(serie_semanal)} semanas) salva em: {PROCESSED_DIR / NOME_SEMANAL}")
    logger.info(f"Série semanal por comorbidade ({len(serie_comorbidade)} linhas) salva em: "
                f"{PROCESSED_DIR / NOME_SEMANAL_COMORBIDADE}")
    logger.info(f"Série semanal por estado ({len(serie_estado)} linhas) salva em: {PROCESSED_DIR / NOME_SEMANAL_ESTADO}")
    logger.info(f"Resumo geral por ano salvo em: {PROCESSED_DIR / NOME_RESUMO_GERAL}")
    logger.info(f"Letalidade por estado (todos os anos somados, {len(agregado_estado)} estados) salva em: "
                f"{PROCESSED_DIR / NOME_ESTADO}")
    logger.info(f"\nRelatório de qualidade salvo em: {salvar_json(relatorio, NOME_RELATORIO)}")
    logger.info(f"\nCasos de COVID por ano (Parquet, uso futuro, sem precisar rebaixar) em: {PASTA_DETALHADO}")
    return status


def gerar_serie_estado() -> Path:
    """Regera só a série semanal de casos por estado a partir dos Parquets, sem baixar nem converter."""
    faltando = _anos_sem_parquet()
    if faltando:
        raise ParquetsFaltando(faltando)
    with abrir_casos(PASTA_DETALHADO, anos=URLS_SRAG) as con:
        serie = serie_semanal_por_estado(con)
    caminho = salvar_csv(serie, NOME_SEMANAL_ESTADO)
    logger.info(f"Série semanal por estado ({len(serie)} linhas) salva em: {caminho}")
    return caminho
