-- Intermediate: deduplicação e qualidade.
--
-- Por que existe deduplicação aqui: as fontes da ANP se sobrepõem de
-- propósito (os arquivos de "últimas 4 semanas" repetem coletas que
-- depois aparecem no consolidado semestral) e arquivos podem conter
-- linhas repetidas. A regra é determinística: para cada combinação
-- posto + produto + data, vence a linha ingerida mais recentemente.
--
-- Por que filtrar preço inválido aqui e não no staging: o staging
-- preserva tudo que veio da fonte, já tipado. Este modelo aplica a
-- primeira regra de negócio (preço de venda precisa ser positivo) e o
-- teste assert_taxa_exclusao_controlada vigia quanto está sendo
-- descartado, para que uma piora na fonte não passe despercebida.

with coletas as (

    select * from {{ ref('stg_anp__coletas') }}

),

deduplicado as (

    select
        *,
        row_number() over (
            partition by cnpj, produto, data_coleta
            order by _ingerido_em desc, _arquivo_origem desc
        ) as ordem_duplicata
    from coletas

),

validado as (

    select
        {{ dbt_utils.generate_surrogate_key(['cnpj', 'produto', 'data_coleta']) }} as id_coleta,
        regiao_sigla,
        uf,
        municipio,
        revenda_nome,
        cnpj,
        rua,
        numero,
        bairro,
        cep,
        produto,
        data_coleta,
        valor_venda,
        valor_compra,
        unidade_medida,
        bandeira,
        _arquivo_origem,
        _ingerido_em,
        (valor_compra is not null and valor_compra > 0)          as tem_margem_calculavel,
        (valor_compra is not null and valor_venda < valor_compra) as e_margem_negativa
    from deduplicado
    where ordem_duplicata = 1
      and valor_venda is not null
      and valor_venda > 0
      and data_coleta is not null
      and length(cnpj) = 14

)

select * from validado
