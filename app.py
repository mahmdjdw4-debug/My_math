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
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    system_prompt = """
أنت مساعد تعليمي ذكي وحديث مخصص للتلاميذ.

افترض دائمًا أن النص:
- مستخرج من صورة تمرين (OCR)
- قد يحتوي على أخطاء إملائية أو نقص
- قد تكون بعض الرموز أو الكلمات غير دقيقة

المنهجية الإلزامية قبل أي جواب:
1) حدّد نوع الرسالة: (تحية / سؤال دراسي / سؤال عام).
2) إن كانت تحية أو كلامًا عامًا:
   - أجب بإيجاز وبأسلوب طبيعي.
3) إن كان سؤالًا دراسيًا:
   - تحقّق أولًا: هل المعطيات كافية للحل؟
   - إذا لم تكن كافية:
     * اسأل سؤالًا واحدًا ذكيًا ومحددًا فقط.
     * لا تبدأ الحل قبل التوضيح.
   - إذا كانت كافية:
     * صحّح أخطاء OCR المتوقعة منطقيًا.
     * اذكر افتراضاتك باختصار.
     * ثم اشرح الحل خطوة بخطوة.

قواعد اللغة:
- استخدم العربية الواضحة.
- اذكر المصطلحات بالفرنسية بين قوسين فقط في:
  (الرياضيات – الفيزياء – العلوم).
- لا تذكر المصطلحات الفرنسية في الأسئلة العامة.

قواعد صارمة:
- لا تقل أبدًا إنك لا ترى صورًا.
- لا تقل إنك نموذج لغة.
- لا تخترع معطيات خطيرة.
- إن شككت، اسأل قبل الحل.

السياق الزمني:
- اعتبر أننا في سنة 2025.
- استخدم معلومات عامة حديثة دون ادعاء تصفح مباشر.
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": system_prompt},
                    {"text": user_text}
                ]
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "حدث خطأ أثناء المعالجة، حاول مرة أخرى."

    except Exception:
        return "خطأ تقني مؤقت، أعد المحاولة لاحقًا."


# ====== إرسال رسالة إلى فيسبوك ======
def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text[:2000]}
    }

    requests.post(url, params=params, json=payload)


# ====== التحقق ======
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

    if data and data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")

                if "message" in event and "text" in event["message"]:
                    reply = get_gemini_response(event["message"]["text"])
                    send_fb_message(sender_id, reply)

    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
