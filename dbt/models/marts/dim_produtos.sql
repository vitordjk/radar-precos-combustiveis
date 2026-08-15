-- Dimensão de produtos: um registro por combustível.
-- A categoria separa líquidos (litro) de gás veicular (metro cúbico),
-- o que evita comparações de preço entre unidades diferentes.
--
-- O grão é garantido por agregação, não por distinct: nos dados reais
-- da ANP o mesmo produto chega com a unidade grafada de formas
-- diferentes conforme o ano do arquivo, e um distinct sobre as duas
-- colunas gerava linha duplicada por produto (falha real encontrada
-- na primeira execução com dados oficiais). São duas defesas em
-- camadas: o staging normaliza as grafias conhecidas e a agregação
-- aqui garante o grão mesmo para variações que a normalização não
-- previu. Os dados de exemplo reproduzem a variação real de grafia.

with produtos as (

    select
        produto,
        max(unidade_medida) as unidade_medida
    from {{ ref('int_coletas_validadas') }}
    group by produto

)

select
    produto,
    unidade_medida,
    case
        when produto = 'GNV' then 'Gás veicular'
        else 'Combustíveis líquidos'
    end as categoria
from produtos
