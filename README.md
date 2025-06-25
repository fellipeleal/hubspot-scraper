# 🤖 Hubspot IA Agent

Automatize a geração de conteúdo para redes sociais a partir de artigos com Inteligência Artificial.  
Este projeto mostra, de forma prática, como IA + automação + scraping + planilhas podem gerar valor real no marketing digital.

## 📌 O que faz

- Acessa o blog da HubSpot 1x ao dia
- Identifica artigos sobre IA
- Lê até 6 parágrafos do conteúdo
- Resume o texto
- Gera um post com ChatGPT
- Escreve em uma planilha do Google Sheets

## 🧠 Tecnologias usadas

- Python 3.11
- Playwright (scraping)
- OpenAI API (ChatGPT)
- Google Sheets API
- GitHub Actions


## 📅 Execução automática com GitHub Actions

O projeto roda automaticamente todos os dias às 06h UTC.  
Você também pode rodar manualmente pela aba **Actions > Run workflow**.

## 📊 Diagnóstico

Use `diagnostico_planilha.py` para verificar o status da planilha:
- Quantos resumos foram capturados
- Quantos prompts foram gerados

## 🧾 Licença

MIT — sinta-se livre para estudar, adaptar e evoluir este projeto.
