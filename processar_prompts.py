# -*- coding: utf-8 -*-
"""
Processa a planilha e cria "Prompt personalizado" para linhas com "Resumo".

Env obrigatórios:
  GSHEETS_KEY_B64
  OPENAI_API_KEY

Env opcionais:
  SHEET_NAME=HubspotIA
  SHEET_TAB=dados
  MODEL=gpt-4o-mini
"""
import os, json, base64, time, gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI

# ---------- Google Sheets ----------
def _ws():
    b64 = os.getenv("GSHEETS_KEY_B64")
    if not b64: raise ValueError("❌ GSHEETS_KEY_B64 não definido.")
    creds = json.loads(base64.b64decode(b64).decode("utf-8"))
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(
        creds, ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    ))
    sh = client.open(os.getenv("SHEET_NAME","HubspotIA"))
    tab = os.getenv("SHEET_TAB","dados")
    return sh.worksheet(tab)

def _header(ws):
    head = ws.row_values(1)
    idx = {name: i+1 for i,name in enumerate(head)}
    if "Prompt personalizado" not in idx:
        head.append("Prompt personalizado")
        ws.update([head], "1:1")
        return _header(ws)
    return head, idx

# ---------- OpenAI ----------
def _client():
    key = os.getenv("OPENAI_API_KEY")
    if not key: raise ValueError("❌ OPENAI_API_KEY não definido.")
    return OpenAI(api_key=key), os.getenv("MODEL","gpt-4o-mini")

def _gen(client, model, resumo):
    user = "\n".join([
        "Crie um post para LinkedIn com tom provocador e autoridade técnica sobre o tema.",
        "", f"Resumo do artigo:\n\"{resumo}\"",
        "", "O texto deve:",
        "– Começar com uma frase que aponte um erro comum no mercado",
        "– Mostrar o contraste entre a prática superficial e a prática correta",
        "– Incluir um exemplo real (ou simulado) que mostre como isso se aplica na prática",
        "– Terminar com uma provocação aberta, convidando ao debate",
        "", "Direto, frases curtas, até 1300 caracteres, com hashtags específicas no final."
    ])
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role":"system","content":"Você é um estrategista de marketing experiente e direto."},
            {"role":"user","content":user}
        ],
        temperature=0.7,max_tokens=500
    )
    return resp.choices[0].message.content.strip()

# ---------- Main ----------
def main():
    ws = _ws()
    head, idx = _header(ws)
    col_r, col_p = idx.get("Resumo"), idx.get("Prompt personalizado")
    if not col_r: raise SystemExit("❌ Coluna 'Resumo' não encontrada.")

    rows = ws.get_all_values()
    if len(rows)<=1: print("ℹ️ Nenhuma linha para processar."); return

    client, model = _client()
    updates=[]; proc=skip=0
    for r in range(2,len(rows)+1):
        resumo = (rows[r-1][col_r-1] if len(rows[r-1])>=col_r else "").strip()
        prompt = (rows[r-1][col_p-1] if len(rows[r-1])>=col_p else "").strip()
        if not resumo or len(resumo)<50 or prompt: skip+=1; continue
        try:
            texto=_gen(client,model,resumo)
            updates.append({"range":f"{gspread.utils.rowcol_to_a1(r,col_p)}","values":[[texto]]})
            proc+=1
            if len(updates)>=5:
                ws.batch_update([{"range":u["range"],"values":u["values"]} for u in updates]); updates.clear()
                time.sleep(0.3)
        except Exception as e: print(f"❌ Erro na linha {r}: {e}")
    if updates: ws.batch_update([{"range":u["range"],"values":u["values"]} for u in updates])
    print(f"✅ Processadas: {proc} | ⏭️ Ignoradas: {skip}")

if __name__=="__main__": main()
