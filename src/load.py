"""Carga (L do ETL): salva os dados tratados em data/processed/."""

import contextlib
import json
import os
from pathlib import Path

import pandas as pd

from config import PROCESSED_DIR


def salvar_csv(df: pd.DataFrame, nome_arquivo: str) -> Path:
    """Salva um DataFrame como CSV dentro de data/processed/."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    caminho = PROCESSED_DIR / nome_arquivo
    df.to_csv(caminho, index=False, encoding="utf-8")
    return caminho


def publicar_csvs(tabelas: dict[str, pd.DataFrame]) -> dict[str, Path]:
    """Grava todos os CSVs em arquivos temporários ao lado dos definitivos e só então troca cada um pelo definitivo.

    Uma falha ao gravar qualquer temporário (disco cheio, erro de escrita) apaga os temporários e deixa todos os
    CSVs publicados como estavam; a troca (os.replace, atômica por arquivo) só começa com todos prontos.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    temporarios = {nome: PROCESSED_DIR / f".{nome}.tmp" for nome in tabelas}
    try:
        for nome, df in tabelas.items():
            df.to_csv(temporarios[nome], index=False, encoding="utf-8")
    except BaseException:
        for temporario in temporarios.values():
            with contextlib.suppress(OSError):
                temporario.unlink(missing_ok=True)
        raise
    for nome, temporario in temporarios.items():
        os.replace(temporario, PROCESSED_DIR / nome)
    return {nome: PROCESSED_DIR / nome for nome in tabelas}


def salvar_json(dados: dict, nome_arquivo: str) -> Path:
    """Salva um dicionário como JSON (UTF-8, quebras de linha LF) dentro de data/processed/."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    caminho = PROCESSED_DIR / nome_arquivo
    with caminho.open("w", encoding="utf-8", newline="\n") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=1)
        arquivo.write("\n")
    return caminho
