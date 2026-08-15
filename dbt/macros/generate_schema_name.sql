{#
  Sobrescreve o comportamento padrão do dbt, que concatenaria o schema
  alvo com o customizado (main_staging, main_marts). Aqui os schemas
  ficam com nomes limpos: staging, marts, apoio.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
