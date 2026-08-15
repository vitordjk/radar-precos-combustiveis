# Posts para o LinkedIn

Três rascunhos, pensados para publicação com alguns dias de intervalo.
Antes de publicar: substituir SEU_USUARIO nos links, anexar as imagens
indicadas e ajustar qualquer frase para a sua voz.

---

## Post 1. Apresentação do projeto

Sugestão de imagem: grafo de linhagem do Dagster (captura de tela da
interface, com o caminho completo do download ao mart).

---

Publiquei o segundo projeto do meu portfólio de dados: uma plataforma
completa construída sobre os dados abertos de preços de combustíveis
da ANP.

O primeiro projeto (Aurora Alimentos) responde "o que está acontecendo
no negócio". Este responde uma pergunta anterior, que costuma ficar
invisível: como garantir que o dado que alimenta as análises é
confiável e chega atualizado sem ninguém precisar lembrar de rodar
nada.

O que a plataforma faz:

Ingestão versionada dos arquivos da ANP, com comparação por hash para
nunca processar a mesma coisa duas vezes. Arquitetura em camadas
(bronze, staging, marts) com uma responsabilidade clara em cada uma.
Transformação em dbt com 29 testes de qualidade executados em todo
build. Orquestração com Dagster e agendamento semanal, alinhado à
publicação da ANP. Integração contínua que roda o pipeline inteiro a
cada alteração no código: se um teste falha, o merge não acontece.

O dado real da ANP é um bom professor: encoding que muda entre anos,
CNPJ com e sem máscara, decimal com vírgula, fontes que se sobrepõem
de propósito. Cada um desses problemas virou uma decisão de
engenharia documentada no repositório.

Código, documentação e o registro de decisões técnicas:
https://github.com/SEU_USUARIO/radar-precos-combustiveis

#engenhariadedados #analyticsengineering #dbt #dados

---

## Post 2. Três decisões de engenharia

Sugestão de imagem: diagrama de arquitetura (a figura da página do
portfólio) ou captura da documentação do dbt publicada.

---

Três decisões do meu projeto de plataforma de dados que valem mais que
a lista de ferramentas.

1. Bronze guarda tudo como texto. Nenhuma conversão de tipo na
entrada. Se a fonte mandar uma data impossível, ela chega intacta ao
bronze e a conversão falha no staging, onde é visível e testável.
Tipar cedo demais esconde erro; tipar no lugar certo transforma erro
em alerta.

2. Testes com severidades diferentes. Preço fora de faixa plausível é
erro e bloqueia o pipeline. Margem negativa é aviso: existe de verdade
no varejo de combustíveis, então o teste só acusa quando a proporção
foge do histórico. Tratar tudo como erro gera alarme falso e as
pessoas param de olhar. Tratar tudo como aviso deixa dado ruim passar.

3. A integração contínua roda contra dados de exemplo versionados no
repositório, que reproduzem os defeitos reais da fonte: Latin-1,
duplicatas, preços inválidos. O pipeline inteiro executa a cada pull
request em segundos, sem depender de portal externo no ar.

A pilha (DuckDB, dbt, Dagster, GitHub Actions) está no repositório,
junto com o registro do que foi descartado e por quê:
https://github.com/SEU_USUARIO/radar-precos-combustiveis

#engenhariadedados #dbt #qualidadededados

---

## Post 3. O que os dados sujos me ensinaram

Sugestão de imagem: captura da documentação do dbt no GitHub Pages
(página de um modelo com descrição e testes visíveis).

---

Passei as últimas semanas trabalhando com um dos conjuntos de dados
públicos mais usados do Brasil: a série histórica de preços de
combustíveis da ANP. Algumas lições que levo para qualquer projeto.

A fonte não está errada, ela é assim. O valor de compra vem vazio na
maior parte das coletas. Não é defeito para consertar: é a natureza do
dado, e o modelo precisa dizer isso com clareza (margem nula quando
não há como calcular, nunca margem inventada).

Sobreposição proposital exige regra explícita. A ANP publica o
consolidado do semestre e, em paralelo, as últimas 4 semanas. Os dois
se sobrepõem. A resposta não é evitar a sobreposição na entrada, é ter
uma regra de deduplicação determinística num único lugar, testada.

Documentar a decisão vale tanto quanto o código. O repositório tem um
registro com as cinco decisões centrais do projeto, cada uma com as
alternativas descartadas e o custo aceito. É o documento que eu
gostaria de encontrar em todo projeto que herdei na vida.

Repositório completo, com guia de reprodução passo a passo:
https://github.com/SEU_USUARIO/radar-precos-combustiveis

#dados #engenhariadedados #dadosabertos
