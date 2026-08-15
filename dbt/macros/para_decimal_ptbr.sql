{#
  Converte texto numérico em formato brasileiro (vírgula decimal)
  para DECIMAL(10,3). Valores vazios viram NULL e conversões
  impossíveis também (try_cast), em vez de derrubar o pipeline.
#}
{% macro para_decimal_ptbr(coluna) %}
    try_cast(replace(nullif(trim({{ coluna }}), ''), ',', '.') as decimal(10, 3))
{% endmacro %}
