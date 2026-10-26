"""Carga (L do ETL): salva os dados tratados em data/processed/."""

import json
from pathlib import Path

import pandas as pd

from config import PROCESSED_DIR


def salvar_csv(df: pd.DataFrame, nome_arquivo: str) -> Path:
    """Salva um DataFrame como CSV dentro de data/processed/."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    caminho = PROCESSED_DIR / nome_arquivo
    df.to_csv(caminho, index=False, encoding="utf-8")
    return caminho


def salvar_json(dados: dict, nome_arquivo: str) -> Path:
    """Salva um dicionário como JSON (UTF-8, quebras de linha LF) dentro de data/processed/."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    caminho = PROCESSED_DIR / nome_arquivo
    with caminho.open("w", encoding="utf-8", newline="\n") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=1)
        arquivo.write("\n")
    return caminho
