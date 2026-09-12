"""Extração (E do ETL): baixa o banco de dados do SIVEP-Gripe (SRAG) do OpenDataSUS."""

from pathlib import Path

import requests

# URLs oficiais do banco de SRAG por ano, hospedadas pelo Ministério da Saúde (OpenDataSUS).
# Conferidas em 2026-09-11 (a URL de cada ano muda de tempos em tempos, porque inclui a
# data da última atualização do "banco vivo" daquele ano).
URLS_SRAG = {
    2020: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2020/INFLUD20-23-03-2026.csv",
    2021: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2021/INFLUD21-23-03-2026.csv",
    2022: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2022/INFLUD22-23-03-2026.csv",
    2023: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2023/INFLUD23-23-03-2026.csv",
    2024: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2024/INFLUD24-23-03-2026.csv",
    2025: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2025/INFLUD25-24-08-2026.csv",
    2026: "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26-24-08-2026.csv",
}

# Pasta onde os dados brutos (sem nenhuma alteração) devem ficar.
PASTA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def baixar_arquivo(url: str, pasta_destino: Path) -> Path:
    """Baixa um arquivo grande em pedaços (streaming), sem carregar tudo na RAM."""
    pasta_destino.mkdir(parents=True, exist_ok=True)
    nome_arquivo = url.split("/")[-1]
    caminho_destino = pasta_destino / nome_arquivo

    with requests.get(url, stream=True, timeout=30) as resposta:
        resposta.raise_for_status()  # lança erro se o servidor devolveu algo diferente de 200 OK
        tamanho_total = int(resposta.headers.get("content-length", 0))
        baixado = 0

        with open(caminho_destino, "wb") as arquivo:
            for pedaco in resposta.iter_content(chunk_size=1024 * 1024):  # 1 MB por vez
                arquivo.write(pedaco)
                baixado += len(pedaco)
                percentual = (baixado / tamanho_total) * 100 if tamanho_total else 0
                print(f"\rBaixado: {baixado / 1e6:,.1f} MB / {tamanho_total / 1e6:,.1f} MB ({percentual:.1f}%)", end="")

    print()  # pula linha no final
    return caminho_destino


if __name__ == "__main__":
    caminho = baixar_arquivo(URLS_SRAG[2020], PASTA_RAW)
    print(f"Download concluído: {caminho}")
