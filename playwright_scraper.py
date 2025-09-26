# -*- coding: utf-8 -*-
"""
Scraper HubSpot (Playwright) — compacto e otimizado

Cabeçalho fixo na aba: Data | Título | Link | Resumo | Prompt personalizado | Data_captura

Env obrigatórios:
  GSHEETS_KEY_B64
  SHEET_NAME=HubspotIA
  SHEET_TAB=dados
  BLOG_URL=https://blog.hubspot.com/marketing

Env opcionais:
  KEYWORDS=IA,inteligência artificial,AI,machine learning,LLM,GenAI
  MAX_LINKS=20
"""
import os, re, time, json, base64
from datetime import datetime
from contextlib import contextmanager
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ---------- Config ----------
HEADER = ["Data", "Título", "Link", "Resumo", "Prompt personalizado", "Data_captura"]
DEFAULT_KW = [
    "IA", "inteligência artificial", "inteligencia artificial",
    "AI", "A.I.", "machine learning", "LLM", "GenAI",
    "modelos de linguagem", "large language model",
    "aprendizado de máquina", "aprendizagem automática",
]
PALAVRAS_CHAVE = [s.strip() for s in os.getenv("KEYWORDS", ",".join(DEFAULT_KW)).split(",") if s.strip()]
MAX_LINKS = int(os.getenv("MAX_LINKS", "20"))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
KW_REGEX = re.compile(
    r"(\bI\.?A\b|\bA\.?I\.?\b|\bAI\b|intelig[eê]ncia\s+artificial|machine\s+learning|\bLLM\b|GenAI|modelos?\s+de\s+linguagem|large\s+language\s+model|aprendiza[gd]o\s+de\s+m[áa]quina|aprendizagem\s+autom[áa]tica)",
    re.IGNORECASE,
)

# ---------- Sheets ----------
def _creds_from_env() -> dict:
    b64 = os.getenv("GSHEETS_KEY_B64")
    if not b64:
        raise RuntimeError("GSHEETS_KEY_B64 não definido")
    return json.loads(base64.b64decode(b64).decode("utf-8"))

def open_ws():
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(
        _creds_from_env(), ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    ))
    sh = client.open(os.getenv("SHEET_NAME", "HubspotIA"))
    tab = os.getenv("SHEET_TAB", "dados")
    try:
        ws = sh.worksheet(tab)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=2000, cols=len(HEADER))
    # garante cabeçalho
    if ws.row_values(1) != HEADER:
        ws.update([HEADER], "1:1")
    return ws

def load_existing_urls(ws):
    vals = ws.get_all_values()
    if not vals or len(vals) < 2: return set()
    try:
        li = vals[0].index("Link")
    except ValueError:
        return set()
    return {normalize_url(r[li]) for r in vals[1:] if len(r) > li and r[li].strip()}

# ---------- Utils ----------
def normalize_url(u: str) -> str:
    try:
        pu = urlparse(u)
        qs = [(k, v) for k, v in parse_qsl(pu.query) if not k.lower().startswith(("utm_", "hss_", "hs_"))]
        return urlunparse(pu._replace(query=urlencode(qs), fragment="")).rstrip("/").lower()
    except Exception:
        return (u or "").strip().rstrip("/").lower()

def has_keywords(text: str) -> bool:
    if not text: return False
    return bool(KW_REGEX.search(text) or any(k.casefold() in text.casefold() for k in PALAVRAS_CHAVE))

def safe_txt(x): return (x or "").strip()

def extract_pub_date(p) -> str:
    # meta
    try:
        meta = p.evaluate("""() => {
          const g=s=>document.querySelector(s)?.getAttribute('content')||'';
          return {
            a:g('meta[property="article:published_time"]')||g('meta[name="article:published_time"]'),
            b:g('meta[property="og:pubdate"]')||g('meta[name="pubdate"]')||g('meta[name="publish-date"]'),
            c:g('meta[name="date"]')||g('meta[itemprop="datePublished"]')
          };
        }""") or {}
        for v in (meta.get("a"), meta.get("b"), meta.get("c")):
            if v:
                try: return datetime.fromisoformat(v.replace("Z","+00:00")).date().isoformat()
                except Exception: pass
    except Exception: pass
    # <time>
    dt = p.get_attribute("time[datetime]", "datetime")
    if dt:
        try: return datetime.fromisoformat(dt.replace("Z","+00:00")).date().isoformat()
        except Exception: pass
    # JSON-LD
    try:
        for s in p.query_selector_all('script[type="application/ld+json"]') or []:
            t = safe_txt(s.text_content()); 
            if not t: continue
            data = json.loads(t); objs = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for o in objs:
                if isinstance(o, dict) and o.get("@type") in ("Article","NewsArticle","BlogPosting"):
                    iso = o.get("datePublished") or o.get("dateCreated")
                    if iso:
                        return datetime.fromisoformat(iso.replace("Z","+00:00")).date().isoformat()
    except Exception: pass
    return datetime.utcnow().date().isoformat()

def build_summary(title, meta_desc, parts, max_chars=600):
    if safe_txt(meta_desc): return meta_desc.strip()[:max_chars]
    txt = " ".join([t for t in parts[:8] if safe_txt(t)]).strip() or safe_txt(title)
    return (txt[:max_chars-3] + "...") if len(txt) > max_chars else txt

# ---------- Playwright ----------
@contextmanager
def pw_context(pw):
    browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
    ctx = browser.new_context(user_agent=UA, ignore_https_errors=True, viewport={"width":1366, "height":768})
    # abortar mídia para acelerar
    ctx.route("**/*", lambda r, req: r.abort() if req.resource_type in {"image","media","font","stylesheet"} else r.continue_())
    try: yield ctx
    finally:
        ctx.close(); browser.close()

def listing_links(page):
    sels = ["a[href*='/blog/']", "article a[href]", ".blog-post-card a[href]", "h2 a[href], h3 a[href]"]
    seen, links = set(), []
    for s in sels:
        for a in page.query_selector_all(s):
            href = a.get_attribute("href") or ""
            if not href or href.startswith("#"): continue
            if href.startswith("/"): href = page.evaluate("() => location.origin") + href
            if "hubspot" not in href: continue
            n = normalize_url(href)
            if n in seen: continue
            seen.add(n); links.append(href)
    return links

# ---------- Main ----------
def main():
    blog_url = os.getenv("BLOG_URL")
    if not blog_url: raise RuntimeError("BLOG_URL não definido")

    ws = open_ws()
    existing = load_existing_urls(ws)
    print(f"🔎 Keywords: {PALAVRAS_CHAVE}")
    print(f"📄 URLs já registradas: {len(existing)}")

    accepted = skipped = 0
    new_rows = []

    with sync_playwright() as pw, pw_context(pw) as ctx:
        page = ctx.new_page()
        page.set_default_timeout(15000); page.set_default_navigation_timeout(15000)
        try: page.goto(blog_url, wait_until="domcontentloaded", timeout=15000)
        except PWTimeoutError: page.goto(blog_url, wait_until="domcontentloaded", timeout=10000)

        links = listing_links(page)[:MAX_LINKS]
        print(f"🧭 Links processados (cap {MAX_LINKS}): {len(links)}")

        for href in links:
            nurl = normalize_url(href)
            if nurl in existing: skipped += 1; continue

            p = ctx.new_page()
            p.set_default_timeout(15000); p.set_default_navigation_timeout(15000)
            try: p.goto(href, wait_until="domcontentloaded", timeout=15000)
            except PWTimeoutError:
                try: p.goto(href, wait_until="domcontentloaded", timeout=8000)
                except PWTimeoutError: skipped += 1; p.close(); continue

            title = safe_txt(p.title()); h1 = safe_txt(p.text_content("h1"))
            meta_desc = p.evaluate("""() => {
              const m = document.querySelector('meta[name="description"]') ||
                        document.querySelector('meta[property="og:description"]');
              return m ? m.content : '';
            }""") or ""

            els = p.query_selector_all("article p, article li") or p.query_selector_all("main p, main li")
            parts = [safe_txt(e.text_content()) for e in els[:60] if safe_txt(e.text_content())]

            if not (has_keywords(" ".join([title, h1, meta_desc])) or has_keywords("\n".join(parts))):
                skipped += 1; p.close(); continue

            row = {
                "Data": extract_pub_date(p),
                "Título": (h1 or title) or href,
                "Link": href,
                "Resumo": build_summary(h1 or title, meta_desc, parts),
                "Prompt personalizado": "",
                "Data_captura": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            new_rows.append(row); existing.add(nurl); accepted += 1; p.close()

    if new_rows:
        ws.append_rows([[r[c] for c in HEADER] for r in new_rows], value_input_option="RAW")
        print(f"✅ Novos posts adicionados: {len(new_rows)}")
    else:
        print("ℹ️ Nenhum novo post elegível encontrado.")

    print(f"📊 Aceitos: {accepted} | Ignorados: {skipped}")

if __name__ == "__main__":
    main()
