import os
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials

credentials_b64 = os.getenv("GSHEETS_KEY_B64")
if not credentials_b64:
    raise ValueError("❌ Variável 'GSHEETS_KEY_B64' não encontrada.")

try:
    credentials_json = base64.b64decode(credentials_b64).decode("utf-8")
    json.loads(credentials_json)
except Exception as e:
    raise ValueError(f"❌ Erro ao decodificar credenciais: {e}")

with open("credenciais.json", "w") as f:
    f.write(credentials_json)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)

sheet = client.open("HubspotIA").sheet1
dados = sheet.get_all_records()

header = sheet.row_values(1)
col_resumo = header.index("Resumo") + 1 if "Resumo" in header else None
col_prompt = header.index("Prompt personalizado") + 1 if "Prompt personalizado" in header else None

total = len(dados)
com_resumo = 0
com_prompt = 0
prontos_para_processar = 0

for row in dados:
    resumo = row.get("Resumo", "").strip()
    prompt = row.get("Prompt personalizado", "").strip()

    if resumo:
        com_resumo += 1
    if prompt:
        com_prompt += 1
    if resumo and not prompt:
        prontos_para_processar += 1

print("📊 Diagnóstico da planilha HubspotIA")
print(f"Total de linhas (exceto cabeçalho): {total}")
print(f"Linhas com resumo preenchido: {com_resumo}")
print(f"Linhas com prompt já preenchido: {com_prompt}")
print(f"Linhas prontas para processamento: {prontos_para_processar}")

if col_resumo is None:
    print("⚠️ A coluna 'Resumo' não foi encontrada.")
if col_prompt is None:
    print("⚠️ A coluna 'Prompt personalizado' não foi encontrada.")
