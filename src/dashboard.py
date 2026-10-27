"""Dashboard de letalidade de COVID-19 por comorbidade: ponto de entrada (`streamlit run src/dashboard.py`).

Monta a navegação por barra lateral e cabeçalho; cada página é um script em src/paginas/ e lê só os CSVs
versionados de data/processed/, o relatório de qualidade e o GeoJSON.
"""

from html import escape
from pathlib import Path

import streamlit as st

from barra_lateral import montar_barra_lateral
from config import PAGINAS, TITULO_APP
from css import CSS_DA_PAGINA

PASTA_SRC = Path(__file__).resolve().parent

_paginas = {
    pagina.chave: st.Page(
        PASTA_SRC / pagina.arquivo, title=pagina.titulo, icon=pagina.icone, url_path=pagina.url, default=pagina.padrao,
    )
    for pagina in PAGINAS
}
# Menu próprio (um bloco por página), no lugar do menu padrão do Streamlit.
_atual = st.navigation(list(_paginas.values()), position="hidden")
_dados_da_pagina = next(p for p in PAGINAS if p.titulo == _atual.title)

st.set_page_config(page_title=f"{_atual.title} · {TITULO_APP}", layout="wide")
st.html(CSS_DA_PAGINA)
montar_barra_lateral(_paginas, _atual)
st.html(f'<div class="cv-titulo-pagina">{escape(_atual.title)}</div>')
for _descricao in _dados_da_pagina.descricoes:
    st.caption(_descricao)
st.html('<div class="cv-divisoria"></div>')
_atual.run()
