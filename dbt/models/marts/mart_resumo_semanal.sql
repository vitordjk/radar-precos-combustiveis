-- Mart de decisão: resumo semanal de preços por UF e produto.
-- Este é o modelo que responde a pergunta de negócio do projeto:
-- onde o preço está fora da curva e como ele se move semana a semana.
--
-- Mediana e percentis em vez de média: preço de combustível tem cauda
-- (postos muito acima do mercado) e a mediana resiste a isso.

with fato as (

    select
        fato.data_coleta,
        fato.produto,
        fato.valor_venda,
        localidades.uf,
        localidades.regiao
    from {{ ref('fct_coletas_precos') }} as fato
    inner join {{ ref('dim_localidades') }} as localidades
        on fato.id_localidade = localidades.id_localidade

),

semanal as (

    select
        date_trunc('week', data_coleta)          as semana,
        uf,
        regiao,
        produto,
        count(*)                                 as qtd_coletas,
        round(median(valor_venda), 3)            as preco_mediano,
        round(quantile_cont(valor_venda, 0.25), 3) as preco_p25,
        round(quantile_cont(valor_venda, 0.75), 3) as preco_p75,
        round(min(valor_venda), 3)               as preco_minimo,
        round(max(valor_venda), 3)               as preco_maximo
    from fato
    group by 1, 2, 3, 4

),

com_variacao as (

    select
        *,
        lag(preco_mediano) over (
            partition by uf, produto
            order by semana
        ) as preco_mediano_semana_anterior
    from semanal

)

select
    semana,
    uf,
    regiao,
    produto,
    qtd_coletas,
    preco_mediano,
    preco_p25,
    preco_p75,
    preco_minimo,
    preco_maximo,
    case
        when preco_mediano_semana_anterior is not null
             and preco_mediano_semana_anterior > 0
            then round(
                (preco_mediano - preco_mediano_semana_anterior)
                / preco_mediano_semana_anterior, 4
            )
    end as variacao_pct_semana
from com_variacao
