import os
import requests
import base64
from flask import Flask, request

app = Flask(__name__)

# ====== ENV ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
VISION_API_KEY = os.environ.get("VISION_API_KEY")

# ====== Facebook helpers ======
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

def send_fb_message(sender_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}

    for part in chunk_text(text):
        payload = {
            "recipient": {"id": sender_id},
            "message": {"text": part.strip()}
        }
        requests.post(url, params=params, json=payload)

# ====== OCR (آمن) ======
def ocr_google(image_url):
    if not VISION_API_KEY:
        return ""

    try:
        img = requests.get(image_url, timeout=20).content
        encoded = base64.b64encode(img).decode()

        url = f"https://vision.googleapis.com/v1/images:annotate?key={VISION_API_KEY}"
        payload = {
            "requests": [{
                "image": {"content": encoded},
                "features": [{"type": "TEXT_DETECTION"}]
            }]
        }

        r = requests.post(url, json=payload, timeout=25)
        text = r.json()["responses"][0].get("fullTextAnnotation", {}).get("text", "")
        return text[:1200]  # 🔐 حد أمان
    except:
        return ""

# ====== Gemini caller (مع fallback) ======
def call_gemini(model, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=35)
        if r.status_code != 200:
            return None
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return None

# ====== AI logic ======
def get_ai_reply(user_text, ocr_text=""):
    lower = user_text.lower()
    if any(x in lower for x in ["من صنعك", "من برمجك", "who made you"]):
        return (
            "صنعني شخص اسمه محمد الأمين أحمد جدو.\n"
            "هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."
        )

    # قالب تعليمي عام
    prompt = f"""
أجب وفق هذا القالب فقط:

1) فهم السؤال
2) المعطيات (Données)
3) الفكرة العلمية مع شرح لماذا
4) الحل خطوة بخطوة
5) الخلاصة

قواعد:
- الشرح بالعربية المبسطة
- المصطلحات العلمية بالفرنسية
- ممنوع LaTeX أو frac أو {{}} []
- أسلوب تعليمي لطالب ثانوي

السؤال:
{user_text}
"""

    if ocr_text:
        prompt += f"""

نص مستخرج من صورة (قد يحتوي أخطاء OCR):
---
{ocr_text}
---
"""

    # 🧠 النموذج الذكي أولًا
    answer = call_gemini("gemini-1.5-pro", prompt)

    # 🛟 fallback
    if not answer:
        answer = call_gemini("gemini-flash-latest", prompt)

    if not answer:
        return "❌ لم أستطع توليد إجابة واضحة، حاول إعادة صياغة السؤال."

    return (
        answer.replace("{", "")
              .replace("}", "")
              .replace("[", "")
              .replace("]", "")
              .strip()
    )

# ====== Webhook ======
@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verification failed", 403

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if data and data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if not sender_id:
                    continue

                msg = event.get("message", {})
                user_text = msg.get("text", "")  # نص الرسالة العادي
                ocr_text = ""

                # معالجة الصور
                attachments = msg.get("attachments", [])
                for att in attachments:
                    if att.get("type") == "image":
                        ocr_result = ocr_google(att["payload"]["url"])
                        if ocr_result:
                            ocr_text += ("\n" + ocr_result) if ocr_text else ocr_result

                # إذا لم يكن هناك نص عادي ولكن الصورة أعطت نصًا
                if not user_text and ocr_text:
                    user_text = ocr_text  # نجعل النص المستخرج هو مدخل البوت

                # إذا هناك أي نص، نفكر إذا كان سؤال دراسي أو مجرد نص
                if user_text:
                    reply = get_ai_reply(user_text, ocr_text)
                    send_fb_message(sender_id, reply)

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
