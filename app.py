import os
import requests
import base64
import io
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import pytesseract
from flask import Flask, request

app = Flask(__name__)

# ====== إعدادات البيئة ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
VISION_API_KEY = os.environ.get("VISION_API_KEY")  # اختياري لتحسين OCR

# ====== ذاكرة محادثة بسيطة ======
conversations = {}
MAX_HISTORY = 8

# ====== Utilities ======
def push_history(sender_id, role, text):
    history = conversations.get(sender_id, [])
    history.append({"role": role, "text": text})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    conversations[sender_id] = history

def build_prompt(sender_id, user_text):
    system_instruction = (
        "أنت مساعد تعليمي خبير في الفيزياء، الرياضيات، والعلوم باللغة العربية، "
        "تحافظ على المصطلحات الفرنسية كما هي، وتشرح السبب وليس فقط كيف، "
        "وترقم الخطوات (1, 2, 3...). "
        "إذا أرسل المستخدم صورة، حاول استخراج النص فقط واطلب توضيحًا إذا لم يكن واضحًا. "
        "تعرف على الأحداث الحالية لعام 2026. "
        "هويتك: صنعك محمد الأمين أحمد جدو. "
        "إذا سُئلت عن الشخص، أجب: 'هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه'."
    )
    parts = [system_instruction, "\n--- المحادثة السابقة ---\n"]
    history = conversations.get(sender_id, [])
    for item in history:
        role = "المستخدم" if item["role"] == "user" else "المساعد"
        parts.append(f"{role}: {item['text']}\n")
    parts.append(f"\nالمستخدم (جديد): {user_text}\n")
    parts.append("\nالمطلوب: أجب بشمولية، مفصل، ومرقم، نص واضح قابل للنسخ.")
    return "\n".join(parts)

def chunk_text(text, max_len=1900):
    chunks = []
    t = text.strip()
    while t:
        if len(t) <= max_len:
            chunks.append(t)
            break
        cut = t.rfind(" ", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(t[:cut].strip())
        t = t[cut:].strip()
    return chunks

def fb_send_chunks(recipient_id, full_text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    for chunk in chunk_text(full_text, max_len=1900):
        payload = {"recipient": {"id": recipient_id}, "message": {"text": chunk}}
        try:
            r = requests.post(url, params=params, json=payload, timeout=10)
        except Exception as e:
            print("FB send exception:", e)

# ====== OCR Helpers ======
def preprocess_image(image: Image.Image):
    img = ImageOps.grayscale(image)
    img = img.filter(ImageFilter.MedianFilter(3))
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.4)
    img = img.resize((int(img.width*1.5), int(img.height*1.5)), Image.LANCZOS)
    return img

def ocr_image(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = preprocess_image(image)
        text = pytesseract.image_to_string(image, lang='ara+fra+eng')
        return text.strip()
    except Exception as e:
        print("OCR exception:", e)
        return ""

def extract_text_from_image_url(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return ""
        text = ocr_image(r.content)
        return text
    except Exception as e:
        print("extract_text_from_image_url exception:", e)
        return ""

# ====== Gemini interaction ======
def get_gemini_response(user_text, sender_id, image_url=None):
    # معالجة الصور أولاً إذا وُجدت
    extracted_text = ""
    if image_url:
        extracted_text = extract_text_from_image_url(image_url)
        if extracted_text:
            user_text += "\n\nنص الصورة المستخرج:\n" + extracted_text
        else:
            user_text += "\n\nملاحظة: الصورة غير واضحة، الرجاء إرسال النص مباشرة إذا أمكن."

    # فحص إذا سأل عن صانع البوت
    if "من صنعك" in user_text.lower() or "من برمجك" in user_text.lower():
        return "صنعني شخص اسمه محمد الأمين أحمد جدو. هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."

    prompt_text = build_prompt(sender_id, user_text)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()
        ai_text = data.get("candidates", [{}])[0].get("content", [{}])[0].get("parts", [{}])[0].get("text", "")
        if not ai_text:
            ai_text = "⚠️ حدث خطأ مؤقت، حاول إعادة إرسال السؤال."
        return ai_text
    except Exception as e:
        print("Gemini exception:", e)
        return f"⚠️ خطأ تقني مؤقت: {str(e)}"

# ====== Webhook ======
@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == FB_VERIFY_TOKEN:
            return challenge
        return "Verification failed", 403

    data = request.json
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if not sender_id:
                    continue

                user_text = ""
                image_url = None
                if "message" in event:
                    msg = event["message"]
                    user_text = msg.get("text", "")
                    attachments = msg.get("attachments", [])
                    for att in attachments:
                        if att.get("type") == "image":
                            image_url = att.get("payload", {}).get("url")

                if not user_text and not image_url:
                    user_text = "مرحباً"  # أي نص افتراضي إذا لم يرسل المستخدم نص

                push_history(sender_id, "user", user_text)
                ai_reply = get_gemini_response(user_text, sender_id, image_url)
                push_history(sender_id, "assistant", ai_reply)
                fb_send_chunks(sender_id, ai_reply)

    return "ok", 200

# ====== Run Server ======
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
