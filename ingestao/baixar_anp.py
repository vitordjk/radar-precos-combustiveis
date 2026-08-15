"""Baixa os arquivos da Série Histórica de Preços da ANP.

Lê o manifesto ingestao/fontes.yml, baixa cada fonte para data/downloads/
e extrai o CSV quando a fonte vem compactada em ZIP (padrão da ANP a
partir de 2022 para os arquivos semestrais).

Comportamento idempotente: o conteúdo baixado é comparado por hash com o
que já existe. Se nada mudou, nada é reprocessado. Isso permite agendar
a execução semanal sem medo de duplicar dados.

Uso:
    python ingestao/baixar_anp.py            # baixa tudo do manifesto
    python ingestao/baixar_anp.py --forcar   # ignora o hash e baixa de novo
"""

import argparse
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import requests
import yaml
from comum import DIR_DOWNLOADS, garantir_diretorios, hash_arquivo

ARQUIVO_FONTES = Path(__file__).resolve().parent / "fontes.yml"
TIMEOUT_SEGUNDOS = 120


def carregar_manifesto() -> list[dict]:
    """Lê a lista de fontes do fontes.yml."""
    conteudo = yaml.safe_load(ARQUIVO_FONTES.read_text(encoding="utf-8"))
    return conteudo.get("fontes", [])


def criar_temporario(sufixo: str) -> Path:
    """Cria um arquivo temporário já fechado e retorna o caminho.

    O tempfile.mkstemp devolve um descritor aberto. No Windows, um
    descritor aberto tranca o arquivo e impede movê-lo ou apagá-lo,
    por isso ele é fechado imediatamente aqui. No Linux o fechamento
    é inofensivo, então o comportamento fica igual nos dois sistemas.
    """
    descritor, caminho = tempfile.mkstemp(suffix=sufixo)
    os.close(descritor)
    return Path(caminho)


def baixar_para_temporario(url: str) -> Path:
    """Baixa a URL para um arquivo temporário e retorna o caminho."""
    temporario = criar_temporario(".download")
    with requests.get(url, timeout=TIMEOUT_SEGUNDOS, stream=True) as resposta:
        resposta.raise_for_status()
        with open(temporario, "wb") as destino:
            for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                destino.write(bloco)
    return temporario


def extrair_csv_do_zip(caminho_zip: Path, nome_fonte: str) -> Path:
    """Extrai o primeiro CSV de um ZIP para um temporário e retorna o caminho."""
    with zipfile.ZipFile(caminho_zip) as zf:
        nomes_csv = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not nomes_csv:
            raise RuntimeError(f"Nenhum CSV encontrado no ZIP da fonte {nome_fonte}")
        if len(nomes_csv) > 1:
            print(f"  Aviso: ZIP tem {len(nomes_csv)} CSVs, usando o primeiro: {nomes_csv[0]}")
        temporario = criar_temporario(".csv")
        with zf.open(nomes_csv[0]) as origem, open(temporario, "wb") as destino:
            shutil.copyfileobj(origem, destino)
        return temporario


def processar_fonte(fonte: dict, forcar: bool) -> str:
    """Baixa uma fonte e grava o CSV final em data/downloads/.

    Retorna o status: 'baixado', 'inalterado' ou 'erro'.
    """
    nome = fonte["nome"]
    url = fonte["url"]
    tipo = fonte.get("tipo", "csv")
    destino_final = DIR_DOWNLOADS / f"{nome}.csv"

    print(f"Fonte {nome} ({tipo})")
    try:
        temporario = baixar_para_temporario(url)
    except requests.RequestException as erro:
        print(f"  Erro no download: {erro}")
        return "erro"

    csv_temporario = None
    try:
        if tipo == "zip":
            csv_temporario = extrair_csv_do_zip(temporario, nome)
        else:
            csv_temporario = temporario

        if destino_final.exists() and not forcar:
            if hash_arquivo(destino_final) == hash_arquivo(csv_temporario):
                print("  Conteúdo inalterado, mantendo o arquivo atual.")
                return "inalterado"

        shutil.move(str(csv_temporario), destino_final)
        tamanho_mb = destino_final.stat().st_size / (1024 * 1024)
        print(f"  Salvo em {destino_final.name} ({tamanho_mb:.1f} MB)")
        return "baixado"
    finally:
        # Limpa qualquer temporário que tenha sobrado (o CSV extraído
        # do ZIP e o próprio download), inclusive nos caminhos de erro.
        for sobra in (csv_temporario, temporario):
            if sobra is not None and sobra.exists():
                sobra.unlink()


def principal() -> int:
    parser = argparse.ArgumentParser(description="Download dos arquivos da ANP")
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Baixa novamente mesmo que o conteúdo não tenha mudado",
    )
    argumentos = parser.parse_args()

    garantir_diretorios()
    fontes = carregar_manifesto()
    if not fontes:
        print("Nenhuma fonte no manifesto. Verifique ingestao/fontes.yml.")
        return 1

    resumo = {"baixado": 0, "inalterado": 0, "erro": 0}
    for fonte in fontes:
        status = processar_fonte(fonte, argumentos.forcar)
        resumo[status] += 1

    print(
        f"\nResumo: {resumo['baixado']} baixado(s), "
        f"{resumo['inalterado']} inalterado(s), {resumo['erro']} erro(s)."
    )
    return 1 if resumo["erro"] and not (resumo["baixado"] or resumo["inalterado"]) else 0


if __name__ == "__main__":
    sys.exit(principal())
