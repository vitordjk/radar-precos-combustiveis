# Registro de decisões técnicas

Cada decisão registra o contexto, as alternativas consideradas, a
escolha e o custo aceito. O objetivo é que qualquer pessoa (inclusive
em entrevista) consiga reconstituir o raciocínio, e não apenas ver o
resultado.

---

## Decisão 1. DuckDB como warehouse

**Contexto.** O projeto precisa de um motor analítico para as camadas
staging e marts, executável em qualquer máquina, sem custo.

**Alternativas.** PostgreSQL (já usado no projeto Aurora), BigQuery no
nível gratuito, DuckDB.

**Escolha.** DuckDB. É um motor colunar embutido: warehouse é um
arquivo, instalação é `pip install`, leitura de Parquet é nativa e o
desempenho analítico em uma máquina só supera com folga um banco
transacional. Repetir o PostgreSQL não agregaria nada novo ao
portfólio; o DuckDB posiciona o projeto na geração atual de
ferramentas analíticas.

**Custo aceito.** Sem acesso concorrente de vários usuários e sem a
experiência de operar um warehouse gerenciado em nuvem. O primeiro é
irrelevante para o caso de uso; o segundo está mapeado como evolução:
o dbt torna a migração para BigQuery uma troca de adaptador e de
profile, com os modelos praticamente intactos.

---

## Decisão 2. Dagster em vez de Airflow

**Contexto.** O pipeline precisa de agendamento, visibilidade de
execução e integração de primeira classe com o dbt.

**Alternativas.** Airflow (padrão de mercado consolidado), Dagster,
agendador do sistema operacional (cron ou Task Scheduler).

**Escolha.** Dagster. O modelo de assets declara o que cada dado é e
de que dados depende, e a integração `dagster-dbt` importa cada modelo
do dbt como um asset individual, com linhagem contínua da ingestão ao
mart. Roda leve em uma máquina local, sem os serviços auxiliares que o
Airflow exige.

**Custo aceito.** O Airflow ainda aparece mais em vagas no Brasil. Os
conceitos, porém, transferem diretamente: DAG, dependência,
agendamento, reexecução e observabilidade existem nos dois, e a
diferença de modelo (tarefa versus asset) é justamente um bom assunto
de entrevista.

---

## Decisão 3. Bronze como Parquet imutável, tudo em texto

**Contexto.** Onde e como guardar o dado bruto da ANP.

**Alternativas.** Carregar o CSV direto em tabelas tipadas do banco;
guardar o CSV original como bronze; converter para Parquet mantendo
tudo como texto.

**Escolha.** Parquet com todas as colunas originais em texto, mais
metadados de linhagem (`_arquivo_origem`, `_ingerido_em`). Tipar cedo
demais esconde erros: se a fonte mandar uma data impossível, a falha
deve acontecer no staging, onde é visível e testável, e não na carga.
Parquet em vez de CSV pela compressão e pela velocidade de leitura
colunar no DuckDB.

**Custo aceito.** Um passo a mais de conversão e armazenamento em
dobro do bruto (CSV baixado mais Parquet). Aceitável pela ordem de
grandeza dos arquivos e pelo ganho de auditabilidade.

---

## Decisão 4. Dados de exemplo versionados para a integração contínua

**Contexto.** A CI precisa executar o pipeline inteiro a cada pull
request, mas depender de download do portal da ANP tornaria o teste
lento e instável, e URLs de governo mudam.

**Alternativas.** CI que baixa dados reais; CI que testa apenas
sintaxe (`dbt parse`); fixtures versionadas no formato exato da fonte.

**Escolha.** Fixtures em `dados_exemplo/`, geradas no formato oficial
da ANP com os problemas reais reproduzidos de propósito: encoding
Latin-1, CNPJ com máscara inconsistente, preços inválidos, duplicatas,
valor de compra ausente. A CI valida o comportamento completo do
pipeline, incluindo os testes de qualidade, de forma determinística e
em segundos.

**Custo aceito.** As fixtures precisam ser mantidas se o formato da
ANP mudar. O custo é baixo e o próprio pipeline acusa a mudança (a
execução real falharia de forma visível).

---

## Decisão 5. Docker opcional, não obrigatório

**Contexto.** Reprodutibilidade do ambiente de execução.

**Alternativas.** Tudo dentro de contêineres desde o início; ambiente
virtual Python como caminho principal com Docker documentado como
opção.

**Escolha.** Ambiente virtual como caminho principal. A pilha escolhida
(DuckDB embutido, Dagster local) não tem serviços externos para
isolar, então o contêiner resolveria um problema que o projeto não
tem, ao custo de fricção para quem clona. O `Dockerfile` e o
`docker-compose.yml` existem e funcionam para quem preferir, e a
reprodutibilidade real vem da CI: o pipeline inteiro roda em uma
máquina limpa do GitHub a cada alteração.

**Custo aceito.** Nenhum relevante. Se a evolução do projeto trouxer
serviços externos (um Postgres, um agendador remoto), a decisão deve
ser revisitada.

---

## Decisão 6. Bronze reflete um único modo por vez

**Contexto.** A ingestão opera em dois modos: amostra (dados de exemplo,
para CI e primeiro contato) e real (arquivos da ANP). Na primeira
execução com dados reais, a leitura dos resultados acusou 2.831
coletas de 2023 e 2024, período que a fonte configurada não cobria.
Eram os Parquet da amostra, carregados antes na mesma pasta bronze e
lidos pelo dbt junto com os reais.

**Alternativas.** Pastas de bronze separadas por modo, com o dbt
apontando para a certa via variável de ambiente; limpeza dos Parquet do
outro modo ao trocar; deixar por conta de quem executa.

**Escolha.** Limpeza automática na troca de modo. O estado da ingestão
já registrava a qual modo cada arquivo pertencia (prefixo da chave), o
que tornou a limpeza segura e explicável em uma mensagem: "Bronze
limpo: N arquivo(s) do modo X removido(s)". Pastas separadas exigiriam
que quem executa lembrasse de trocar também a variável do dbt, um
segundo ponto de falha para resolver o mesmo problema.

**Custo aceito.** Trocar de modo reprocessa o bronze inteiro daquele
modo (o hash dos arquivos continua evitando redownload). É barato e
raro: em operação, o modo real fica fixo.
