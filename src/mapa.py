"""Apoio ao mapa por estado: cores dos rótulos, centro dos estados e orientação dos anéis do GeoJSON."""

from itertools import pairwise


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

    O claro vale até o escuro ter 2,5 vezes o contraste (WCAG) dele: em fundos de tom médio, texto pequeno claro
    lê melhor que o escuro, mesmo com contraste calculado um pouco menor."""
    posicao = 0.5 if maximo == minimo else (valor - minimo) / (maximo - minimo)
    fundo = luminancia_relativa(cor_na_escala(posicao, escala))

    def contraste(cor: str) -> float:
        luz = luminancia_relativa(_hex_para_rgb(cor))
        return (max(fundo, luz) + 0.05) / (min(fundo, luz) + 0.05)

    return claro if contraste(claro) * 2.5 >= contraste(escuro) else escuro


def _area_e_centroide_anel(anel: list[list[float]]) -> tuple[float, tuple[float, float]]:
    """Área (com sinal) e centroide de um anel de polígono, pela fórmula padrão de
    centroide de polígono — só soma/multiplicação, sem nenhuma biblioteca geoespacial
    (evitamos shapely/geopandas de propósito, essa máquina tem pouca memória livre)."""
    area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(anel)
    for i in range(n - 1):  # o último ponto do anel repete o primeiro, no padrão GeoJSON
        x0, y0 = anel[i]
        x1, y1 = anel[i + 1]
        cruz = x0 * y1 - x1 * y0
        area += cruz
        cx += (x0 + x1) * cruz
        cy += (y0 + y1) * cruz
    area /= 2.0
    if area == 0:
        xs = [p[0] for p in anel]
        ys = [p[1] for p in anel]
        return 0.0, (sum(xs) / len(xs), sum(ys) / len(ys))
    cx /= 6 * area
    cy /= 6 * area
    return abs(area), (cx, cy)


def centro_aproximado(geometria: dict) -> tuple[float, float]:
    """Centro aproximado (lon, lat) de um Polygon/MultiPolygon: usa o maior anel externo,
    pra ilhas distantes (ex: Fernando de Noronha, em Pernambuco) não puxarem o centro
    do rótulo pra longe do corpo principal do estado."""
    if geometria["type"] == "Polygon":
        aneis = [geometria["coordinates"][0]]
    else:
        aneis = [poligono[0] for poligono in geometria["coordinates"]]

    maior_area = -1.0
    melhor_centro = None
    for anel in aneis:
        area, centro = _area_e_centroide_anel(anel)
        if area > maior_area:
            maior_area = area
            melhor_centro = centro
    return melhor_centro


def _area_assinada(anel: list[list[float]]) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in pairwise(anel)) / 2


def _orientar_poligono(aneis: list[list[list[float]]]) -> list[list[list[float]]]:
    """Anel externo no sentido horário e buracos no anti-horário, que é a convenção do d3-geo (usado pelo Plotly)."""
    return [
        anel if (_area_assinada(anel) < 0) == (i == 0) else anel[::-1]
        for i, anel in enumerate(aneis)
    ]


def geojson_para_plotly(geojson: dict) -> dict:
    """Cópia do GeoJSON com os anéis na orientação que o `go.Choropleth` espera.

    O GeoJSON padrão (RFC 7946) traz o anel externo anti-horário; no d3-geo isso significa "todo o globo menos o
    polígono", e cada estado sai como um retângulo cobrindo o mapa.
    """
    estados = []
    for feature in geojson["features"]:
        geometria = feature["geometry"]
        poligonos = [geometria["coordinates"]] if geometria["type"] == "Polygon" else geometria["coordinates"]
        orientados = [_orientar_poligono(p) for p in poligonos]
        coordenadas = orientados[0] if geometria["type"] == "Polygon" else orientados
        estados.append({**feature, "geometry": {**geometria, "coordinates": coordenadas}})
    return {**geojson, "features": estados}
