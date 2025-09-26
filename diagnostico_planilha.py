import os
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Credenciais via env (base64) ---
credentials_b64 = os.getenv("GSHEETS_KEY_B64")
if not credentials_b64:
    raise ValueError("❌ Variável 'GSHEETS_KEY_B64' não encontrada.")

try:
    credentials = json.loads(base64.b64decode(credentials_b64).decode("utf-8"))
except Exception as e:
    raise ValueError(f"❌ Erro ao decodificar credenciais: {e}")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope))

# --- Planilha e aba vindas do ambiente (com defaults) ---
sheet_name = os.getenv("SHEET_NAME", "HubspotIA")
tab_name   = os.getenv("SHEET_TAB", "dados")

sh = client.open(sheet_name)
try:
    ws = sh.worksheet(tab_name)
except gspread.exceptions.WorksheetNotFound:
    raise SystemExit(f"❌ Aba '{tab_name}' não encontrada na planilha '{sheet_name}'. "
                     f"Abas disponíveis: {[w.title for w in sh.worksheets()]}")

# --- Leitura de dados ---
# get_all_records() ignora a linha de header e linhas totalmente vazias
dados = ws.get_all_records()
header = ws.row_values(1)

# Localiza colunas por nome (tolerante a ausência)
def col_idx(nome):
    return header.index(nome) + 1 if nome in header else None

col_resumo = col_idx("Resumo")
col_prompt = col_idx("Prompt personalizado")

total = len(dados)
com_resumo = sum(1 for r in dados if (r.get("Resumo") or "").strip())
com_prompt = sum(1 for r in dados if (r.get("Prompt personalizado") or "").strip())
prontos_para_processar = sum(1 for r in dados
                             if (r.get("Resumo") or "").strip() and not (r.get("Prompt personalizado") or "").strip())

print("📊 Diagnóstico da planilha", sheet_name)
print(f"🗂️ Aba analisada: {ws.title}")
print(f"Total de linhas (exceto cabeçalho): {total}")
print(f"Linhas com resumo preenchido: {com_resumo}")
print(f"Linhas com prompt já preenchido: {com_prompt}")
print(f"Linhas prontas para processamento: {prontos_para_processar}")

if col_resumo is None:
    print("⚠️ A coluna 'Resumo' não foi encontrada.")
if col_prompt is None:
    print("⚠️ A coluna 'Prompt personalizado' não foi encontrada.")
