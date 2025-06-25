import os
import json
import base64
from io import StringIO
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# ✅ Decodificar credenciais do Google Sheets
credentials_b64 = os.getenv("GSHEETS_KEY_B64")
if not credentials_b64:
    raise ValueError("❌ GSHEETS_KEY_B64 não está definido. Verifique os GitHub Secrets.")

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
dados = sheet.get_all_records()

# ✅ Configurar cliente da OpenAI
client_oai = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Localizar colunas
header = sheet.row_values(1)
col_resumo = header.index("Resumo") + 1
col_prompt = header.index("Prompt personalizado") + 1 if "Prompt personalizado" in header else len(header) + 1
if "Prompt personalizado" not in header:
    sheet.update_cell(1, col_prompt, "Prompt personalizado")

# ✅ Processar cada linha
for i, row in enumerate(dados, start=2):
    resumo = row.get("Resumo", "").strip()
    prompt_personalizado = row.get("Prompt personalizado", "").strip()

    if not resumo:
        print(f"⚠️ Linha {i} ignorada: sem resumo.")
        continue
    if prompt_personalizado:
        print(f"⏩ Linha {i} já processada.")
        continue
    if len(resumo) < 50:
        print(f"⚠️ Linha {i} ignorada: resumo muito curto.")
        continue

    print(f"\n💬 Gerando post para linha {i}...")
    print(f"📝 Resumo inicial: {resumo[:80]}{'...' if len(resumo) > 80 else ''}")

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

    try:
        response = client_oai.chat.completions.create(
            model="gpt-3.5-turbo",  # ou "gpt-4o" se quiser qualidade máxima
            messages=[
                {"role": "system", "content": "Você é um estrategista de marketing experiente e direto."},
                {"role": "user", "content": mensagem_usuario}
            ],
            temperature=0.7,
            max_tokens=500
        )
        texto = response.choices[0].message.content.strip()
        sheet.update_cell(i, col_prompt, texto)
        print(f"✅ Post adicionado na linha {i}.")

    except openai.APIError as e:
        print(f"🚨 API Error na linha {i}: {e}")
    except openai.RateLimitError:
        print(f"⏳ Rate limit atingido na linha {i}, tente novamente mais tarde.")
    except Exception as e:
        print(f"❌ Erro inesperado na linha {i}: {e}")
