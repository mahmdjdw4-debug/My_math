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
VISION_API_KEY = os.environ.get("VISION_API_KEY")  # Google Vision API (اختياري)

# ====== ذاكرة محادثات ======
conversations = {}
MAX_HISTORY_MESSAGES = 8

# ====== Utilities ======
def push_history(sender_id, role, text):
    history = conversations.get(sender_id, [])
    history.append({"role": role, "text": text})
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    conversations[sender_id] = history

def build_prompt(sender_id, user_text, extra_note=""):
    system_note = (
        "أنت مساعد ذكي متخصص في حل تمارين وشرح دروس الفيزياء، الرياضيات والعلوم. "
        "أجب باللغة العربية المبسطة، وحافظ على المصطلحات الفرنسية كما هي. "
        "اشرح السبب (why) مع الحل، لا تكتفِ بكيف (how). "
        "رقم الخطوات عند الشرح، لا تستخدم رموز LaTeX المعقدة. "
        "إذا كانت الصورة ناقصة اطلب سؤالًا واحدًا فقط قبل الحل. "
        "كن مدركًا للعام الحالي 2026."
    )
    if extra_note:
        system_note += " " + extra_note
    parts = [system_note, "\n--- المحادثة السابقة ---\n"]
    for item in conversations.get(sender_id, []):
        role = "المستخدم" if item["role"] == "user" else "المساعد"
        parts.append(f"{role}: {item['text']}\n")
    parts.append("\nالمستخدم الجديد: " + user_text + "\n")
    parts.append("\nالمطلوب: رد تفصيلي ومرقم مع ذكر السبب، قابل للنسخ.")
    return "\n".join(parts)

def split_text(text, limit=1900):
    chunks = []
    t = text.strip()
    while t:
        if len(t) <= limit:
            chunks.append(t)
            break
        cut = t.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(t[:cut].strip())
        t = t[cut:].strip()
    return chunks

def fb_send_chunks(recipient_id, full_text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    for chunk in split_text(full_text):
        payload = {"recipient": {"id": recipient_id}, "message": {"text": chunk}}
        try:
            r = requests.post(url, params={"access_token": FB_PAGE_ACCESS_TOKEN}, json=payload, timeout=15)
            print("FB send status:", r.status_code)
        except Exception as e:
            print("FB send exception:", e)

# ====== OCR Helpers ======
def preprocess_image(image: Image.Image) -> Image.Image:
    img = ImageOps.grayscale(image)
    img = img.filter(ImageFilter.MedianFilter(3))
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.4)
    img = img.resize((int(img.width*1.5), int(img.height*1.5)), Image.LANCZOS)
    return img

def ocr_tesseract(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = preprocess_image(image)
        text = pytesseract.image_to_string(image, lang="eng+fra+ara")
        return text.strip()
    except Exception as e:
        print("OCR Tesseract error:", e)
        return ""

def ocr_google_vision(image_bytes):
    try:
        if not VISION_API_KEY:
            return ""
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        url = f"https://vision.googleapis.com/v1/images:annotate?key={VISION_API_KEY}"
        payload = {"requests": [{"image": {"content": encoded}, "features": [{"type": "TEXT_DETECTION"}]}]}
        r = requests.post(url, json=payload, timeout=15)
        data = r.json()
        return data["responses"][0].get("fullTextAnnotation", {}).get("text", "").strip()
    except Exception as e:
        print("OCR Google Vision error:", e)
        return ""

def image_to_text(url):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return ""
        img_bytes = r.content
        text = ""
        if VISION_API_KEY:
            text = ocr_google_vision(img_bytes)
        if not text:
            text = ocr_tesseract(img_bytes)
        return text
    except Exception as e:
        print("image_to_text exception:", e)
        return ""

# ====== Gemini AI Interaction ======
def get_gemini_response(user_text, sender_id, image_text=None):
    # سؤال عن الصانع
    if "من صنعك" in user_text or "من برمجك" in user_text.lower():
        return "صنعني شخص اسمه محمد الأمين أحمد جدو. هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."
    
    combined_text = user_text
    if image_text:
        combined_text += "\n\nنص الصورة:\n" + image_text

    prompt_text = build_prompt(sender_id, combined_text)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
            ai_text = ai_text.replace("[","").replace("]","").replace("{","").replace("}","")
            return ai_text.strip()
        else:
            print("Gemini error:", response.text)
            return "❌ حدث خطأ في معالجة النموذج. حاول مرة أخرى."
    except Exception as e:
        print("Gemini exception:", e)
        return f"⚠️ خطأ تقني: {str(e)}"

# ====== Webhook ======
@app.route("/", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == FB_VERIFY_TOKEN:
        return challenge
    return "Verification failed", 403

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if not sender_id:
                    continue

                msg = event.get("message", {})
                user_text = msg.get("text","")
                image_texts = []

                for att in msg.get("attachments", []):
                    if att.get("type") == "image":
                        url = att.get("payload", {}).get("url")
                        if url:
                            text = image_to_text(url)
                            if text:
                                image_texts.append(text)
                
                image_text = "\n---\n".join(image_texts) if image_texts else None

                push_history(sender_id, "user", user_text)
                reply = get_gemini_response(user_text, sender_id, image_text)
                push_history(sender_id, "assistant", reply)
                fb_send_chunks(sender_id, reply)

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
