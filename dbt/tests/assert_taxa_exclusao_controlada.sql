-- Teste singular (severidade warn): vigia quanto a camada intermediate
-- está descartando do staging (preço inválido, CNPJ malformado, data
-- ausente e duplicatas). Descarte acima de 5% indica degradação na
-- fonte ou erro novo na limpeza. O teste falha listando os números,
-- que é exatamente o que se quer ver primeiro ao investigar.

{{ config(severity = 'warn') }}

with contagens as (

    select
        (select count(*) from {{ ref('stg_anp__coletas') }})      as linhas_staging,
        (select count(*) from {{ ref('int_coletas_validadas') }}) as linhas_validadas

)

select
    linhas_staging,
    linhas_validadas,
    linhas_staging - linhas_validadas                                as linhas_excluidas,
    round((linhas_staging - linhas_validadas) * 1.0
        / nullif(linhas_staging, 0), 4)                              as taxa_exclusao
from contagens
where (linhas_staging - linhas_validadas) * 1.0
      / nullif(linhas_staging, 0) > 0.05
