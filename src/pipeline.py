"""Orquestra o pipeline completo (E-T-L) para vários anos do SIVEP-Gripe.

Para cada ano: baixa o CSV bruto (pula o download se ele já estiver em data/raw/) e o converte
em Parquet só com os casos de COVID e as colunas usadas (DuckDB). As tabelas de saída saem de
consultas SQL sobre esses Parquets. Os CSVs brutos ficam salvos permanentemente.
"""

import sys
from collections.abc import Iterable
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
from estado import ano_em_dia, assinatura_csv, gravar_estado, ler_estado, registro_do_ano
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
        print(f"[{ano}] Baixando...")
        caminho_csv = baixar_arquivo(url, PASTA_RAW)
    else:
        registro = registros.get(str(ano))
        if not forcar and ano_em_dia(registro, assinatura_csv(caminho_csv, url), caminho_parquet):
            print(f"[{ano}] Em dia — {registro['casos']:,} casos de COVID no Parquet, nada a fazer.")
            return EM_DIA
        print(f"[{ano}] CSV já está em disco, pulando download.")

    print(f"[{ano}] Filtrando casos de COVID e gravando o Parquet...")
    casos = csv_para_parquet(caminho_csv, caminho_parquet)
    registros[str(ano)] = registro_do_ano(assinatura_csv(caminho_csv, url), casos)
    gravar_estado(PASTA_DETALHADO, registros)

    tamanho_gb = caminho_csv.stat().st_size / 1e9
    print(f"[{ano}] OK — {casos:,} casos de COVID. CSV bruto ({tamanho_gb:.2f} GB) mantido em {caminho_csv}.")
    return BAIXADO if baixar else CONVERTIDO


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

    faltando = [a for a in sorted(URLS_SRAG) if not (PASTA_DETALHADO / f"ano={a}" / NOME_PARQUET_ANO).exists()]
    if faltando:
        raise ParquetsFaltando(faltando)

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
    return status


if __name__ == "__main__":
    try:
        executar_pipeline()
    except ErroDeValidacao as erro:
        print(f"\nValidação falhou, nenhum CSV de saída foi gravado:\n{erro}", file=sys.stderr)
        sys.exit(1)
