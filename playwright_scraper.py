# Atualização do script para coletar todos os artigos da home do blog da HubSpot relacionados à IA
import os
import json
import base64
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

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
    page.wait_for_selector(".blog-post-card, article", timeout=30000)

    # Busca mais ampla por artigos na página
    elementos_artigo = page.query_selector_all(".blog-post-card, article")

    for artigo in elementos_artigo:
        try:
            h3 = artigo.query_selector("h3.blog-post-card-title a, h2 a")
            if not h3:
                continue
            titulo = h3.inner_text().strip()
            link = h3.get_attribute("href")
            link = link if link.startswith("http") else "https://br.hubspot.com" + link

            # Verifica palavras-chave tanto no título quanto no conteúdo do artigo
            if re.search(r"\b(IA|inteligência artificial|AI|machine learning|LLM)\b", titulo, re.IGNORECASE):
                if not artigo_ja_existe(titulo, dados_existentes):
                    print(f"🌐 Visitando artigo: {titulo}")
                    artigo_page = browser.new_page()
                    artigo_page.goto(link)
                    artigo_page.wait_for_timeout(5000)

                    paragrafos = artigo_page.query_selector_all("article p, .post-body p, main p")
                    texto_completo = ""
                    count = 0
                    for ptag in paragrafos:
                        try:
                            texto_completo += ptag.inner_text().strip() + " "
                            count += 1
                        except:
                            continue
                        if count >= 6:
                            break
                    artigo_page.close()

                    resumo = texto_completo.strip()
                    data_coleta = datetime.now().strftime("%Y-%m-%d")
                    sheet.append_row([data_coleta, titulo, link, resumo, ""])
                    print(f"✅ Adicionado com resumo: {titulo}")
                    adicionados += 1
        except Exception as e:
            print(f"⚠️ Erro ao processar artigo: {e}")

    browser.close()

print(f"📌 Total de artigos adicionados com resumo: {adicionados}")
