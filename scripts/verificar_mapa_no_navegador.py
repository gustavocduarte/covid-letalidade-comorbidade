"""Verificação manual do mapa de estados no navegador: abre a página, estreita e alarga a janela e fotografa o
painel dos estados a cada passo, para conferir que o mapa continua inteiro e centralizado.

Não roda no CI nem no pytest: exige o dashboard no ar, o Chrome instalado e o Playwright (que não está nas
dependências do projeto; instale à parte, por exemplo `pip install playwright` num ambiente virtual temporário).

Uso:
    streamlit run src/dashboard.py --server.port 8511
    python scripts/verificar_mapa_no_navegador.py http://localhost:8511/tempo-e-estados PASTA_DE_SAIDA PREFIXO
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

LARGO, ESTREITO, ALTURA = 1500, 900, 900
PAINEL = ".st-key-painel_estados"


def _esperar_mapa(pagina):
    pagina.wait_for_selector(f"{PAINEL} .js-plotly-plot .geo .choroplethlayer path", timeout=90_000)
    pagina.wait_for_timeout(2500)


def _foto(pagina, pasta, nome):
    pagina.locator(PAINEL).scroll_into_view_if_needed()
    pagina.wait_for_timeout(500)
    pagina.locator(PAINEL).screenshot(path=str(pasta / f"{nome}.png"))
    print("ok", nome, flush=True)


def main(url, pasta, prefixo):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome", headless=True)
        pagina = navegador.new_page(viewport={"width": LARGO, "height": ALTURA})
        pagina.goto(url)
        _esperar_mapa(pagina)
        _foto(pagina, pasta, f"{prefixo}_1_largo")
        pagina.set_viewport_size({"width": ESTREITO, "height": ALTURA})
        pagina.wait_for_timeout(3000)
        _foto(pagina, pasta, f"{prefixo}_2_estreitado")
        pagina.set_viewport_size({"width": LARGO, "height": ALTURA})
        pagina.wait_for_timeout(3000)
        _foto(pagina, pasta, f"{prefixo}_3_alargado_de_novo")
        pagina.close()

        pagina = navegador.new_page(viewport={"width": ESTREITO, "height": ALTURA})
        pagina.goto(url)
        _esperar_mapa(pagina)
        _foto(pagina, pasta, f"{prefixo}_4_abre_estreito")
        pagina.set_viewport_size({"width": LARGO, "height": ALTURA})
        pagina.wait_for_timeout(3000)
        _foto(pagina, pasta, f"{prefixo}_5_estreito_depois_largo")
        pagina.close()

        # Redimensionamento gradual, como arrastar a borda da janela: vários eventos de resize seguidos.
        pagina = navegador.new_page(viewport={"width": LARGO, "height": ALTURA})
        pagina.goto(url)
        _esperar_mapa(pagina)
        for largura in (1300, 1100, 950, 800, 650, 800, 950, 1100, 1300, LARGO):
            pagina.set_viewport_size({"width": largura, "height": ALTURA})
            pagina.wait_for_timeout(400)
            if largura in (650, 800):
                pagina.wait_for_timeout(1500)
                _foto(pagina, pasta, f"{prefixo}_6_gradual_{largura}")
        pagina.wait_for_timeout(3000)
        _foto(pagina, pasta, f"{prefixo}_7_gradual_de_volta_ao_largo")

        navegador.close()


if __name__ == "__main__":
    main(*sys.argv[1:4])
