"""Bloco de CSS do dashboard: o único `st.html` com estilo da página."""

from string import Template

from config import (
    COR_BORDA,
    COR_FUNDO_PAINEL,
    COR_LINHA_TABELA,
    COR_PRINCIPAL,
    COR_TEXTO,
    COR_TEXTO_SECUNDARIO,
)

# Ganchos `.st-key-painel_*` e `.st-key-barra_*` saem do `key` de cada st.container. Se o Streamlit deixar
# de aceitar este bloco, o conteúdo continua na tela, só sem o estilo.
CSS_DA_PAGINA = Template("""<style>
[class*="st-key-painel_"] { background-color: $painel; border-radius: 12px; }
[class*="st-key-barra_"] { background-color: $painel; border-color: $borda; border-radius: 10px; }
[class*="st-key-barra_"][class*="_ativa"] { border-color: $principal; }
[class*="st-key-barra_"] a, [class*="st-key-barra_"] a p { font-size: 16px; font-weight: 600; }
[class*="st-key-barra_"][class*="_ativa"] a, [class*="st-key-barra_"][class*="_ativa"] a p { color: $principal; }
.st-key-barra_rodape { background-color: transparent; border-color: transparent; }
.st-key-barra_rodape p, .st-key-barra_rodape a { font-size: 13px; color: $secundario; }
[data-testid="stMainBlockContainer"] { padding-top: 4rem; }
.cv-titulo-pagina { font-size: 1.4rem; font-weight: 700; line-height: 1.2; }
.cv-marca { font-size: 1rem; font-weight: 700; padding: .25rem .25rem .5rem; }
.cv-divisoria { border-top: 1px solid $borda; margin: .25rem 0 .75rem; }
.cv-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1rem; }
.cv-kpi { background: $painel; border: 1px solid $borda; border-radius: 12px; padding: 18px 20px;
  display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.cv-secao { font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  color: $secundario; margin: 0; }
.cv-ajuda { cursor: help; margin-left: .4rem; padding: 0 .35rem; border: 1px solid $borda;
  border-radius: 50%; font-size: .65rem; letter-spacing: 0; }
.cv-valor { font-family: "JetBrains Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums;
  font-size: 1.75rem; font-weight: 600; white-space: nowrap; color: $texto; }
.cv-linha { font-size: .8rem; color: $secundario; min-height: 1.2em; }
.cv-cabecalho { display: flex; justify-content: space-between; align-items: center; gap: .75rem; }
.cv-celulas { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: $borda;
  border-radius: 8px; overflow: hidden; }
.cv-celula { background: $painel; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.cv-valor-medio { font-family: "JetBrains Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums;
  font-size: 1.35rem; font-weight: 600; color: $texto; }
.cv-legenda { display: flex; gap: 1rem; font-size: 12px; color: $secundario; margin: .25rem 0; }
.cv-legenda span { display: flex; align-items: center; gap: 6px; }
.cv-legenda i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.cv-linha-tabela { border-top: 1px solid $linha; }
</style>""").substitute(
    painel=COR_FUNDO_PAINEL, borda=COR_BORDA, principal=COR_PRINCIPAL, secundario=COR_TEXTO_SECUNDARIO,
    texto=COR_TEXTO, linha=COR_LINHA_TABELA,
)
