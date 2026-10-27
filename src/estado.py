"""Estado do pipeline incremental: de qual CSV e de qual versão da conversão veio o Parquet de cada ano.

O estado é só uma dica para pular trabalho: o disco manda (Parquet ausente ou estado ilegível
significam reconverter).
"""

import json
import os
from pathlib import Path

from config import NOME_ESTADO_PIPELINE, VERSAO_CONVERSAO

VERSAO_ARQUIVO = 1


def assinatura_csv(caminho_csv: Path, url: str) -> dict:
    """Identifica o CSV bruto usado: URL, tamanho e data de modificação."""
    info = caminho_csv.stat()
    return {"url": url, "tamanho_csv": info.st_size, "mtime_csv_ns": info.st_mtime_ns}


def ler_estado(pasta: Path) -> dict[str, dict]:
    """Registros por ano (chave "2024"); arquivo ausente, ilegível ou de outra versão vale por vazio."""
    try:
        dados = json.loads((pasta / NOME_ESTADO_PIPELINE).read_text(encoding="utf-8"))
        if dados["versao"] == VERSAO_ARQUIVO and isinstance(dados["anos"], dict):
            return dados["anos"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {}


def gravar_estado(pasta: Path, anos: dict[str, dict]) -> None:
    """Grava o estado de forma atômica: uma interrupção não deixa o arquivo pela metade."""
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / NOME_ESTADO_PIPELINE
    parcial = destino.with_name(destino.name + ".parcial")
    parcial.write_text(json.dumps({"versao": VERSAO_ARQUIVO, "anos": anos}, indent=1) + "\n", encoding="utf-8")
    os.replace(parcial, destino)


def registro_do_ano(assinatura: dict, casos: int) -> dict:
    return {**assinatura, "versao_conversao": VERSAO_CONVERSAO, "casos": casos}


def ano_em_dia(registro: dict | None, assinatura: dict, caminho_parquet: Path) -> bool:
    """O Parquet existe e foi gerado por esta versão da conversão a partir deste mesmo CSV."""
    return (
        registro is not None
        and caminho_parquet.exists()
        and registro.get("versao_conversao") == VERSAO_CONVERSAO
        and all(registro.get(chave) == valor for chave, valor in assinatura.items())
    )
