"""Barra lateral: marca do app, um bloco por página (o da página aberta em destaque) e rodapé."""

import re
from datetime import date

import streamlit as st

from config import PAGINAS, TITULO_APP, URL_REPOSITORIO, URLS_SRAG

PADRAO_DATA_NO_ARQUIVO = re.compile(r"-(\d{2})-(\d{2})-(\d{4})\.csv$")


def data_da_base(urls: dict[int, str] = URLS_SRAG) -> date | None:
    """Data mais recente que aparece no nome dos arquivos do OpenDataSUS (INFLUD26-24-08-2026.csv), ou None."""
    datas = []
    for url in urls.values():
        achado = PADRAO_DATA_NO_ARQUIVO.search(url)
        if achado:
            dia, mes, ano = (int(g) for g in achado.groups())
            datas.append(date(ano, mes, dia))
    return max(datas, default=None)


def montar_barra_lateral(paginas: dict[str, st.Page], atual: st.Page) -> None:
    """Um bloco por página, com a chave `barra_<chave>` (mais `_ativa` na aberta), e o rodapé."""
    st.sidebar.html(f'<div class="cv-marca">{TITULO_APP}</div>')
    for pagina in PAGINAS:
        ativa = paginas[pagina.chave].url_path == atual.url_path
        with st.sidebar.container(key=f"barra_{pagina.chave}{'_ativa' if ativa else ''}"):
            st.page_link(paginas[pagina.chave], label=pagina.titulo, icon=pagina.icone)
    with st.sidebar.container(key="barra_rodape"):
        st.caption("Fonte: SIVEP-Gripe (OpenDataSUS)")
        data_base = data_da_base()
        if data_base is not None:
            st.caption(f"Base do OpenDataSUS de {data_base:%d/%m/%Y}")
        st.markdown(f"[Código no GitHub]({URL_REPOSITORIO})")
