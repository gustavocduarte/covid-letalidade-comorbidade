"""Carga (L do ETL): salva os dados tratados em data/processed/."""

from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"


def salvar_csv(df: pd.DataFrame, nome_arquivo: str) -> Path:
    """Salva um DataFrame como CSV dentro de data/processed/."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    caminho = PROCESSED_DIR / nome_arquivo
    df.to_csv(caminho, index=False, encoding="utf-8")
    return caminho


def anexar_csv(df: pd.DataFrame, nome_arquivo: str, primeiro_bloco: bool) -> Path:
    """Acrescenta um DataFrame a um CSV, um pedaço de cada vez, sem juntar tudo na memória antes.

    `primeiro_bloco=True` começa o arquivo do zero (com cabeçalho); nos blocos seguintes,
    passe `False` pra só ir acrescentando linhas (sem repetir o cabeçalho).
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    caminho = PROCESSED_DIR / nome_arquivo
    modo = "w" if primeiro_bloco else "a"
    df.to_csv(caminho, index=False, encoding="utf-8", mode=modo, header=primeiro_bloco)
    return caminho
