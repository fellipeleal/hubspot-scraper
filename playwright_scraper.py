import os
import json
import base64
from datetime import datetime
import re
from playwright.sync_api import sync_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

credentials_b64 = os.getenv("GSHEETS_KEY_B64")
if not credentials_b64:
    raise ValueError("❌ GSHEETS_KEY_B64 não está definido. Verifique os GitHub Secrets.")

try:
    credentials_json = base64.b64decode(credentials_b64).decode("utf-8")
    json.loads(credentials_json)
except Exception as e:
    raise ValueError(f"❌ Erro ao decodificar GSHEETS_KEY_B64: {e}")

with open("credenciais.json", "w") as f:
    f.write(credentials_json)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)
sheet = client.open("HubspotIA").sheet1

adicionados = 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://br.hubspot.com/blog")
    page.wait_for_selector("article")

    articles = page.query_selector_all("article")
    for article in articles:
        title_tag = article.query_selector("h3")
        if not title_tag:
            continue
        titulo = title_tag.inner_text().strip()
        if re.search(r"\b(IA|inteligência artificial|AI|machine learning|LLM)\b", titulo, re.IGNORECASE):
            link_tag = article.query_selector("a")
            link = link_tag.get_attribute("href") if link_tag else ""
            link = link if link.startswith("http") else "https://br.hubspot.com" + link

            desc_tag = article.query_selector("p")
            resumo = desc_tag.inner_text().strip() if desc_tag else ""
            data = datetime.now().strftime("%Y-%m-%d")
            sheet.append_row([data, titulo, link, resumo, ""])
            adicionados += 1
    browser.close()

print(f"✅ {adicionados} post(s) adicionados à planilha.")
