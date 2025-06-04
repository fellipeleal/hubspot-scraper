import os
import json
import base64
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Decodificar e salvar credenciais.json
credentials_b64 = os.getenv("GSHEETS_KEY_B64")
if not credentials_b64:
    raise ValueError("❌ GSHEETS_KEY_B64 não está definido.")

try:
    credentials_json = base64.b64decode(credentials_b64).decode("utf-8")
    json.loads(credentials_json)
except Exception as e:
    raise ValueError(f"❌ Erro ao decodificar GSHEETS_KEY_B64: {e}")

with open("credenciais.json", "w") as f:
    f.write(credentials_json)

# Autenticar com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)
sheet = client.open("HubspotIA").sheet1

def artigo_ja_existe(titulo, dados_existentes):
    for row in dados_existentes:
        if row["Título"].strip().lower() == titulo.strip().lower():
            return True
    return False

dados_existentes = sheet.get_all_records()
adicionados = 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://br.hubspot.com/blog")
    page.wait_for_selector(".blog-post-card", timeout=20000)

    artigos = page.query_selector_all(".blog-post-card")

    for artigo in artigos:
        try:
            h3 = artigo.query_selector("h3.blog-post-card-title a")
            if not h3:
                continue
            titulo = h3.inner_text().strip()
            link = h3.get_attribute("href")
            link = link if link.startswith("http") else "https://br.hubspot.com" + link

            if re.search(r"\b(IA|inteligência artificial|AI|machine learning|LLM)\b", titulo, re.IGNORECASE):
                if not artigo_ja_existe(titulo, dados_existentes):
                    data = datetime.now().strftime("%Y-%m-%d")
                    sheet.append_row([data, titulo, link, "", ""])
                    print(f"✅ Adicionado: {titulo}")
                    adicionados += 1
        except Exception as e:
            print(f"⚠️ Erro ao processar artigo: {e}")

    browser.close()

print(f"📌 Total de artigos adicionados: {adicionados}")
