# Script para inspecionar cada div de artigo e verificar presença de palavras-chave relacionadas à IA
import os
import json
import base64
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Palavras-chave alvo
PALAVRAS_CHAVE = ["IA", "inteligência artificial", "AI", "machine learning", "LLM"]

# ✅ Decodificar credenciais do Google Sheets
credentials_b64 = os.getenv("GSHEETS_KEY_B64")
if not credentials_b64:
    raise ValueError("❌ GSHEETS_KEY_B64 não está definido.")

try:
    credentials_json = base64.b64decode(credentials_b64).decode("utf-8")
    credentials_dict = json.loads(credentials_json)
except Exception as e:
    raise ValueError(f"❌ Erro ao decodificar GSHEETS_KEY_B64: {e}")

# ✅ Autenticar com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
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

    elementos_artigo = page.query_selector_all(".blog-post-card, article")
    print(f"🔍 Total de blocos de artigos encontrados: {len(elementos_artigo)}")

    for idx, artigo in enumerate(elementos_artigo):
        try:
            h3 = artigo.query_selector("h3.blog-post-card-title a, h2 a")
            if not h3:
                continue
            titulo = h3.inner_text().strip()
            link = h3.get_attribute("href")
            link = link if link.startswith("http") else "https://br.hubspot.com" + link

            if artigo_ja_existe(titulo, dados_existentes):
                print(f"⏩ Ignorando (já existe): {titulo}")
                continue

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

            if any(re.search(rf"\b{re.escape(p)}\b", texto_completo, re.IGNORECASE) for p in PALAVRAS_CHAVE):
                resumo = texto_completo.strip()
                data_coleta = datetime.now().strftime("%Y-%m-%d")
                sheet.append_row([data_coleta, titulo, link, resumo, ""])
                print(f"✅ Adicionado com resumo: {titulo}")
                adicionados += 1
            else:
                print(f"❌ Ignorado: não contém palavras-chave no conteúdo.")

        except Exception as e:
            print(f"⚠️ Erro ao processar artigo #{idx + 1}: {e}")

    browser.close()

print(f"\n📌 Total de artigos adicionados com resumo: {adicionados}")
