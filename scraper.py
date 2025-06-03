import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

# Autenticar com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)

# Acessar planilha
sheet = client.open("HubspotIA").sheet1

# Scraping do blog da HubSpot
url = "https://blog.hubspot.com/marketing"
resposta = requests.get(url)
soup = BeautifulSoup(resposta.text, "html.parser")
cards = soup.select("div.blog-card")

adicionados = 0

for card in cards:
    titulo_tag = card.select_one("a.blog-card__title")
    if not titulo_tag:
        continue

    titulo = titulo_tag.text.strip()
    link = "https://blog.hubspot.com" + titulo_tag['href']

    if re.search(r"\b(IA|inteligência artificial|AI)\b", titulo, re.IGNORECASE):
        desc_tag = card.select_one("p.blog-card__description")
        resumo = desc_tag.text.strip() if desc_tag else ""
        data = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""Crie um post de LinkedIn com base nesse artigo da HubSpot: "{titulo}".

Objetivo: mostrar como profissionais de marketing podem aplicar esse conceito na prática.

Use um tom claro, sem jargão técnico, com até 2 emojis. Finalize com uma pergunta ou CTA para engajar a audiência.

Fonte: {link}"""

        sheet.append_row([data, titulo, link, resumo, prompt])
        adicionados += 1

print(f"✅ {adicionados} post(s) adicionados à planilha.")
