import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ====== إعدادات البيئة ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# ====== تقسيم رسائل فيسبوك ======
def chunk_text(text, limit=1900):
    parts = []
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    return parts

# ====== Gemini AI (بسيط + مضمون) ======
def get_gemini_response(user_text):
    if not user_text or not user_text.strip():
        return "لم أفهم السؤال، هل يمكنك توضيحه؟"

    lowered = user_text.lower()
    if ("من صنعك" in lowered) or ("من برمجك" in lowered) or ("who made you" in lowered):
        return (
            "صنعني شخص اسمه محمد الأمين أحمد جدو.\n"
            "هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."
        )

    prompt = (
        "اشرح الإجابة بالعربية المبسطة، "
        "مع الحفاظ على المصطلحات العلمية بالفرنسية، "
        "واذكر لماذا قبل كيف، "
        "ورقم الشرح 1، 2، 3.\n\n"
        f"السؤال:\n{user_text}"
    )

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print("Gemini Status:", response.status_code)
        print("Gemini Raw:", response.text)

        if response.status_code != 200:
            return "❌ حدث خطأ أثناء الاتصال بالذكاء الاصطناعي."

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        # تنظيف خفيف فقط
        return (
            text.replace("{", "")
                .replace("}", "")
                .replace("[", "")
                .replace("]", "")
                .strip()
        )

    except Exception as e:
        print("Gemini Exception:", e)
        return "⚠️ خطأ تقني مؤقت، حاول مرة أخرى."

# ====== إرسال رسالة إلى فيسبوك ======
def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}

    for part in chunk_text(text):
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": part}
        }
        r = requests.post(url, params=params, json=payload)
        print("FB Status:", r.status_code, r.text)

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
