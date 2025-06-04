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

# Função para verificar se o artigo já está na planilha
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
    page.wait_for_selector("article, h3, .blog-post-card")

    # Coletar múltiplas seções de artigos
    blocos = page.query_selector_all("article, .blog-post-card, section h3, div h3")

    for bloco in blocos:
        try:
            titulo = bloco.inner_text().strip()
        except:
            continue
        if not titulo:
            continue

        if re.search(r"\b(IA|inteligência artificial|AI|machine learning|LLM)\b", titulo, re.IGNORECASE):
            link_tag = bloco.query_selector("a")
            link = link_tag.get_attribute("href") if link_tag else ""
            link = link if link.startswith("http") else "https://br.hubspot.com" + link

            resumo = ""
            parent = bloco.evaluate_handle("node => node.parentElement")
            if parent:
                try:
                    p_tag = parent.query_selector("p")
                    resumo = p_tag.inner_text().strip() if p_tag else ""
                except:
                    resumo = ""

            if not artigo_ja_existe(titulo, dados_existentes):
                data = datetime.now().strftime("%Y-%m-%d")
                sheet.append_row([data, titulo, link, resumo, ""])
                print(f"✅ Adicionado: {titulo}")
                adicionados += 1

    browser.close()

print(f"📌 Total de artigos adicionados: {adicionados}")
