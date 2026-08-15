-- Dimensão de localidades: grão município + UF.
-- O seed seed_estados fornece o nome do estado e a região por extenso,
-- enriquecendo a sigla que vem da ANP.

with localidades as (

    select distinct
        uf,
        municipio
    from {{ ref('int_coletas_validadas') }}

),

enriquecido as (

    select
        {{ dbt_utils.generate_surrogate_key(['localidades.uf', 'localidades.municipio']) }} as id_localidade,
        localidades.uf,
        localidades.municipio,
        estados.estado,
        estados.regiao
    from localidades
    left join {{ ref('seed_estados') }} as estados
        on localidades.uf = estados.uf

)

select * from enriquecido
