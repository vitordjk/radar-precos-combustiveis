"""Converte os CSVs brutos em Parquet na camada bronze.

Princípios da camada bronze aplicados aqui:
1. Fidelidade ao original: todas as colunas entram como texto (VARCHAR).
   Nenhuma conversão de tipo acontece aqui. Tipagem é responsabilidade
   da camada staging (dbt), onde erros de conversão ficam visíveis e
   testáveis.
2. Imutabilidade com metadados: cada linha ganha _arquivo_origem e
   _ingerido_em, o que permite auditar de onde cada registro veio e
   deduplicar de forma determinística nas camadas seguintes.
3. Encoding detectado, nunca assumido: os arquivos da ANP alternam
   entre UTF-8 e Latin-1 ao longo dos anos. O encoding é detectado e
   informado ao DuckDB, que lê o arquivo original direto, sem cópias
   intermediárias (cópias temporárias travam no Windows).

Uso:
    python ingestao/para_bronze.py --modo amostra   # usa dados_exemplo/ (offline, CI)
    python ingestao/para_bronze.py --modo real      # usa data/downloads/ (após baixar_anp.py)
"""

import argparse
import sys
from pathlib import Path

import duckdb
from comum import (
    DIR_BRONZE,
    DIR_DOWNLOADS,
    DIR_EXEMPLO,
    agora_utc,
    carregar_estado,
    garantir_diretorios,
    hash_arquivo,
    salvar_estado,
)


def formatar_milhar(numero: int) -> str:
    """Formata inteiro com separador de milhar brasileiro (ponto)."""
    return f"{numero:,}".replace(",", ".")


def detectar_encoding(origem: Path) -> str:
    """Detecta o encoding do CSV tentando decodificar o conteúdo.

    Tenta UTF-8 (com ou sem BOM) e cai para Latin-1, que aceita
    qualquer sequência de bytes. O DuckDB recebe o nome do encoding e
    lê o arquivo original direto, sem cópia intermediária.
    """
    conteudo_bytes = origem.read_bytes()
    try:
        conteudo_bytes.decode("utf-8-sig")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def converter_arquivo(con: duckdb.DuckDBPyConnection, origem: Path) -> int:
    """Converte um CSV em Parquet na camada bronze e retorna o total de linhas."""
    encoding = detectar_encoding(origem)
    print(f"  Encoding de origem: {encoding}")
    destino = DIR_BRONZE / f"{origem.stem}.parquet"

    def sql_texto(valor: str) -> str:
        """Escapa aspas simples para uso seguro em literal SQL."""
        return valor.replace("'", "''")

    # O comando COPY do DuckDB não aceita parâmetros preparados,
    # por isso o SQL é montado com literais escapados. Os valores
    # vêm do próprio pipeline (caminhos, encoding e timestamp), não
    # de entrada externa. As barras do Windows são normalizadas para
    # barras comuns, que o DuckDB aceita em qualquer sistema.
    con.execute(
        f"""
        copy (
            select
                *,
                '{sql_texto(origem.name)}' as _arquivo_origem,
                cast('{agora_utc()}' as timestamp) as _ingerido_em
            from read_csv('{sql_texto(origem.as_posix())}',
                          header = true, sep = ';', all_varchar = true,
                          encoding = '{encoding}')
        ) to '{sql_texto(destino.as_posix())}' (format parquet)
        """
    )
    total = con.execute(
        "select count(*) from read_parquet(?)", [destino.as_posix()]
    ).fetchone()[0]
    return total


def principal() -> int:
    parser = argparse.ArgumentParser(description="CSV bruto para Parquet (bronze)")
    parser.add_argument(
        "--modo",
        choices=["amostra", "real"],
        default="amostra",
        help="amostra usa dados_exemplo/ (offline); real usa data/downloads/",
    )
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Reprocessa mesmo arquivos cujo conteúdo não mudou",
    )
    argumentos = parser.parse_args()

    garantir_diretorios()
    diretorio_origem = DIR_EXEMPLO if argumentos.modo == "amostra" else DIR_DOWNLOADS
    arquivos = sorted(diretorio_origem.glob("*.csv"))
    if not arquivos:
        print(f"Nenhum CSV encontrado em {diretorio_origem}.")
        if argumentos.modo == "real":
            print("Execute antes: python ingestao/baixar_anp.py")
        return 1

    estado = carregar_estado()

    # O bronze reflete um único modo por vez. Ao trocar de amostra para
    # real (ou o inverso), os Parquet do outro modo são removidos, senão
    # o dbt leria os dois conjuntos misturados. O prefixo da chave no
    # estado registra a qual modo cada arquivo pertence.
    outro_modo = "real" if argumentos.modo == "amostra" else "amostra"
    chaves_outro = [c for c in estado if c.startswith(f"{outro_modo}:")]
    for chave in chaves_outro:
        parquet_antigo = DIR_BRONZE / f"{Path(chave.split(':', 1)[1]).stem}.parquet"
        if parquet_antigo.exists():
            parquet_antigo.unlink()
        del estado[chave]
    if chaves_outro:
        print(
            f"Bronze limpo: {len(chaves_outro)} arquivo(s) do modo '{outro_modo}' "
            f"removido(s) para não misturar com o modo '{argumentos.modo}'."
        )

    con = duckdb.connect()
    processados, pulados, total_linhas = 0, 0, 0

    for arquivo in arquivos:
        hash_atual = hash_arquivo(arquivo)
        chave = f"{argumentos.modo}:{arquivo.name}"
        destino = DIR_BRONZE / f"{arquivo.stem}.parquet"

        if not argumentos.forcar and estado.get(chave) == hash_atual and destino.exists():
            print(f"{arquivo.name}: inalterado, pulando.")
            pulados += 1
            continue

        print(f"{arquivo.name}: convertendo para Parquet")
        linhas = converter_arquivo(con, arquivo)
        print(f"  {formatar_milhar(linhas)} linhas gravadas em bronze")
        estado[chave] = hash_atual
        processados += 1
        total_linhas += linhas

    salvar_estado(estado)
    print(
        f"\nResumo bronze: {processados} arquivo(s) processado(s), "
        f"{pulados} pulado(s), {formatar_milhar(total_linhas)} linha(s) novas."
    )
    return 0


if __name__ == "__main__":
    sys.exit(principal())
