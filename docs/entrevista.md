# Preparação para entrevista

Perguntas que este projeto tende a provocar, com o núcleo da resposta.
A ideia não é decorar frases, e sim dominar o raciocínio a ponto de
responder com suas palavras. Este arquivo pode ficar fora do
repositório público se você preferir (basta apagar antes do push ou
adicionar ao .gitignore).

---

**Por que DuckDB e não Spark ou um warehouse em nuvem?**

Dimensionamento honesto. A base da ANP tem centenas de milhares de
linhas por semestre; Spark existe para ordens de grandeza que exigem
distribuir processamento entre máquinas, e usá-lo aqui seria pagar
complexidade sem receber nada. O DuckDB processa esse volume em
segundos numa máquina comum. E a arquitetura não prende: como a
transformação está toda em dbt, migrar para BigQuery é trocar o
adaptador e o profile, com os modelos praticamente intactos. Saber
dimensionar a ferramenta ao problema é parte do trabalho.

**Por que Dagster e não Airflow?**

Modelo mental. O Airflow orquestra tarefas; o Dagster orquestra
assets, e um pipeline analítico é sobre o estado dos dados, não sobre
scripts que rodam. A integração dagster-dbt importa cada modelo como
um asset com linhagem própria, então a interface mostra o caminho
contínuo do download da ANP até o mart. Os conceitos transferem para o
Airflow sem atrito: DAG, dependências, agendamento, reexecução. Se a
empresa usa Airflow, a adaptação é de sintaxe, não de fundamento.

**Como você garante que rodar o pipeline duas vezes não duplica dados?**

Idempotência em duas camadas. Na ingestão, cada arquivo tem o hash
SHA-256 do conteúdo registrado; se o hash não mudou, o arquivo é
pulado. Na transformação, a deduplicação da camada intermediate é
determinística: para cada posto + produto + data, vence a linha com
timestamp de ingestão mais recente. Rodar mil vezes produz o mesmo
resultado que rodar uma.

**Como você lida com fontes que se sobrepõem?**

A ANP publica o consolidado semestral e, em paralelo, um arquivo com as
últimas 4 semanas que se sobrepõe a ele. Em vez de tentar evitar a
sobreposição na ingestão (frágil), o bronze aceita tudo e a regra de
resolução vive num único lugar testável: a intermediate. A chave
natural da coleta define o grão e o metadado de ingestão define o
desempate.

**O que acontece se a ANP mudar o formato do arquivo?**

Três linhas de defesa. A leitura do bronze usa `union_by_name`, que
tolera coluna nova ou ausente sem quebrar. Se uma coluna essencial
sumir ou mudar de nome, a tipagem do staging gera nulos e os testes de
não nulidade falham no build seguinte, apontando exatamente onde. E o
teste de taxa de exclusão acusa se a limpeza começar a descartar mais
que o histórico. O pipeline não promete sobreviver a qualquer mudança;
promete falhar de forma visível e localizada.

**Por que os testes têm severidades diferentes?**

Porque anomalia e violação são coisas distintas. Preço fora da faixa
plausível é violação: bloqueia o build, dado assim não pode chegar ao
consumo. Margem negativa é anomalia: existe de verdade (queima de
estoque, guerra de preço), então o teste avisa quando a proporção
passa de 5%, pedindo investigação sem parar a operação. Tratar tudo
como erro gera alarme falso e as pessoas param de olhar; tratar tudo
como aviso deixa dado ruim passar.

**Por que média não, e mediana sim, no resumo semanal?**

Preço de combustível tem cauda: poucos postos muito acima do mercado
puxam a média e distorcem a leitura. A mediana resiste a extremos. Os
quartis dão a faixa em que o mercado realmente opera. A escolha da
estatística é decisão de engenharia tanto quanto a escolha do banco.

**Como você testaria isso em um pipeline de produção de verdade?**

Exatamente como está na CI: dados de fixture versionados que
reproduzem os defeitos reais da fonte, pipeline completo executado a
cada pull request, merge bloqueado se qualquer teste falhar. A
diferença em produção seria acrescentar ambientes (dev e prod com
schemas ou bancos separados), alertas dos testes para um canal de
equipe e monitoramento de custo e duração das execuções.

**O que você faria diferente com mais tempo?**

Contratos de modelo formais (model contracts do dbt) nas marts,
materialização incremental na fato quando o histórico crescer para
muitos semestres, um ambiente de produção separado do de
desenvolvimento e a publicação do resumo semanal em uma camada de
consumo (uma API leve ou um painel). A lista curta e concreta importa:
saber o que falta é parte de saber o que se fez.
