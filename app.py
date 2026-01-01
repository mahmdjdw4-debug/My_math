import os
import requests
import io
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import pytesseract  # اختياري لاستخراج نصوص من الصور
from flask import Flask, request

app = Flask(__name__)

# ====== إعدادات البيئة ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# ====== Utilities ======
def split_message(text, limit=2000):
    """تقسيم النص الطويل إلى أجزاء لا تتجاوز 2000 حرف"""
    text = text.strip()
    if not text:
        return []
    return [text[i:i+limit] for i in range(0, len(text), limit)]

def send_fb_message(recipient_id, text):
    """إرسال رسالة إلى فيسبوك مع تقسيم الرسائل الطويلة"""
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}

    for part in split_message(text):
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": part}
        }
        try:
            r = requests.post(url, params=params, json=payload, timeout=10)
            print("FB Status:", r.status_code)
        except Exception as e:
            print("FB send exception:", e)

# ====== OCR للصور ======
def preprocess_image(image: Image.Image) -> Image.Image:
    """تحسين الصورة لتقليل أخطاء القراءة"""
    img = ImageOps.grayscale(image)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    img = img.resize((int(img.width * 1.5), int(img.height * 1.5)), Image.LANCZOS)
    return img

def ocr_image_from_url(url):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return ""
        img_bytes = io.BytesIO(r.content)
        image = Image.open(img_bytes)
        image = preprocess_image(image)
        text = pytesseract.image_to_string(image, lang='ara+fra+eng')
        return text.strip()
    except Exception as e:
        print("OCR exception:", e)
        return ""

# ====== Gemini AI ======
def get_gemini_response(user_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    system_prompt = """
أنت مساعد تعليمي ذكي للتلاميذ، صنعك محمد الأمين أحمد جدو.
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
        "prompt": f"{system_prompt}\n\n{user_text if user_text.strip() else 'مرحبا'}",
        "max_output_tokens": 1200,
        "temperature": 0.2,
        "candidate_count": 1
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            try:
                text = data["candidates"][0]["content"][0]["text"]
                return text.strip() if text else "⚠️ لم أتمكن من فهم الطلب."
            except Exception:
                return "⚠️ حدث خطأ مؤقت أثناء قراءة الرد من النموذج."
        else:
            print("Gemini error:", response.status_code, response.text)
            return "⚠️ حدث خطأ أثناء المعالجة، حاول مرة أخرى."
    except Exception as e:
        print("Gemini exception:", e)
        return "⚠️ خطأ تقني مؤقت، أعد المحاولة لاحقًا."

# ====== Webhook ======
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Verification failed", 403

    data = request.json
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if not sender_id:
                    continue

                user_text = ""
                # معالجة نصوص الصور
                if "message" in event:
                    msg = event["message"]
                    # استخراج النصوص من الصور إذا وُجدت
                    if "attachments" in msg:
                        for att in msg["attachments"]:
                            if att.get("type") == "image":
                                ocr_text = ocr_image_from_url(att["payload"]["url"])
                                if ocr_text:
                                    user_text += f"\n\nنص الصورة المستخرج:\n{ocr_text}"

                    # النص الأصلي
                    if "text" in msg:
                        user_text = (msg["text"] + "\n" + user_text).strip()

                if user_text:
                    reply = get_gemini_response(user_text)
                    send_fb_message(sender_id, reply)

    return "ok", 200

# ====== تشغيل السيرفر ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
