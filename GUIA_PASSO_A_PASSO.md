# Guia passo a passo: construindo a plataforma do zero

Este guia explica como o projeto foi construído, na ordem em que as
decisões foram tomadas. Cada fase tem quatro partes: o que foi feito,
por que foi feito assim, como executar e como validar que funcionou.

A ideia é que você consiga reconstruir o projeto entendendo cada peça,
e não apenas copiando comandos. Os conceitos explicados aqui (camadas,
idempotência, testes como contrato, orquestração por assets) são os
mesmos que aparecem em entrevistas para vagas de analytics engineer e
engenheiro de dados.

---

## Fase 0. O mapa mental antes de qualquer código

Toda plataforma de dados responde às mesmas cinco perguntas:

1. De onde o dado vem e como ele entra? (ingestão)
2. Onde o dado bruto fica guardado sem alteração? (bronze)
3. Como o dado vira algo confiável e organizado? (transformação)
4. Como eu sei que ele continua confiável amanhã? (testes e frescor)
5. Quem aperta o botão todo dia? (orquestração e CI)

Neste projeto:

| Pergunta | Resposta | Ferramenta |
| --- | --- | --- |
| Ingestão | Download semanal dos arquivos da ANP | Python |
| Bronze | Parquet imutável com metadados | Python + DuckDB |
| Transformação | Camadas staging, intermediate e marts | dbt |
| Confiança | 29 testes por build + frescor da fonte | dbt |
| Automação | Grafo de assets agendado + pipeline a cada PR | Dagster + GitHub Actions |

Guarde este quadro. Tudo que vem a seguir é o preenchimento dele.

---

## Fase 1. Ambiente

### O que

Python 3.11 ou superior, Git e um editor (VS Code). Nenhum banco para
instalar: o DuckDB é uma biblioteca Python e o warehouse é um arquivo.

### Por que

A escolha do DuckDB elimina toda a fricção de infraestrutura (servidor,
usuário, porta, firewall) e mantém o foco no que o projeto quer
demonstrar: engenharia de dados analítica. A justificativa completa
está em `docs/decisoes.md`, decisão 1.

### Como

```powershell
# Windows (PowerShell), a partir da pasta do projeto
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação do ambiente virtual, execute uma
única vez:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Como validar

```powershell
python -c "import duckdb; print(duckdb.__version__)"
dbt --version
dagster --version
```

Os três comandos devem imprimir versões sem erro.

---

## Fase 2. Entender a fonte antes de escrever código

### O que

A Série Histórica da ANP, na página oficial de dados abertos. Antes de
qualquer linha de código, abra um arquivo e olhe o conteúdo.

### Por que

Este é o hábito que separa pipeline que funciona de pipeline que
quebra no terceiro mês. Olhando os arquivos reais da ANP se descobre:

- O separador é ponto e vírgula, não vírgula.
- O decimal usa vírgula (5,89) e precisa de conversão.
- O CNPJ aparece com máscara, sem máscara e com espaços ao redor.
- O valor de compra está vazio na maior parte das linhas. Isso não é
  defeito: é a natureza da fonte, e o modelo precisa conviver com isso.
- Arquivos antigos vêm em Latin-1, os novos em UTF-8. Se o código
  assumir um só encoding, a acentuação quebra silenciosamente.
- Os arquivos semestrais recentes vêm compactados em ZIP.
- Os arquivos de "últimas 4 semanas" repetem coletas que depois
  aparecem no consolidado semestral. A sobreposição é proposital e
  exige uma regra de deduplicação.

Cada um desses pontos virou uma decisão de código nas fases seguintes.
O arquivo `ingestao/fontes.yml` registra as URLs verificadas e a data
da verificação, porque URLs de portal governamental mudam.

### Como validar

Abra `dados_exemplo/ca-2024-01-amostra.csv` no editor e identifique
na prática os problemas listados acima. Os arquivos de exemplo
reproduzem cada um deles de propósito (ver `dados_exemplo/LEIA-ME.md`).

---

## Fase 3. Ingestão e camada bronze

### O que

Dois scripts:

- `ingestao/baixar_anp.py` baixa os arquivos do manifesto, extrai o
  CSV de dentro do ZIP quando necessário e só substitui o arquivo
  local se o conteúdo tiver mudado (comparação por hash SHA-256).
- `ingestao/para_bronze.py` normaliza o encoding para UTF-8, converte
  cada CSV em Parquet e adiciona duas colunas de metadados:
  `_arquivo_origem` e `_ingerido_em`.

### Por que

Três princípios de engenharia estão embutidos aqui:

**Idempotência.** Rodar o pipeline duas vezes seguidas produz o mesmo
resultado que rodar uma vez. Sem isso, não existe agendamento seguro:
qualquer reexecução (e reexecuções acontecem) duplicaria dados. O hash
do conteúdo é o que torna o pulo de arquivos inalterados confiável,
mais confiável que comparar datas de modificação.

**Bronze fiel ao original.** Na camada bronze, tudo entra como texto,
sem nenhuma conversão de tipo. Se a ANP mandar uma data inválida, ela
chega inválida ao bronze e a conversão falha de forma visível e
testável no staging. Converter cedo demais esconde erros.

**Metadados de linhagem.** As colunas `_arquivo_origem` e
`_ingerido_em` respondem, para qualquer linha do warehouse, "de onde
você veio e quando". Elas também são o critério de desempate da
deduplicação: entre duas versões da mesma coleta, vence a mais
recentemente ingerida.

Parquet em vez de CSV no bronze porque é tipado por coluna, comprimido
e ordens de magnitude mais rápido de ler no DuckDB.

### Como

```powershell
# Primeiro contato: modo amostra, sem depender de internet
python ingestao/para_bronze.py --modo amostra

# Com os dados reais da ANP
python ingestao/baixar_anp.py
python ingestao/para_bronze.py --modo real
```

### Como validar

1. Rode `para_bronze.py --modo amostra` duas vezes. A segunda execução
   deve pular os dois arquivos ("inalterado, pulando"). Isso é a
   idempotência funcionando.
2. Confira o encoding: o arquivo `ca-2023-02-amostra.csv` está em
   Latin-1, mas o Parquet gerado deve mostrar "SÃO JOSÉ DOS CAMPOS"
   com acentuação correta:

```powershell
python -c "import duckdb; print(duckdb.sql(\"select distinct Municipio from read_parquet('data/bronze/anp/ca-2023-02-amostra.parquet') where Municipio like '%SÃO%'\"))"
```

---

## Fase 4. Transformação com dbt: as camadas

### O que

O dbt organiza a transformação em modelos SQL com dependências
explícitas (`ref`) e uma fonte declarada (`source`). Aqui são três
camadas com responsabilidades separadas:

| Modelo | Camada | Faz | Não faz |
| --- | --- | --- | --- |
| `stg_anp__coletas` | staging | Tipagem, renomeação, CNPJ sem máscara, texto padronizado | Deduplicar, filtrar, regra de negócio |
| `int_coletas_validadas` | intermediate | Deduplicação determinística, filtro de preço válido, flags de qualidade | Agregar, juntar dimensões |
| `dim_*`, `fct_*`, `mart_*` | marts | Modelo estrela e resumo semanal de decisão | Limpeza |

### Por que

**Uma responsabilidade por camada.** Quando cada transformação tem um
lugar único, um erro tem um lugar único para ser procurado. Se a
margem está errada, o problema está na fato. Se apareceu duplicata, o
problema está na intermediate. Isso é o que torna o pipeline
manutenível por outra pessoa (ou por você daqui a seis meses).

**A deduplicação mora na intermediate** porque a sobreposição entre
arquivos da ANP é um fato da fonte, não uma sujeira acidental. A regra
é determinística e está escrita no próprio modelo: para cada
combinação posto + produto + data, vence a linha com `_ingerido_em`
mais recente. Determinística significa: rodando mil vezes, o resultado
é o mesmo.

**Mediana em vez de média no resumo semanal** porque preço de
combustível tem cauda (poucos postos muito acima do mercado puxariam a
média para cima). A mediana resiste a valores extremos. Mesmo
raciocínio do DOH ponderado no projeto Aurora: a estatística escolhida
é parte da qualidade da resposta.

**Detalhes de implementação que valem estudo:**

- A fonte bronze é lida direto dos Parquet pelo dbt-duckdb via
  `external_location`, sem etapa de carga. O caminho é parametrizado
  por variável de ambiente para funcionar tanto na execução manual
  quanto no Dagster (ver fase 6).
- A macro `para_decimal_ptbr` centraliza a conversão de vírgula para
  ponto com `try_cast`: valor impossível vira nulo em vez de derrubar
  o build, e os testes acusam se os nulos passarem do aceitável.
- A macro `generate_schema_name` mantém os schemas com nomes limpos
  (staging, marts, apoio) em vez do padrão concatenado do dbt.
- O seed `seed_estados` mostra o uso correto de seed: tabela pequena,
  estática e de apoio. Seed não é para dado de fato.

### Como

```powershell
dbt deps --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt
```

`dbt build` executa seeds, modelos e testes na ordem do grafo de
dependências. Os parâmetros `--project-dir` e `--profiles-dir` fixam a
execução a partir da raiz do repositório, que é a convenção deste
projeto (assim os caminhos relativos do warehouse e do bronze
funcionam sem configuração extra).

### Como validar

O resultado esperado é `PASS=37 WARN=0 ERROR=0`. Depois, explore o
warehouse:

```powershell
python -c "import duckdb; con = duckdb.connect('warehouse/radar.duckdb'); print(con.sql('select * from marts.mart_resumo_semanal order by semana desc limit 10'))"
```

---

## Fase 5. Testes: o contrato de qualidade

### O que

29 testes que rodam em todo build, em duas famílias:

**Testes genéricos** (declarados nos arquivos `.yml`): unicidade e não
nulidade de chaves, relacionamentos entre fato e dimensões, valores
aceitos para categoria, combinação única de semana + UF + produto no
resumo.

**Testes singulares** (arquivos SQL em `dbt/tests/`), cada um com uma
severidade escolhida de propósito:

| Teste | Severidade | Protege contra |
| --- | --- | --- |
| `assert_precos_dentro_de_faixa_plausivel` | erro | Erro de unidade ou de conversão decimal |
| `assert_margem_negativa_incomum` | aviso | Degradação da fonte ou da limpeza (mais de 5% das margens negativas) |
| `assert_taxa_exclusao_controlada` | aviso | Limpeza descartando dado demais sem ninguém perceber |

### Por que

Um teste de dados é um contrato: enquanto ele passa, quem consome o
mart pode confiar sem reconferir. A distinção erro versus aviso é a
parte que demonstra maturidade: erro é para violação que invalida o
dado (preço de 250 reais o litro não pode chegar ao consumo), aviso é
para anomalia que merece um olhar humano mas não justifica parar a
operação (margem negativa existe de verdade em guerra de preço).

O teste de taxa de exclusão merece atenção especial: ele vigia o
próprio pipeline. Se a intermediate começar a descartar mais de 5% do
staging, o teste falha listando os números. Sem ele, uma mudança na
fonte poderia silenciosamente encolher a base.

Além dos testes de build, `dbt source freshness` compara o
`_ingerido_em` mais recente com o relógio: se a ingestão parar de
trazer dado novo por mais de 45 dias, aviso; mais de 120, erro.

### Como validar

Quebre de propósito para ver o contrato agir. Edite temporariamente
`dados_exemplo/ca-2024-01-amostra.csv`, troque um preço para `99,000`,
rode a ingestão com `--forcar` e o build:

```powershell
python ingestao/para_bronze.py --modo amostra --forcar
dbt build --project-dir dbt --profiles-dir dbt
```

O teste `assert_precos_dentro_de_faixa_plausivel` deve falhar com
erro, apontando a linha. Desfaça a edição e rode de novo com
`--forcar` para voltar ao verde. Saber quebrar e consertar o pipeline
é a melhor forma de entendê-lo.

---

## Fase 6. Orquestração com Dagster

### O que

`orquestracao/definitions.py` declara o pipeline como um grafo de
assets: `arquivos_anp_brutos` (download), `camada_bronze` (Parquet) e
todos os modelos do dbt, importados automaticamente do manifest. Um
job materializa tudo e um agendamento executa toda segunda às 7h
(horário de São Paulo), alinhado à publicação semanal da ANP.

### Por que

**Asset em vez de tarefa.** O Airflow clássico pensa em tarefas
("rode este script"). O Dagster pensa em ativos ("este dado existe e
depende daquele"). Para um pipeline analítico, o segundo modelo é mais
honesto: o que importa é o estado dos dados, não a execução em si. O
grafo de linhagem que aparece na interface não é um desenho decorativo,
é o plano de execução real.

**A costura entre os dois mundos** está na classe `TradutorRadar`: ela
mapeia a fonte bronze do dbt para o asset `camada_bronze` do Dagster.
Sem ela, a interface mostraria dois grafos desconexos; com ela, o
fluxo aparece contínuo do download da ANP até o mart final.

**O detalhe que mais ensina** neste arquivo é o dos caminhos: o
Dagster executa o dbt com diretório de trabalho dentro de `dbt/`, o
que quebraria os caminhos relativos pensados para execução manual da
raiz. A solução é o orquestrador exportar `DUCKDB_PATH` e
`BRONZE_GLOB` como caminhos absolutos antes de qualquer chamada.
Problemas de diretório de trabalho são dos mais comuns em produção;
saber explicar este aqui vale por um capítulo de curso.

### Como

```powershell
dagster dev -f orquestracao/definitions.py
```

Abra `http://localhost:3000`, vá em Assets, selecione tudo e clique em
Materialize. Para demonstração offline:

```powershell
$env:MODO_INGESTAO = "amostra"
dagster dev -f orquestracao/definitions.py
```

### Como validar

Na interface, o grafo deve mostrar a cadeia completa:
`arquivos_anp_brutos` até `mart_resumo_semanal`, sem nós soltos. Após
materializar, cada asset fica verde com o horário da última execução.
Este é o momento de capturar as telas para o portfólio (grafo de
linhagem e execução bem sucedida são as duas imagens que mais
comunicam o projeto).

---

## Fase 7. Integração contínua

### O que

`.github/workflows/ci.yml` roda a cada push e pull request: lint do
Python (ruff), ingestão em modo amostra e `dbt build` completo. Se
qualquer teste falhar, o merge fica bloqueado.

### Por que

CI transforma qualidade de intenção em regra. A peça que faz isso
funcionar são os dados de exemplo versionados: a CI não pode depender
de baixar arquivo de portal governamental (lento, instável, muda de
URL), então o pipeline roda contra fixtures que reproduzem os
problemas reais da fonte. É o mesmo princípio de testes com massa de
dados controlada usado em qualquer software sério.

### Como

Depois de criar o repositório no GitHub:

```powershell
git init
git add .
git commit -m "Plataforma de dados da Série Histórica da ANP"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/radar-precos-combustiveis.git
git push -u origin main
```

Para viver o fluxo completo de trabalho com PR (recomendado, mesmo
sozinho):

```powershell
git checkout -b ajuste-teste
# faça uma mudança pequena, por exemplo no README
git add . ; git commit -m "Ajuste no README" ; git push -u origin ajuste-teste
```

Abra o pull request no GitHub e observe a CI executar antes do merge.

### Como validar

Na aba Actions do repositório, o workflow `ci` deve aparecer verde. O
selo no topo do README (troque `SEU_USUARIO` pelo seu usuário) passa a
refletir o estado real do pipeline.

---

## Fase 8. Documentação viva no GitHub Pages

### O que

`.github/workflows/docs.yml` gera a documentação do dbt (`dbt docs
generate`) a cada push na main e publica no GitHub Pages: um site
navegável com a descrição de cada modelo, cada coluna, cada teste e o
grafo de linhagem interativo.

### Por que

Documentação que se gera sozinha a partir do código nunca fica
desatualizada. Para recrutador e gestor técnico, é uma URL clicável
que prova o projeto sem precisar clonar nada. Esse link vai no
portfólio e no LinkedIn.

### Como

No repositório do GitHub: Settings, depois Pages, e em Source escolha
"GitHub Actions". No próximo push na main, o site é publicado em
`https://SEU_USUARIO.github.io/radar-precos-combustiveis/`.

### Como validar

Abra a URL, clique em qualquer modelo e depois no ícone de grafo no
canto inferior direito para ver a linhagem completa.

---

## Fase 9. Dados reais e volumetria

### O que

Trocar a amostra pelos arquivos oficiais da ANP listados em
`ingestao/fontes.yml`: dois semestres completos mais os arquivos de
últimas 4 semanas, atualizados semanalmente.

### Por que

A amostra prova o código; o dado real prova a plataforma. Os arquivos
semestrais da ANP trazem centenas de milhares de linhas cada um, e é
neles que a escolha do DuckDB aparece: o build continua levando
segundos, não minutos.

Atenção a dois pontos práticos:

- URLs de portal governamental mudam. As de `fontes.yml` foram
  verificadas em agosto de 2026; se um download falhar com erro 404,
  confira a página oficial da Série Histórica e atualize o manifesto.
- Para ampliar o histórico, adicione semestres anteriores ao
  manifesto seguindo o mesmo padrão. A partir de 2022 os arquivos vêm
  em ZIP (use `tipo: zip`); antes disso, CSV direto.

### Como

```powershell
python ingestao/baixar_anp.py
python ingestao/para_bronze.py --modo real
dbt build --project-dir dbt --profiles-dir dbt
```

### Como validar

Anote os números da execução real (linhas ingeridas, tempo de build,
resultado dos testes) e atualize a seção de resultados do README com
eles. Resultado quantificado com número seu vale mais que qualquer
adjetivo.

---

## Fase 10. Publicação e narrativa

Checklist final antes de divulgar:

1. Substituir `SEU_USUARIO` no README (selo da CI), na exposure do dbt
   (`dbt/models/marts/_marts__modelos.yml`) e nos textos de
   `divulgacao/`.
2. CI verde na aba Actions.
3. GitHub Pages publicado com a documentação do dbt.
4. Duas capturas de tela do Dagster (grafo de linhagem e execução
   verde) salvas para o portfólio e o LinkedIn.
5. Números reais da fase 9 na seção de resultados do README.
6. Página do projeto adicionada ao portfólio (arquivo em
   `divulgacao/projeto-plataforma-dados.html`).
7. Posts do LinkedIn (rascunhos em `divulgacao/posts_linkedin.md`),
   publicados com pelo menos alguns dias de intervalo.

Sobre a narrativa: este projeto conversa com os outros dois do
portfólio sem repetir nenhum. O Aurora Alimentos responde "o que está
acontecendo" (BI descritivo com alertas), este responde "como garantir
que o dado que alimenta tudo é confiável e chega sozinho" (plataforma),
e o terceiro responderá "o que fazer a seguir" (preditivo e
prescritivo). Três perguntas, três projetos, uma história.

---

## Solução de problemas

**A ativação do venv falha no PowerShell.** Execute
`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
uma única vez e abra um terminal novo.

**`dbt build` reclama que não encontra o profile.** Os comandos deste
projeto sempre levam `--project-dir dbt --profiles-dir dbt` e são
executados da raiz do repositório. Conferir a pasta atual resolve a
maioria dos casos.

**O dbt não encontra os Parquet do bronze.** Rode antes
`python ingestao/para_bronze.py --modo amostra` (ou `--modo real`). O
staging lê os arquivos de `data/bronze/anp/`, que só existem após a
ingestão.

**Erro de arquivo em uso no warehouse (Windows).** O DuckDB permite um
escritor por vez. Feche outras conexões abertas (um `dagster dev`
esquecido, um cliente SQL) e rode de novo.

**Download da ANP falha com 404.** A URL mudou no portal. Abra a
página da Série Histórica, copie o link novo e atualize
`ingestao/fontes.yml`.

**A porta 3000 já está em uso.** `dagster dev -f
orquestracao/definitions.py -p 3001`.

**A CI falha só no GitHub.** Leia o log do passo que falhou na aba
Actions. Como a CI usa os dados de exemplo versionados, uma falha lá
quase sempre reproduz localmente com os mesmos três comandos do
workflow.
