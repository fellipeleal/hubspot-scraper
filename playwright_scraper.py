# -*- coding: utf-8 -*-
"""
Scraper (Playwright) 
Env vars esperadas:
  GSHEETS_KEY_B64  -> credenciais do service account (base64)
  SHEET_NAME       -> nome da planilha (ex.: "HubspotIA")
  SHEET_TAB        -> aba/worksheet (ex.: "dados")
  BLOG_URL         -> URL de listagem (ex.: "https://blog.hubspot.com/marketing")
  KEYWORDS         -> opcional, separadas por vírgula (default embutido)
"""
import os
import re
import time
import json
import base64
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from contextlib import contextmanager
from typing import List, Dict, Tuple, Set

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# -------- Config --------
DEFAULT_KEYWORDS = [
    "IA", "inteligência artificial", "inteligencia artificial",
    "AI", "A.I.", "machine learning", "aprendizado de máquina",
    "aprendizagem automática", "LLM", "GenAI", "modelos de linguagem",
    "large language model", "modelo de linguagem"
]

KW_ENV = os.getenv("KEYWORDS")
PALAVRAS_CHAVE = [k.strip() for k in KW_ENV.split(",")] if KW_ENV else DEFAULT_KEYWORDS

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# regex: variantes e tolerância a pontuação colada (ex.: IA:)
KW_REGEX = re.compile(
    r"(\\bI\\.?A\\b|\\bA\\.?I\\.?\\b|\\bAI\\b|intelig[eê]ncia\\s+artificial|machine\\s+learning|\\bLLM\\b|GenAI|modelos?\\s+de\\s+linguagem|large\\s+language\\s+model|aprendiza[gd]o\\s+de\\s+m[áa]quina|aprendizagem\\s+autom[áa]tica)",
    re.IGNORECASE
)

# -------- Helpers --------
def decode_gsheets_key() -> Dict:
    b64 = os.getenv("GSHEETS_KEY_B64")
    if not b64:
        raise RuntimeError("GSHEETS_KEY_B64 não definido")
    return json.loads(base64.b64decode(b64).decode("utf-8"))

def open_sheet():
    creds = decode_gsheets_key()
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope))
    sheet_name = os.getenv("SHEET_NAME", "HubspotIA")
    tab_name = os.getenv("SHEET_TAB", "dados")
    sh = client.open(sheet_name)
    ws = sh.worksheet(tab_name)
    return ws

def normalize_url(u: str) -> str:
    try:
        parsed = urlparse(u)
        # remove tracking params
        qs = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith(("utm_", "hss_", "hs_"))]
        new_query = urlencode(qs)
        clean = parsed._replace(query=new_query, fragment="")
        return urlunparse(clean).rstrip("/").lower()
    except Exception:
        return u.strip().rstrip("/").lower()

def get_headers(ws) -> Tuple[Dict[str, int], List[str]]:
    """Retorna mapeamento 'header_normalizado' -> índice (1-based) e a linha de cabeçalho original."""
    header = ws.row_values(1) or []
    norm = {}
    for idx, name in enumerate(header, start=1):
        key = name.strip().lower()
        key = key.replace("á", "a").replace("ã", "a").replace("â", "a").replace("é","e").replace("ê","e")
        key = key.replace("í","i").replace("ó","o").replace("ô","o").replace("ú","u").replace("ç","c")
        norm[key] = idx
    return norm, header

def ensure_columns(ws, header_map, header_row):
    wanted = ["titulo", "link", "data_captura", "resumo", "prompt personalizado"]
    added = False
    for col in wanted:
        if not any(col in k for k in header_map.keys()):
            header_row.append(col.capitalize() if col != "prompt personalizado" else "Prompt personalizado")
            added = True
    if added:
        ws.update("1:1", [header_row])
        return get_headers(ws)
    return header_map, header_row

def load_existing(ws, header_map) -> Tuple[Set[str], Set[str]]:
    # Identify columns
    url_col = None
    title_col = None
    for k, idx in header_map.items():
        if "link" in k or k == "url":
            url_col = idx
        if "titulo" in k or "título" in k:
            title_col = idx
    urls = set()
    titles = set()
    if url_col or title_col:
        values = ws.get_all_values()
        for r in values[1:]:
            if url_col and len(r) >= url_col and r[url_col-1].strip():
                urls.add(normalize_url(r[url_col-1]))
            if title_col and len(r) >= title_col and r[title_col-1].strip():
                titles.add(r[title_col-1].strip().lower())
    return urls, titles

def extract_links_from_listing(page) -> List[str]:
    # Busca links “de post” comuns em listagens de blog
    selectors = [
        "a[href*='/blog/']",
        "article a[href]",
        ".blog-post-card a[href]",
        "h2 a[href], h3 a[href]",
    ]
    hrefs = set()
    for sel in selectors:
        for a in page.query_selector_all(sel):
            href = a.get_attribute("href") or ""
            if href.startswith("#"):
                continue
            if href.startswith("/"):
                origin = page.evaluate("() => location.origin")
                href = origin + href
            if "hubspot" in href:  # heurística simples para o domínio
                hrefs.add(href)
    return list(hrefs)

def text_contains_keywords(text: str) -> bool:
    if not text:
        return False
    if KW_REGEX.search(text):
        return True
    # fallback: procura cada palavra-chave individual (casefold)
    t = text.casefold()
    return any(k.casefold() in t for k in PALAVRAS_CHAVE)

@contextmanager
def browser_context(pw):
    browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
    context = browser.new_context(user_agent=UA, ignore_https_errors=True, viewport={"width":1366, "height":768})
    try:
        yield context
    finally:
        context.close()
        browser.close()

def main():
    blog_url = os.getenv("BLOG_URL")
    if not blog_url:
        raise RuntimeError("BLOG_URL não definido")
    ws = open_sheet()
    header_map, header_row = get_headers(ws)
    header_map, header_row = ensure_columns(ws, header_map, header_row)
    existing_urls, existing_titles = load_existing(ws, header_map)

    print(f"🔎 Palavras-chave: {PALAVRAS_CHAVE}")
    print(f"📄 Linhas existentes: URLs={len(existing_urls)} | Títulos={len(existing_titles)}")

    accepted, skipped = 0, 0

    with sync_playwright() as pw:
        with browser_context(pw) as ctx:
            page = ctx.new_page()
            try:
                page.goto(blog_url, wait_until="networkidle", timeout=45000)
            except PWTimeoutError:
                page.goto(blog_url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2000)

            # tentar carregar mais itens se existir botão
            for _ in range(3):
                more = page.query_selector("button:has-text('Load more'), .load-more, .hs-load-more")
                if not more:
                    break
                try:
                    more.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(1000)
                except Exception:
                    break

            links = extract_links_from_listing(page)
            print(f"🧭 Links encontrados na listagem: {len(links)}")

            # Processar links
            new_rows = []
            for href in links:
                url_norm = normalize_url(href)
                if url_norm in existing_urls:
                    skipped += 1
                    continue

                p = ctx.new_page()
                try:
                    p.goto(href, wait_until="networkidle", timeout=45000)
                except PWTimeoutError:
                    p.goto(href, wait_until="domcontentloaded", timeout=45000)
                    p.wait_for_timeout(1500)

                # Extrair título e metas
                title = (p.title() or "").strip()
                h1 = p.text_content("h1") or ""
                meta_desc = p.evaluate("""() => {
                    const m = document.querySelector('meta[name="description"]') || document.querySelector('meta[property="og:description"]');
                    return m ? m.content : '';
                }""") or ""

                header_text = " ".join([title, h1, meta_desc])

                # Corpo: pegar primeiros ~30 parágrafos e <li>
                elements = p.query_selector_all("article p, article li") or p.query_selector_all("main p, main li")
                body_parts = []
                for el in elements[:60]:  # até 60 blocos p/li
                    t = (el.text_content() or "").strip()
                    if t:
                        body_parts.append(t)
                body_text = "\n".join(body_parts)

                matched = text_contains_keywords(header_text) or text_contains_keywords(body_text)

                if not matched:
                    skipped += 1
                    p.close()
                    continue

                # Preferir h1 como título
                final_title = (h1.strip() or title).strip() or href
                row = {
                    "titulo": final_title,
                    "link": href,
                    "data_captura": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "resumo": "",
                    "prompt personalizado": ""
                }
                new_rows.append(row)
                # atualizar dedupe dinamicamente
                existing_urls.add(url_norm)
                existing_titles.add(final_title.lower())
                accepted += 1
                p.close()

            if new_rows:
                # Mapear colunas atuais
                header_map, header_row = get_headers(ws)
                col_index = {name.lower(): idx for idx, name in enumerate(header_row, start=1)}
                def col(name):
                    # busca por aproximação
                    name_l = name.lower()
                    for k, idx in col_index.items():
                        if name_l in k:
                            return idx
                    # fallback: append
                    header_row.append(name)
                    ws.update("1:1", [header_row])
                    return len(header_row)

                rows_to_append = []
                for r in new_rows:
                    line = [""] * len(header_row)
                    line[col("Título")-1] = r["titulo"]
                    line[col("Link")-1] = r["link"]
                    line[col("Data_captura")-1] = r["data_captura"]
                    line[col("Resumo")-1] = r["resumo"]
                    line[col("Prompt personalizado")-1] = r["prompt personalizado"]
                    rows_to_append.append(line)

                ws.append_rows(rows_to_append, value_input_option="RAW")
                print(f"✅ Novos posts adicionados: {len(rows_to_append)}")
            else:
                print("ℹ️ Nenhum novo post elegível encontrado.")

    print(f"📊 Aceitos: {accepted} | Ignorados: {skipped}")

if __name__ == "__main__":
    main()
