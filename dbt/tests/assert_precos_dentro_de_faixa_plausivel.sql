-- Teste singular (severidade error): nenhum preço válido pode estar
-- fora da faixa fisicamente plausível para combustíveis no Brasil.
-- A faixa é generosa de propósito (0,50 a 25,00 reais) para não gerar
-- alarme falso com inflação, mas pega erros de unidade e de conversão.

select
    id_coleta,
    produto,
    data_coleta,
    valor_venda
from {{ ref('fct_coletas_precos') }}
where valor_venda < 0.5
   or valor_venda > 25
