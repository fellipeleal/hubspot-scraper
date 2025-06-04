import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

# Criar o arquivo credenciais.json dinamicamente a partir do secret
if not os.path.exists("credenciais.json"):
    with open("credenciais.json", "w") as f:
        f.write(os.getenv("GOOGLE_CREDENTIALS"))

# Segue a autenticação normal
from oauth2client.service_account import ServiceAccountCredentials
import gspread

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credenciais.json", scope)
client = gspread.authorize(creds)

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
        try:
            mensagem_usuario = "\n".join([
                "Crie um post para LinkedIn com tom provocador e autoridade técnica sobre o tema.",
                "",
                "Resumo do artigo:",
                f'"{resumo}"',
                "",
                "O texto deve:",
                "– Começar com uma frase que aponte um erro comum no mercado",
                "– Mostrar o contraste entre a prática superficial e a prática correta",
                "– Incluir um exemplo real (ou simulado) que mostre como isso se aplica na prática",
                "– Terminar com uma provocação aberta, convidando ao debate",
                "",
                "O post deve ser direto, com frases curtas, e ter o tom de alguém que já viveu isso na pele — não de quem está repetindo buzzwords.",
                "Use no máximo 1.300 caracteres e inclua hashtags específicas no final."
            ])

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Você é um estrategista de marketing experiente e direto."},
                    {"role": "user", "content": mensagem_usuario}
                ],
                temperature=0.7,
                max_tokens=500
            )

            texto = response["choices"][0]["message"]["content"].strip()
            sheet.update_cell(i, col_prompt, texto)

        except Exception as e:
            print(f"❌ Erro na linha {i}: {e}")
