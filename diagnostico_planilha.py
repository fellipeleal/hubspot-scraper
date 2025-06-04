import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Autenticar com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)

# Acessar planilha e aba
sheet = client.open("HubspotIA").sheet1
dados = sheet.get_all_records()

# Identificar colunas
header = sheet.row_values(1)
col_resumo = header.index("Resumo") + 1 if "Resumo" in header else None
col_prompt = header.index("Prompt personalizado") + 1 if "Prompt personalizado" in header else None

# Diagnóstico
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
