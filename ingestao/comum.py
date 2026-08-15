"""Funções e caminhos compartilhados pela camada de ingestão.

Tudo aqui existe para garantir duas propriedades:
1. Idempotência: rodar o pipeline duas vezes seguidas não duplica dados
   nem refaz trabalho desnecessário (comparação por hash de conteúdo).
2. Rastreabilidade: todo arquivo processado deixa registro de quando
   e com qual conteúdo foi ingerido.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

# Raiz do repositório: um nível acima da pasta ingestao/
RAIZ = Path(__file__).resolve().parent.parent

DIR_DOWNLOADS = RAIZ / "data" / "downloads"
DIR_BRONZE = RAIZ / "data" / "bronze" / "anp"
DIR_EXEMPLO = RAIZ / "dados_exemplo"
ARQUIVO_ESTADO = RAIZ / "data" / "estado_ingestao.json"


def garantir_diretorios() -> None:
    """Cria os diretórios de trabalho caso não existam."""
    DIR_DOWNLOADS.mkdir(parents=True, exist_ok=True)
    DIR_BRONZE.mkdir(parents=True, exist_ok=True)


def hash_arquivo(caminho: Path) -> str:
    """Calcula o SHA-256 do conteúdo de um arquivo.

    O hash é a identidade do dado: se o conteúdo não mudou,
    o hash não muda e o pipeline pode pular o reprocessamento.
    """
    sha = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(bloco)
    return sha.hexdigest()


def carregar_estado() -> dict:
    """Lê o registro de arquivos já processados (hash por nome)."""
    if ARQUIVO_ESTADO.exists():
        return json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    return {}


def salvar_estado(estado: dict) -> None:
    """Persiste o registro de arquivos processados."""
    ARQUIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_ESTADO.write_text(
        json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def agora_utc() -> str:
    """Timestamp UTC em formato ISO, usado como metadado de ingestão."""
    return datetime.now(timezone.utc).isoformat()
