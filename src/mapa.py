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


def siglas_com_rotulo(
    geojson: dict,
    zoom: float,
    textos: dict[str, str],
    centros: dict[str, tuple[float, float]],
    fonte_px: int = 8,
    aproveitamento: float = 0.6,
) -> set[str]:
    """Siglas dos estados cujo texto cabe no estado e não encosta no texto de outro, no zoom dado.

    Mede em pixels a caixa de cada estado (descontando o que ela tem de vazio, `aproveitamento`) e o retângulo do
    texto no `centro` (lon, lat) do estado; os maiores estados escolhem primeiro. A largura de um caractere é
    estimada em 0,6 da fonte. Quem fica de fora mostra o valor só ao passar o mouse.
    """
    mundo = TILE_PX * 2**zoom
    candidatos = []
    for feature in geojson["features"]:
        sigla = feature["properties"]["sigla"]
        lon_min, lon_max, lat_min, lat_max = limites_do_geojson({"features": [feature]})
        largura = math.radians(lon_max - lon_min) * mundo / (2 * math.pi) * aproveitamento
        altura = (_y_mercator(lat_max) - _y_mercator(lat_min)) * mundo / (2 * math.pi) * aproveitamento
        largura_texto, altura_texto = len(textos[sigla]) * 0.6 * fonte_px, fonte_px * 1.2
        if largura >= largura_texto + 4 and altura >= altura_texto + 4:
            lon, lat = centros[sigla]
            x = math.radians(lon) * mundo / (2 * math.pi)
            y = -_y_mercator(lat) * mundo / (2 * math.pi)
            candidatos.append((largura * altura, sigla, (x, y, largura_texto, altura_texto)))

    colocados: list[tuple[float, float, float, float]] = []
    escolhidos = set()
    for _, sigla, (x, y, largura_texto, altura_texto) in sorted(candidatos, reverse=True):
        encosta = any(
            abs(x - x2) < (largura_texto + l2) / 2 + 3 and abs(y - y2) < (altura_texto + a2) / 2 + 3
            for x2, y2, l2, a2 in colocados
        )
        if not encosta:
            colocados.append((x, y, largura_texto, altura_texto))
            escolhidos.add(sigla)
    return escolhidos


def _hex_para_rgb(cor: str) -> tuple[float, float, float]:
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


def cor_na_escala(posicao: float, escala: tuple[str, ...] | list[str]) -> tuple[float, float, float]:
    """RGB no ponto `posicao` (0 a 1) de uma escala de cores equidistantes, interpolando entre as vizinhas."""
    ponto = min(max(posicao, 0.0), 1.0) * (len(escala) - 1)
    inferior = min(int(ponto), len(escala) - 2)
    fracao = ponto - inferior
    c0, c1 = _hex_para_rgb(escala[inferior]), _hex_para_rgb(escala[inferior + 1])
    return tuple(a + fracao * (b - a) for a, b in zip(c0, c1, strict=True))


def luminancia_relativa(rgb: tuple[float, float, float]) -> float:
    """Luminância relativa (WCAG) de uma cor RGB 0-255."""

    def canal(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def cor_texto_contraste(
    valor: float, minimo: float, maximo: float, escala: tuple[str, ...], claro: str, escuro: str,
) -> str:
    """`claro` ou `escuro` para o texto sobre a cor da escala naquele valor.

    O claro vale até o escuro ter 1,6 vez o contraste (WCAG) dele: em fundos de tom médio, texto pequeno claro
    lê melhor que o escuro, mesmo com contraste calculado um pouco menor."""
    posicao = 0.5 if maximo == minimo else (valor - minimo) / (maximo - minimo)
    fundo = luminancia_relativa(cor_na_escala(posicao, escala))

    def contraste(cor: str) -> float:
        luz = luminancia_relativa(_hex_para_rgb(cor))
        return (max(fundo, luz) + 0.05) / (min(fundo, luz) + 0.05)

    return claro if contraste(claro) * 1.6 >= contraste(escuro) else escuro
