-- Teste singular (severidade warn): margem negativa deve ser exceção.
-- Vender abaixo do custo acontece (queima de estoque, guerra de preço),
-- mas se passar de 5% das coletas com margem calculável, algo está
-- errado na fonte ou na transformação e merece investigação humana.

{{ config(severity = 'warn') }}

with base as (

    select
        count(*) filter (where tem_margem_calculavel)                        as com_margem,
        count(*) filter (where tem_margem_calculavel and e_margem_negativa)  as negativas
    from {{ ref('int_coletas_validadas') }}

)

select
    com_margem,
    negativas,
    round(negativas * 1.0 / nullif(com_margem, 0), 4) as proporcao
from base
where negativas * 1.0 / nullif(com_margem, 0) > 0.05
