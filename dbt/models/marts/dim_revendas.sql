-- Dimensão de revendas (postos): um registro por CNPJ.
-- Nome, endereço e bandeira são os mais recentes observados nas
-- coletas. Bandeira muda ao longo do tempo (embandeiramento); a
-- bandeira vigente em cada coleta permanece na fato.

with coletas as (

    select * from {{ ref('int_coletas_validadas') }}

),

mais_recente as (

    select
        cnpj,
        revenda_nome,
        rua,
        numero,
        bairro,
        cep,
        municipio,
        uf,
        bandeira as bandeira_atual,
        data_coleta,
        row_number() over (
            partition by cnpj
            order by data_coleta desc, _ingerido_em desc
        ) as ordem
    from coletas

)

select
    cnpj,
    revenda_nome,
    rua,
    numero,
    bairro,
    cep,
    municipio,
    uf,
    bandeira_atual,
    data_coleta as data_ultima_coleta
from mais_recente
where ordem = 1
