"""Linha de comando do projeto: contorno dos estados, pipeline de dados e série por estado.

    python src/cli.py geo
    python src/cli.py pipeline [--anos 2020 2022-2024] [--forcar] [--rebaixar]
    python src/cli.py serie-estado
    python src/cli.py tudo [--anos ...] [--forcar] [--rebaixar]

Código de saída: 0 ok, 1 validação reprovou, 2 uso incorreto, 3 faltam Parquets de anos não processados.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

import geo
import pipeline
from config import CAMINHO_GEOJSON, URLS_SRAG
from validacao import ErroDeValidacao

SAIDA_OK, SAIDA_VALIDACAO, SAIDA_USO, SAIDA_PARQUETS_FALTANDO = 0, 1, 2, 3


def interpretar_anos(tokens: Sequence[str]) -> list[int]:
    """Converte "2020 2022-2024" em [2020, 2022, 2023, 2024]; ano sem URL em URLS_SRAG é erro de uso."""
    anos = set()
    for token in tokens:
        inicio, separador, fim = token.partition("-")
        try:
            primeiro, ultimo = int(inicio), int(fim if separador else inicio)
        except ValueError:
            raise argparse.ArgumentTypeError(f"ano inválido: {token!r} (use 2024 ou 2022-2024)") from None
        anos.update(range(primeiro, ultimo + 1))
    desconhecidos = sorted(anos - URLS_SRAG.keys())
    if desconhecidos:
        validos = ", ".join(str(a) for a in sorted(URLS_SRAG))
        raise argparse.ArgumentTypeError(f"anos sem arquivo conhecido: {desconhecidos}. Anos válidos: {validos}")
    return sorted(anos)


def _opcoes_do_pipeline(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--anos", nargs="+", metavar="ANO", help="anos a baixar/converter, ex.: 2024 ou 2022-2024 "
                        "(padrão: todos; as saídas sempre cobrem todos os anos)")
    parser.add_argument("--forcar", action="store_true", help="reconverte os anos escolhidos, mesmo em dia")
    parser.add_argument("--rebaixar", action="store_true", help="baixa de novo o CSV bruto dos anos escolhidos")


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.py", description=__doc__.split("\n\n")[0])
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    subcomandos.add_parser("geo", help="baixa o contorno dos 27 estados (IBGE)")
    _opcoes_do_pipeline(subcomandos.add_parser("pipeline", help="baixa, converte, valida e grava as saídas"))
    subcomandos.add_parser("serie-estado", help="regera só a série semanal por estado a partir dos Parquets")
    _opcoes_do_pipeline(subcomandos.add_parser("tudo", help="geo (se faltar o GeoJSON) e depois pipeline"))
    return parser


def _executar_pipeline(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        anos = interpretar_anos(args.anos) if args.anos else None
    except argparse.ArgumentTypeError as erro:
        parser.error(str(erro))
    pipeline.executar_pipeline(anos, forcar=args.forcar, rebaixar=args.rebaixar)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    parser = montar_parser()
    args = parser.parse_args(argv)  # uso incorreto sai com código 2
    try:
        if args.comando == "geo":
            geo.baixar_geojson()
        elif args.comando == "pipeline":
            _executar_pipeline(args, parser)
        elif args.comando == "serie-estado":
            pipeline.gerar_serie_estado()
        elif args.comando == "tudo":
            if CAMINHO_GEOJSON.exists():
                logging.getLogger(__name__).info("GeoJSON já existe em %s, pulando.", CAMINHO_GEOJSON)
            else:
                geo.baixar_geojson()
            _executar_pipeline(args, parser)
    except ErroDeValidacao as erro:
        print(f"\nValidação falhou, nenhum CSV de saída foi gravado:\n{erro}", file=sys.stderr)
        return SAIDA_VALIDACAO
    except pipeline.ParquetsFaltando as erro:
        print(f"\n{erro}", file=sys.stderr)
        return SAIDA_PARQUETS_FALTANDO
    return SAIDA_OK


if __name__ == "__main__":
    sys.exit(main())
