import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json# Autenticar com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)

# Acessar planilha
sheet = client.open("HubspotIA").sheet1

adicionados = 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://blog.hubspot.com/")
    page.wait_for_selector("article")

    articles = page.query_selector_all("article")
    for article in articles:
        title_tag = article.query_selector("h3")
        if not title_tag:
            continue
        titulo = title_tag.inner_text().strip()
        print("🔎 Título encontrado:", titulo)

        if re.search(r"\b(IA|inteligência artificial|AI|machine learning|LLM)\b", titulo, re.IGNORECASE):
            link_tag = article.query_selector("a")
            link = link_tag.get_attribute("href") if link_tag else ""
            link = link if link.startswith("http") else "https://blog.hubspot.com" + link
            data = datetime.now().strftime("%Y-%m-%d")
            prompt = f"""Crie um post de LinkedIn com base nesse artigo da HubSpot: "{titulo}".

Objetivo: mostrar como profissionais de marketing podem aplicar esse conceito na prática.

Use um tom claro, sem jargão técnico, com até 2 emojis. Finalize com uma pergunta ou CTA para engajar a audiência.

Fonte: {link}"""
            sheet.append_row([data, titulo, link, "", prompt])
            adicionados += 1

    browser.close()

print(f"✅ {adicionados} post(s) adicionados à planilha.")
