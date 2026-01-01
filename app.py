import os
import requests
from flask import Flask, request

app = Flask(__name__)

# ====== إعدادات البيئة ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# ====== تقسيم الرسائل الطويلة ======
def split_text(text, limit=1900):
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].strip()
    return chunks

# ====== Gemini AI ======
def get_gemini_response(user_text):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    system_prompt = """
أنت مساعد تعليمي ذكي وحديث للتلاميذ، صنعك محمد الأمين أحمد جدو.
إذا سُئلت عن صانع البوت قل: "هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه".

التعليمات:
1. افترض أن النص قد يكون مستخرج من صورة تمرين (OCR) ويحتوي على أخطاء.
2. حدّد نوع الرسالة: تحية / سؤال دراسي / سؤال عام.
3. إذا كانت تحية أو نص عام: أجب بإيجاز وطبيعي.
4. إذا كان سؤالًا دراسيًا:
   - تحقق أولًا: هل المعطيات كافية؟
   - إذا لم تكن كافية، اسأل سؤالًا واحدًا ذكيًا قبل الحل.
   - إذا كانت كافية، صحح أخطاء OCR المحتملة واذكر افتراضاتك.
   - ثم اشرح الحل خطوة بخطوة، مع ترقيم واضح (1, 2, 3...).
5. استخدم العربية الواضحة، واذكر المصطلحات بالفرنسية في الرياضيات، الفيزياء، العلوم.
6. لا تقل أبداً أنك لا ترى الصور، ولا تقل أنك نموذج لغة.
7. استخدم معلومات عامة حديثة لسنة 2025.
"""

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": system_prompt},
                    {"text": user_text if user_text.strip() else "مرحبا"}
                ]
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            # استخراج النص مع حماية من الأخطاء
            try:
                text = data["candidates"][0]["content"][0]["parts"][0]["text"]
                return text.strip() if text else "⚠️ لم أتمكن من فهم الطلب، حاول إعادة صياغته."
            except Exception:
                return "⚠️ حدث خطأ مؤقت أثناء قراءة الرد من النموذج."
        else:
            return "⚠️ حدث خطأ أثناء المعالجة، حاول مرة أخرى."
    except Exception:
        return "⚠️ خطأ تقني مؤقت، أعد المحاولة لاحقًا."

# ====== إرسال الرسائل لفيسبوك ======
def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    for chunk in split_text(text):
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": chunk[:2000]}
        }
        try:
            requests.post(url, params={"access_token": FB_PAGE_ACCESS_TOKEN}, json=payload, timeout=10)
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
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if not sender_id:
                    continue

                user_text = ""
                if "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]

                reply = get_gemini_response(user_text)
                send_fb_message(sender_id, reply)
    return "ok", 200

# ====== تشغيل السيرفر ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
