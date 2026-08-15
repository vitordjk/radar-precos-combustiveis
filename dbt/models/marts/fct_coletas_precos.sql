-- Fato: uma linha por coleta de preço válida.
-- Grão: posto (CNPJ) + produto + data da coleta.
-- Margem bruta e percentual só existem quando a fonte informa o valor
-- de compra (minoria das coletas), e ficam nulas caso contrário: número
-- ausente é mais honesto que número inventado.

with coletas as (

    select * from {{ ref('int_coletas_validadas') }}

)

select
    coletas.id_coleta,
    coletas.cnpj,
    coletas.produto,
    localidades.id_localidade,
    coletas.data_coleta,
    coletas.bandeira,
    coletas.valor_venda,
    coletas.valor_compra,
    case
        when coletas.tem_margem_calculavel
            then round(coletas.valor_venda - coletas.valor_compra, 3)
    end as margem_bruta,
    case
        when coletas.tem_margem_calculavel
            then round((coletas.valor_venda - coletas.valor_compra) / coletas.valor_compra, 4)
    end as margem_pct,
    coletas.e_margem_negativa,
    coletas._arquivo_origem,
    coletas._ingerido_em
from coletas
left join {{ ref('dim_localidades') }} as localidades
    on coletas.uf = localidades.uf
   and coletas.municipio = localidades.municipio
