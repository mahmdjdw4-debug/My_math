import os
import json
import requests
from flask import Flask, request

app = Flask(__name__)

# =========================
# Environment Variables
# =========================

FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# =========================
# Gemini API Configuration
# =========================

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


# =========================
# Utility: Log helper
# =========================

def log(title, data=None):
    print("\n" + "=" * 40)
    print(title)
    if data is not None:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    print("=" * 40 + "\n")


# =========================
# Gemini: List Models (Debug)
# =========================

def list_gemini_models():
    url = f"{GEMINI_BASE_URL}/models?key={GEMINI_API_KEY}"
    response = requests.get(url)

    log("Gemini List Models - Status", response.status_code)

    try:
        return response.json()
    except Exception:
        return {"error": "Invalid JSON from Gemini"}


# =========================
# Gemini: Generate Content
# =========================

def generate_gemini_response(user_text):
    url = (
        f"{GEMINI_BASE_URL}/models/"
        f"{DEFAULT_GEMINI_MODEL}:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_text}]
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    log("Gemini Response Status", response.status_code)
    log("Gemini Raw Response", response.text)

    if response.status_code != 200:
        return "⚠️ حدث خطأ أثناء الاتصال بنموذج الذكاء الاصطناعي."

    data = response.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return "⚠️ لم أتمكن من فهم رد النموذج."


# =========================
# Facebook: Send Message
# =========================

def send_facebook_message(recipient_id, text):
    url = (
        "https://graph.facebook.com/v18.0/me/messages"
        f"?access_token={FB_PAGE_ACCESS_TOKEN}"
    )

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }

    response = requests.post(url, json=payload)

    log("Facebook Send Status", response.status_code)
    log("Facebook Send Response", response.text)


# =========================
# Webhook Verification
# =========================

@app.route("/", methods=["GET"])
def verify_webhook():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == FB_VERIFY_TOKEN:
        return challenge, 200

    return "Verification failed", 403


# =========================
# Webhook Receiver
# =========================

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    log("Incoming Webhook", data)

    try:
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                if "message" in messaging_event:
                    text = messaging_event["message"].get("text")

                    if text:
                        ai_reply = generate_gemini_response(text)
                        send_facebook_message(sender_id, ai_reply)

    except Exception as e:
        log("Webhook Processing Error", str(e))

    return "ok", 200


# =========================
# Optional: Manual Debug Route
# =========================

@app.route("/debug/models", methods=["GET"])
def debug_models():
    models = list_gemini_models()
    return models, 200
