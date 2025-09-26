# -*- coding: utf-8 -*-
"""
Processa a planilha e cria "Prompt personalizado" para linhas com "Resumo".
Compatível com:
  GSHEETS_KEY_B64 (obrigatório)
  OPENAI_API_KEY  (obrigatório)
  SHEET_NAME=HubspotIA
  SHEET_TAB=dados
  MODEL=gpt-4o-mini  (opcional; fallback gpt-3.5-turbo)

Fluxo:
- Lê a aba indicada
- Garante a coluna "Prompt personalizado"
- Para cada linha sem prompt e com resumo >= 50 chars, gera o texto e preenche
"""
import os, json, base64, time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI

# ---------- Google Sheets ----------
def _client_sheets():
    b64 = os.getenv("GSHEETS_KEY_B64")
    if not b64:
        raise ValueError("❌ GSHEETS_KEY_B64 não definido.")
    creds = json.loads(base64.b64decode(b64).decode("utf-8"))
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    return gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(creds, scope))

def _open_ws():
    sh = _client_sheets().open(os.getenv("SHEET_NAME", "HubspotIA"))
    tab = os.getenv("SHEET_TAB", "dados")
    try:
        return sh.worksheet(tab)
    except gspread.exceptions.WorksheetNotFound:
        raise SystemExit(f"❌ Aba '{tab}' não encontrada. Abas: {[w.title for w in sh.worksheets()]}")

def _header_map(ws):
    header = ws.row_values(1)
    idx = {name: i+1 for i, name in enumerate(header)}
    return header, idx

def _ensure_prompt_col(ws, header, idx):
    if "Prompt personalizado" in idx:
        return header, idx
    header.append("Prompt personalizado")
    ws.update([header], "1:1")
    return _header_map(ws)

# ---------- OpenAI ----------
def _client_oai():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("❌ OPENAI_API_KEY não definido.")
    return OpenAI(api_key=key), os.getenv("MODEL", "gpt-4o-mini") or "gpt-3.5-turbo"

def _gen_post(client, model, resumo):
    system = "Você é um estrategista de marketing experiente e direto."
    user = "\n".join([
        "Crie um post para LinkedIn com tom provocador e autoridade técnica sobre o tema.",
        "",
        "Resumo do artigo:",
        f"\"{resumo}\"",
        "",
        "O texto deve:",
        "– Começar com uma frase que aponte um erro comum no mercado",
        "– Mostrar o contraste entre a prática superficial e a prática correta",
        "– Incluir um exemplo real (ou simulado) que mostre como isso se aplica na prática",
        "– Terminar com uma provocação aberta, convidando ao debate",
        "",
        "Seja direto, com frases curtas. No máx. 1300 caracteres. Inclua hashtags específicas no final."
    ])
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.7,
        max_tokens=500,
    )
    return resp.choices[0].message.content.strip()

# ---------- Main ----------
def main():
    ws = _open_ws()
    header, idx = _header_map(ws)
    header, idx = _ensure_prompt_col(ws, header, idx)

    col_resumo = idx.get("Resumo")
    col_prompt = idx.get("Prompt personalizado")
    if not col_resumo:
        raise SystemExit("❌ Coluna 'Resumo' não encontrada na primeira linha da aba.")

    rows = ws.get_all_values()
    if len(rows) <= 1:
        print("ℹ️ Nenhuma linha para processar.")
        return

    client, model = _client_oai()
    updates = []
    processed = skipped = 0

    # enumerate a partir da 2ª linha (conteúdo)
    for r_idx in range(2, len(rows) + 1):
        row = rows[r_idx-1]
        resumo = (row[col_resumo-1] if len(row) >= col_resumo else "").strip()
        prompt = (row[col_prompt-1] if len(row) >= col_prompt else "").strip()

        if not resumo:
            skipped += 1; continue
        if len(resumo) < 50:
            print(f"⚠️ L{r_idx} ignorada: resumo curto.")
            skipped += 1; continue
        if prompt:
            skipped += 1; continue

        try:
            texto = _gen_post(client, model, resumo)
            updates.append({"range": f"{gspread.utils.rowcol_to_a1(r_idx, col_prompt)}",
                            "values": [[texto]]})
            processed += 1
            # flush a cada 5 para reduzir round-trips
            if len(updates) >= 5:
                ws.batch_update([{"range": u["range"], "values": u["values"]} for u in updates])
                updates.clear()
                time.sleep(0.3)
        except Exception as e:
            print(f"❌ Erro na linha {r_idx}: {e}")

    if updates:
        ws.batch_update([{"range": u["range"], "values": u["values"]} for u in updates])

    print(f"✅ Processadas: {processed} | ⏭️ Ignoradas: {skipped}")

if __name__ == "__main__":
    main()
