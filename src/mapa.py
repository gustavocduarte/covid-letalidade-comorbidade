"""Enquadramento do mapa por estado: centro e zoom que acomodam o Brasil no quadro do gráfico."""

import math

# O MapLibre usa tiles de 512 px: o mundo todo tem 512 * 2**zoom px de largura (projeção Mercator).
TILE_PX = 512


def limites_do_geojson(geojson: dict) -> tuple[float, float, float, float]:
    """(lon_min, lon_max, lat_min, lat_max) de todos os anéis das geometrias do GeoJSON."""
    longitudes, latitudes = [], []

    def percorrer(coordenadas) -> None:
        if coordenadas and isinstance(coordenadas[0], (int, float)):
            longitudes.append(coordenadas[0])
            latitudes.append(coordenadas[1])
        else:
            for filho in coordenadas:
                percorrer(filho)

    for feature in geojson["features"]:
        percorrer(feature["geometry"]["coordinates"])
    return min(longitudes), max(longitudes), min(latitudes), max(latitudes)


def _y_mercator(latitude: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2))


def enquadramento(
    limites: tuple[float, float, float, float], largura_px: int, altura_px: int, folga: float = 0.94,
) -> tuple[dict[str, float], float]:
    """Centro `{"lat", "lon"}` e zoom em que os limites cabem no quadro, com uma folga nas bordas.

    O zoom é o do eixo mais apertado: a largura de uma área larga demais para o quadro manda, senão a altura.
    """
    lon_min, lon_max, lat_min, lat_max = limites
    y_min, y_max = _y_mercator(lat_min), _y_mercator(lat_max)
    escala_largura = largura_px * folga * 2 * math.pi / (TILE_PX * math.radians(lon_max - lon_min))
    escala_altura = altura_px * folga * 2 * math.pi / (TILE_PX * (y_max - y_min))
    zoom = math.log2(min(escala_largura, escala_altura))
    y_centro = (y_min + y_max) / 2
    lat_centro = math.degrees(2 * math.atan(math.exp(y_centro)) - math.pi / 2)
    return {"lat": lat_centro, "lon": (lon_min + lon_max) / 2}, zoom
