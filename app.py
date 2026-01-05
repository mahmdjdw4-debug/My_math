import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ========= ENV =========
PAGE_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_KEY = os.environ.get("GOOGLE_API_KEY")

# ========= Facebook Send =========
def send_message(psid, text):
    if not text:
        return
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": PAGE_TOKEN}
    payload = {
        "recipient": {"id": psid},
        "message": {"text": text}
    }
    r = requests.post(url, params=params, json=payload)
    if r.status_code != 200:
        print("FB ERROR:", r.text)

# ========= Gemini (آمن) =========
def ask_gemini(question):
    if not GEMINI_KEY:
        print("❌ GEMINI KEY NOT FOUND")
        return None

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
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

    r = requests.post(url, json=payload, headers=headers)

    try:
        data = r.json()
    except Exception:
        print("❌ INVALID JSON:", r.text)
        return None

    print("🔎 GEMINI RAW RESPONSE:", data)

    if "candidates" not in data or not data["candidates"]:
        print("❌ NO CANDIDATES")
        return None

    candidate = data["candidates"][0]

    if candidate.get("finishReason") == "SAFETY":
        return "⚠️ لا يمكنني شرح هذا الموضوع حالياً."

    parts = candidate.get("content", {}).get("parts", [])

    if not parts or "text" not in parts[0]:
        print("❌ NO TEXT IN PARTS")
        return None

    return parts[0]["text"].strip()

# ========= Webhook Verify =========
@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Forbidden", 403

# ========= Webhook Receive =========
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    print("📩 INCOMING:", data)

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event.get("sender", {}).get("id")
            msg = event.get("message", {}).get("text", "")

            if not sender or not msg:
                continue

            text = msg.lower().strip()

            # ===== ردود محلية =====
            if text in ["مرحبا", "السلام عليكم", "hi", "hello"]:
                send_message(sender, "أهلاً بك 👋 كيف أستطيع مساعدتك؟")
                continue

            if "من صنعك" in text:
                send_message(sender, "صنعني محمد الأمين أحمد جدو 🤍")
                continue

            # ===== Gemini =====
            reply = ask_gemini(msg)

            if not reply:
                reply = "❌ لم أستطع الرد حالياً، حاول لاحقاً."

            send_message(sender, reply)

    return "ok", 200

# ========= Run =========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
