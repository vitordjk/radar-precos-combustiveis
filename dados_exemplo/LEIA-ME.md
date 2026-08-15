# Dados de exemplo

Arquivos no formato exato da Série Histórica da ANP, com valores
fictícios gerados para permitir execução offline e na integração
contínua, onde download externo não é confiável nem desejável.

A sujeira presente é intencional e espelha problemas reais da fonte:

- `ca-2023-02-amostra.csv` está em Latin-1 com CRLF (padrão de anos antigos da ANP)
- `ca-2024-01-amostra.csv` está em UTF-8
- CNPJs aparecem com máscara, com espaços ao redor e sem máscara
- Municípios com espaços extras e em minúsculas
- Preços de venda negativos e zerados (devem ser filtrados pelo pipeline)
- Valor de compra maior que o de venda em algumas linhas (margem negativa, deve gerar aviso)
- Linhas exatamente duplicadas (devem ser deduplicadas)
- Valor de compra ausente na maior parte das linhas, como na fonte real
