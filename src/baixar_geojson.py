"""Baixa o contorno geográfico dos 27 estados brasileiros da API oficial do IBGE
e monta um único GeoJSON local, conferindo a sigla de cada estado contra a lista
oficial do IBGE antes de salvar (evita erro de digitação/troca acidental)."""

import json
from pathlib import Path

import requests

PASTA_GEO = Path(__file__).resolve().parent.parent / "data" / "geo"
CAMINHO_SAIDA = PASTA_GEO / "brasil_estados.geojson"

URL_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
URL_MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{sigla}?formato=application/vnd.geo+json"


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
        print(f"Baixando contorno de {sigla}...")
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

    print(f"Verificação OK: as {len(features)} siglas batem com os códigos oficiais do IBGE.")
    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    geojson_brasil = montar_geojson_brasil()

    PASTA_GEO.mkdir(parents=True, exist_ok=True)
    with open(CAMINHO_SAIDA, "w", encoding="utf-8") as arquivo:
        json.dump(geojson_brasil, arquivo, ensure_ascii=False)
    print(f"Salvo em: {CAMINHO_SAIDA}")
