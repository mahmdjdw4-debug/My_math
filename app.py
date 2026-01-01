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

    # تحسين system prompt ليكون أكثر ذكاءً ومنهجية
    system_prompt = """
أنت مساعد تعليمي ذكي وحديث مخصص للتلاميذ.

افترض دائمًا أن النص:
- مستخرج من صورة تمرين (OCR)
- قد يحتوي على أخطاء إملائية أو نقص
- قد تكون بعض الرموز أو الكلمات غير دقيقة

المنهجية قبل أي جواب:
1. حدّد نوع الرسالة: تحية / سؤال دراسي / سؤال عام.
2. إذا كانت تحية أو نص عام: أجب بإيجاز وبأسلوب طبيعي.
3. إذا كان سؤالًا دراسيًا:
   - تحقق أولًا: هل المعطيات كافية للحل؟
   - إذا لم تكن كافية: اسأل سؤالًا واحدًا ذكيًا فقط قبل الحل.
   - إذا كانت كافية:
       - صحح أخطاء OCR المتوقعة منطقيًا.
       - اذكر افتراضاتك باختصار.
       - اشرح الحل خطوة بخطوة ومنهجية واضحة.
4. استخدم العربية الواضحة، واذكر المصطلحات بالفرنسية في الرياضيات، الفيزياء، العلوم فقط.
5. لا تقل أبدًا أنك لا ترى الصور أو أنك نموذج لغة.
6. لا تخترع معطيات خطيرة.
7. كن مدركًا للسنة الحالية 2025، واستخدم معلومات عامة حديثة.
8. إذا كان الرد طويلًا جدًا، اقسمه إلى فقرات واضحة لتسهيل القراءة.
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
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                # إضافة تقسيم الرد الطويل إلى أجزاء
                if len(text) > 2000:
                    return "\n---\n".join([text[i:i+2000] for i in range(0, len(text), 2000)])
                return text
            except Exception:
                return "⚠️ حدث خطأ مؤقت أثناء قراءة الرد من النموذج."
        else:
            print("Gemini error:", response.status_code, response.text)
            return "⚠️ حدث خطأ أثناء المعالجة، حاول مرة أخرى."

    except Exception as e:
        print("Gemini exception:", e)
        return "⚠️ خطأ تقني مؤقت، أعد المحاولة لاحقًا."

# ====== إرسال رسالة إلى فيسبوك مع تقسيم الرسائل الطويلة ======
def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}

    # تقسيم الرسائل الطويلة
    messages = [text[i:i+2000] for i in range(0, len(text), 2000)]

    for part in messages:
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": part}
        }
        try:
            requests.post(url, params=params, json=payload, timeout=10)
        except Exception as e:
            print("FB send exception:", e)

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
                    user_text = event["message"]["text"].strip()
                    if user_text:
                        reply = get_gemini_response(user_text)
                        send_fb_message(sender_id, reply)

    return "ok", 200

# ====== تشغيل السيرفر ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
