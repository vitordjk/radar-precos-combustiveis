-- Staging: primeira camada tipada.
-- Responsabilidades desta camada (e apenas desta camada):
--   1. Renomear colunas para snake_case em português.
--   2. Converter tipos: datas, decimais com vírgula, texto aparado.
--   3. Padronizar chaves: CNPJ sem máscara, produto e bandeira em caixa alta.
-- O que NÃO acontece aqui: deduplicação, filtros de qualidade e regras
-- de negócio. Isso é papel da camada intermediate, para que cada
-- transformação tenha um lugar único e testável.

with fonte as (

    select * from {{ source('bronze', 'anp_coletas') }}

),

renomeado_e_tipado as (

    select
        trim("Regiao - Sigla")                                   as regiao_sigla,
        trim("Estado - Sigla")                                   as uf,
        upper(trim(regexp_replace("Municipio", '\s+', ' ', 'g'))) as municipio,
        trim("Revenda")                                          as revenda_nome,
        regexp_replace(coalesce("CNPJ da Revenda", ''), '[^0-9]', '', 'g') as cnpj,
        trim("Nome da Rua")                                      as rua,
        trim("Numero Rua")                                       as numero,
        trim("Bairro")                                           as bairro,
        trim("Cep")                                              as cep,
        upper(trim("Produto"))                                   as produto,
        strptime(trim("Data da Coleta"), '%d/%m/%Y')::date       as data_coleta,
        {{ para_decimal_ptbr('"Valor de Venda"') }}              as valor_venda,
        {{ para_decimal_ptbr('"Valor de Compra"') }}             as valor_compra,
        -- Arquivos de anos diferentes grafam a unidade de formas
        -- distintas ("R$ / litro", "R$/litro"). Normaliza caixa,
        -- colapsa espaços e padroniza o entorno da barra.
        regexp_replace(
            regexp_replace(upper(trim("Unidade de Medida")), '\s+', ' ', 'g'),
            '\s*/\s*', ' / ', 'g'
        )                                                        as unidade_medida,
        upper(trim("Bandeira"))                                  as bandeira,
        _arquivo_origem,
        _ingerido_em
    from fonte

)

select * from renomeado_e_tipado
