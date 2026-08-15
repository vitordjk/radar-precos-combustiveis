"""Definições do Dagster: o mapa executável do pipeline.

O Dagster trabalha com o conceito de asset: cada dado importante
(arquivos brutos, bronze, cada modelo dbt) é um ativo com dependências
explícitas. O grafo de linhagem que aparece na interface não é um
desenho, é o próprio plano de execução.

Fluxo: arquivos_anp_brutos -> camada_bronze -> modelos do dbt
(staging -> intermediate -> marts), com agendamento semanal alinhado
à publicação dos arquivos de "últimas 4 semanas" pela ANP.

Para subir a interface local:
    dagster dev -f orquestracao/definitions.py
"""

import os
import subprocess
import sys
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetKey,
    Definitions,
    MaterializeResult,
    ScheduleDefinition,
    asset,
    define_asset_job,
)
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

RAIZ = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# MODO_INGESTAO=amostra roda offline com dados_exemplo/ (útil para
# demonstração e testes). MODO_INGESTAO=real baixa da ANP.
MODO_INGESTAO = os.getenv("MODO_INGESTAO", "real")

# O DbtCliResource executa o dbt com diretório de trabalho dentro de
# dbt/, o que quebraria os caminhos relativos padrão (pensados para
# execução manual a partir da raiz). O orquestrador resolve isso
# exportando caminhos absolutos antes de qualquer chamada ao dbt.
os.environ["DUCKDB_PATH"] = (RAIZ / "warehouse" / "radar.duckdb").as_posix()
os.environ["BRONZE_GLOB"] = (RAIZ / "data" / "bronze" / "anp").as_posix() + "/*.parquet"

projeto_dbt = DbtProject(
    project_dir=RAIZ / "dbt",
    profiles_dir=RAIZ / "dbt",
)
# Em `dagster dev`, gera o manifest.json automaticamente se necessário.
projeto_dbt.prepare_if_dev()


def _rodar_script(context: AssetExecutionContext, argumentos: list[str]) -> None:
    """Executa um script da ingestão a partir da raiz do repositório."""
    resultado = subprocess.run(
        [PYTHON, *argumentos],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    if resultado.stdout:
        context.log.info(resultado.stdout)
    if resultado.returncode != 0:
        raise RuntimeError(f"Falha em {' '.join(argumentos)}:\n{resultado.stderr}")


@asset(
    group_name="ingestao",
    description="Arquivos CSV da ANP em data/downloads/ (ou dados_exemplo/ no modo amostra).",
)
def arquivos_anp_brutos(context: AssetExecutionContext) -> MaterializeResult:
    if MODO_INGESTAO == "amostra":
        context.log.info("Modo amostra: usando dados_exemplo/, sem download.")
        return MaterializeResult(metadata={"modo": "amostra"})
    _rodar_script(context, ["ingestao/baixar_anp.py"])
    return MaterializeResult(metadata={"modo": "real"})


@asset(
    group_name="ingestao",
    deps=[arquivos_anp_brutos],
    description="Camada bronze: Parquet imutável com metadados de ingestão.",
)
def camada_bronze(context: AssetExecutionContext) -> MaterializeResult:
    _rodar_script(context, ["ingestao/para_bronze.py", "--modo", MODO_INGESTAO])
    return MaterializeResult(metadata={"modo": MODO_INGESTAO})


class TradutorRadar(DagsterDbtTranslator):
    """Liga o mundo dbt ao mundo Dagster no grafo de linhagem.

    A fonte bronze do dbt passa a apontar para o asset camada_bronze,
    de modo que ingestão e transformação apareçam como um grafo único
    e contínuo na interface do Dagster.
    """

    def get_asset_key(self, dbt_resource_props):
        if dbt_resource_props["resource_type"] == "source":
            return AssetKey("camada_bronze")
        return super().get_asset_key(dbt_resource_props)


@dbt_assets(
    manifest=projeto_dbt.manifest_path,
    dagster_dbt_translator=TradutorRadar(),
)
def modelos_dbt(context: AssetExecutionContext, dbt: DbtCliResource):
    """Todos os modelos, seeds e testes do dbt como assets do Dagster."""
    yield from dbt.cli(["build"], context=context).stream()

job_pipeline_completo = define_asset_job(
    name="pipeline_completo",
    selection="*",
    description="Ingestão da ANP seguida do build completo do dbt com testes.",
)

agendamento_semanal = ScheduleDefinition(
    name="semanal_segunda_7h",
    job=job_pipeline_completo,
    cron_schedule="0 7 * * 1",
    execution_timezone="America/Sao_Paulo",
)

defs = Definitions(
    assets=[arquivos_anp_brutos, camada_bronze, modelos_dbt],
    jobs=[job_pipeline_completo],
    schedules=[agendamento_semanal],
    resources={
        "dbt": DbtCliResource(project_dir=projeto_dbt),
    },
)
