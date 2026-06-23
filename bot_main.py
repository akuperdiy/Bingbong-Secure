import os
from flask import Flask, request, jsonify
import requests
from ddgs import DDGS

app = Flask(__name__)

# Konfigurasi - diambil dari environment variable (aman untuk produksi)
TELEGRAM_TOKEN = os.environ.get("8929027662:AAGWt2TN2ZjvCBgXNQA38BP5FXbLPvSxTC4", "")
KUNYA_API_KEY = os.environ.get("kunya_10Eq1K3E0ZaSbvVQQ9_rUWaMMKCk3ciRCYUZTwZ3MOk6pj1Z", "")

# Memori chat
chat_histories = {}
MAX_HISTORY = 10

# Daftar model yang tersedia
AVAILABLE_MODELS = {
    "gemini": "gemini-3.5-flash",      # Cepat, untuk chat umum (default)
    "gpt": "gpt-5.5",                   # Model terbaru OpenAI
    "o3": "o3",                         # Reasoning kuat (coding/matematika)
    "claude": "claude-opus-4.5",        # Kreatif, menulis, analisis dalam
    "deepseek": "deepseek-v5-0324"     # Alternatif reasoning
}

# Default model
current_model = "gemini-3.5-flash"


def cari_internet(query):
    """Mencari informasi terbaru dari internet"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            if results:
                info = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
                return f"Hasil pencarian internet untuk '{query}':\n{info}"
            return "Tidak ada hasil ditemukan."
    except Exception as e:
        return f"Gagal mencari: {str(e)}"


@app.route('/', methods=['POST'])
def webhook():
    global current_model
    data = request.json

    if not data or 'message' not in data:
        return "ok", 200

    if 'text' not in data['message']:
        return "ok", 200

    chat_id = data['message']['chat']['id']
    user_text = data['message']['text']

    # === CEK COMMAND /model ===
    if user_text.startswith('/model'):
        parts = user_text.strip().split()
        if len(parts) == 1 or (len(parts) > 1 and parts[1] == 'current'):
            reply = f"🧠 Model saat ini: *{current_model}*"
        elif parts[1] == 'list':
            reply = "📋 *Daftar model tersedia:*\n"
            for key, model in AVAILABLE_MODELS.items():
                marker = "✅ " if model == current_model else "   "
                reply += f"{marker}`{key}` → {model}\n"
            reply += "\nGunakan: `/model <nama>` untuk ganti model"
        elif parts[1] in AVAILABLE_MODELS:
            current_model = AVAILABLE_MODELS[parts[1]]
            reply = f"✅ Model diganti ke *{current_model}*"
        else:
            reply = f"❌ Model `{parts[1]}` tidak dikenal. Ketik `/model list` untuk melihat daftar."

        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown"
        })
        return "ok", 200

    # === LOGIKA CHAT BIASA (dengan memori) ===
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    chat_histories[chat_id].append({"role": "user", "content": user_text})

    kata_trigger_search = ['cari', 'search', 'info terbaru', 'berita', 'latest',
                           'news', 'apa yang terjadi', 'siapa', 'berapa harga', 'kapan']
    if any(kata in user_text.lower() for kata in kata_trigger_search):
        hasil_search = cari_internet(user_text)
        chat_histories[chat_id].append({
            "role": "system",
            "content": f"Hasil pencarian internet: {hasil_search}"
        })

    messages_to_send = chat_histories[chat_id][-MAX_HISTORY:]

    try:
        kunya_resp = requests.post(
            "https://api.kunya.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {KUNYA_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": current_model,
                "messages": messages_to_send
            },
            timeout=30
        )
        kunya_resp.raise_for_status()
        ai_reply = kunya_resp.json()['choices'][0]['message']['content']
    except Exception as e:
        ai_reply = f"⚠️ Maaf, terjadi error saat menghubungi AI: {str(e)}"

    chat_histories[chat_id].append({"role": "assistant", "content": ai_reply})

    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
        "chat_id": chat_id,
        "text": ai_reply
    })

    return "ok", 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)