import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# Autenticar com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)

# Autenticar com OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Abrir planilha
sheet = client.open("HubspotIA").sheet1
dados = sheet.get_all_records()

# Identificar cabeçalhos
header = sheet.row_values(1)
col_resumo = header.index("Resumo") + 1
col_prompt = header.index("Prompt personalizado") + 1 if "Prompt personalizado" in header else len(header) + 1

# Criar coluna se não existir
if "Prompt personalizado" not in header:
    sheet.update_cell(1, col_prompt, "Prompt personalizado")

# Processar cada linha
for i, row in enumerate(dados, start=2):  # começa na linha 2
    resumo = row.get("Resumo", "").strip()
    prompt_personalizado = row.get("Prompt personalizado", "").strip()

    if resumo and not prompt_personalizado:
        print(f"💬 Gerando post para linha {i}...")

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Você é um redator de marketing digital."},
                    {"role": "user", "content": f"""Crie um post de LinkedIn com base neste resumo de notícia:

"""{resumo}"""

O post deve:
- Ser claro e aplicável a profissionais de marketing
- Usar até 2 emojis
- Terminar com uma pergunta ou CTA
"""}
                ],
                temperature=0.7,
                max_tokens=300
            )

            texto = response["choices"][0]["message"]["content"].strip()
            sheet.update_cell(i, col_prompt, texto)
            print(f"✅ Post adicionado na linha {i}.")

        except Exception as e:
            print(f"❌ Erro na linha {i}: {e}")
