import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ===== ENV =====
PAGE_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_KEY = os.environ.get("GOOGLE_API_KEY")

# ===== Facebook Send =====
def send_message(psid, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": PAGE_TOKEN}
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }
    requests.post(url, params=params, json=payload)

# ===== Gemini =====
def ask_gemini(question):
    if not GEMINI_KEY:
        print("❌ NO GEMINI KEY")
        return None

    url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_KEY
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "اشرح بأسلوب تعليمي مبسط:\n" + question}
                ]
            }
        ]
    }

    r = requests.post(url, headers=headers, json=payload)
    print("GEMINI STATUS:", r.status_code)
    print("RAW:", r.text)

    if r.status_code != 200:
        return None

    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]

# ===== Verify =====
@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Forbidden", 403

# ===== Webhook =====
@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event.get("sender", {}).get("id")
            msg = event.get("message", {}).get("text", "")

            if not sender or not msg:
                continue

            text = msg.strip().lower()

            if text in ["مرحبا", "السلام عليكم", "hi", "hello"]:
                send_message(sender, "أهلاً بك 👋")
                continue

            reply = ask_gemini(msg)
            if not reply:
                reply = "❌ حدث خطأ مؤقت، حاول لاحقاً."

            send_message(sender, reply)

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
