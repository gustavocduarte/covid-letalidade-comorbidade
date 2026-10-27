"""Extração (E do ETL): baixa o banco de dados do SIVEP-Gripe (SRAG) do OpenDataSUS."""

import os
from pathlib import Path

import requests

from config import PASTA_RAW, URLS_SRAG


def baixar_arquivo(url: str, pasta_destino: Path) -> Path:
    """Baixa um arquivo grande em pedaços (streaming), sem carregar tudo na RAM.

    Grava num arquivo parcial e só o renomeia no fim: um download interrompido nunca deixa um CSV
    truncado com o nome final (o pipeline o tomaria por completo).
    """
    pasta_destino.mkdir(parents=True, exist_ok=True)
    nome_arquivo = url.split("/")[-1]
    caminho_destino = pasta_destino / nome_arquivo
    parcial = caminho_destino.with_name(nome_arquivo + ".parcial")

    try:
        with requests.get(url, stream=True, timeout=30) as resposta:
            resposta.raise_for_status()  # lança erro se o servidor devolveu algo diferente de 200 OK
            tamanho_total = int(resposta.headers.get("content-length", 0))
            baixado = 0

            with open(parcial, "wb") as arquivo:
                for pedaco in resposta.iter_content(chunk_size=1024 * 1024):  # 1 MB por vez
                    arquivo.write(pedaco)
                    baixado += len(pedaco)
                    percentual = (baixado / tamanho_total) * 100 if tamanho_total else 0
                    print(f"\rBaixado: {baixado / 1e6:,.1f} MB / {tamanho_total / 1e6:,.1f} MB ({percentual:.1f}%)", end="")
        print()  # pula linha no final
        os.replace(parcial, caminho_destino)
    except BaseException:
        parcial.unlink(missing_ok=True)
        raise
    return caminho_destino


if __name__ == "__main__":
    caminho = baixar_arquivo(URLS_SRAG[2020], PASTA_RAW)
    print(f"Download concluído: {caminho}")
