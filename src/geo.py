"""Baixa o contorno geográfico dos 27 estados brasileiros da API oficial do IBGE
e monta um único GeoJSON local, conferindo a sigla de cada estado contra a lista
oficial do IBGE antes de salvar (evita erro de digitação/troca acidental)."""

import json
import logging
from pathlib import Path

import requests

from config import CAMINHO_GEOJSON, URL_LOCALIDADES, URL_MALHA

logger = logging.getLogger(__name__)


def obter_estados_oficiais() -> dict[str, dict]:
    """Busca a lista oficial de estados do IBGE: sigla -> {codigo, nome}."""
    resposta = requests.get(URL_LOCALIDADES, timeout=30)
    resposta.raise_for_status()
    estados = resposta.json()
    return {estado["sigla"]: {"codigo": estado["id"], "nome": estado["nome"]} for estado in estados}


def baixar_contorno_estado(sigla: str) -> dict:
    """Baixa o GeoJSON do contorno de um único estado."""
    resposta = requests.get(URL_MALHA.format(sigla=sigla), timeout=30)
    resposta.raise_for_status()
    return resposta.json()


def montar_geojson_brasil() -> dict:
    """Baixa os 27 estados e junta num FeatureCollection só, verificando cada um."""
    estados_oficiais = obter_estados_oficiais()
    if len(estados_oficiais) != 27:
        raise ValueError(f"Esperava 27 estados na lista oficial do IBGE, vieram {len(estados_oficiais)}.")

    features = []
    for sigla, info in sorted(estados_oficiais.items()):
        logger.info("Baixando contorno de %s...", sigla)
        geojson_estado = baixar_contorno_estado(sigla)

        for feature in geojson_estado["features"]:
            # A API de malhas devolve o código numérico (codarea), não a sigla.
            # Conferimos aqui que ele bate com o código oficial daquela sigla
            # antes de anexar sigla/nome à feature — se não bater, para tudo em
            # vez de salvar um mapa com estado errado silenciosamente.
            codigo_retornado = int(feature["properties"]["codarea"])
            if codigo_retornado != info["codigo"]:
                raise ValueError(
                    f"Divergência para {sigla}: a API de malhas devolveu codarea={codigo_retornado}, "
                    f"mas o código oficial do IBGE para {sigla} é {info['codigo']}."
                )
            feature["properties"]["sigla"] = sigla
            feature["properties"]["nome"] = info["nome"]
            features.append(feature)

    logger.info("Verificação OK: as %d siglas batem com os códigos oficiais do IBGE.", len(features))
    return {"type": "FeatureCollection", "features": features}


def baixar_geojson(destino: Path | None = None) -> Path:
    """Monta o GeoJSON do Brasil e o salva (por padrão em data/geo/); devolve o caminho."""
    destino = CAMINHO_GEOJSON if destino is None else destino
    geojson_brasil = montar_geojson_brasil()

    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as arquivo:
        json.dump(geojson_brasil, arquivo, ensure_ascii=False)
    logger.info("Salvo em: %s", destino)
    return destino
