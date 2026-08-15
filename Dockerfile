# Execução opcional em contêiner. O caminho principal do projeto é o
# ambiente virtual local (ver docs/decisoes.md, decisão 5), mas este
# Dockerfile garante reprodutibilidade em qualquer máquina com Docker.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN dbt deps --project-dir dbt --profiles-dir dbt

EXPOSE 3000

CMD ["dagster", "dev", "-f", "orquestracao/definitions.py", "-h", "0.0.0.0", "-p", "3000"]
