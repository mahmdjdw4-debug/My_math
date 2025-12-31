import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ====== إعدادات البيئة ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# ====== Gemini AI ======
def get_gemini_response(user_text):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": user_text}
                ]
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print("Gemini Status:", response.status_code)
        print("Gemini Response:", response.text)

        if response.status_code == 200:
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "❌ حدث خطأ أثناء الاتصال بالذكاء الاصطناعي."

    except Exception as e:
        return f"⚠️ خطأ تقني: {str(e)}"


# ====== إرسال رسالة إلى فيسبوك ======
def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }

    r = requests.post(url, params=params, json=payload)
    print("FB Status:", r.status_code)
    print("FB Response:", r.text)


# ====== التحقق من Webhook ======
@app.route("/", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == FB_VERIFY_TOKEN:
        return challenge
    return "Verification failed", 403


# ====== استقبال الرسائل ======
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    print("Webhook data:", data)

    if data and data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")

                if not sender_id:
                    continue

                if "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]
                    reply = get_gemini_response(user_text)
                    send_fb_message(sender_id, reply)

    return "ok", 200


# ====== تشغيل السيرفر ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
