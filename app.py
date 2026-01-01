import os
import requests
import base64
import io
from flask import Flask, request
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract

app = Flask(__name__)

# ================== ENV ==================
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
VISION_API_KEY = os.environ.get("VISION_API_KEY")

# ================== MEMORY ==================
conversations = {}
MAX_HISTORY = 6

# ================== HELPERS ==================
def safe_push(sender, role, text):
    conversations.setdefault(sender, [])
    conversations[sender].append({"role": role, "text": text})
    conversations[sender] = conversations[sender][-MAX_HISTORY:]

def smart_chunks(text, limit=1700):
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    return parts

def fb_send(sender, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    for chunk in smart_chunks(text):
        payload = {
            "recipient": {"id": sender},
            "message": {"text": chunk.strip()}
        }
        requests.post(url, params=params, json=payload)

# ================== OCR ==================
def preprocess(img):
    img = ImageOps.grayscale(img)
    img = img.filter(ImageFilter.MedianFilter(3))
    img = ImageEnhance.Contrast(img).enhance(1.6)
    return img

def ocr_google(img_bytes):
    if not VISION_API_KEY:
        return ""
    encoded = base64.b64encode(img_bytes).decode()
    url = f"https://vision.googleapis.com/v1/images:annotate?key={VISION_API_KEY}"
    payload = {
        "requests": [{
            "image": {"content": encoded},
            "features": [{"type": "TEXT_DETECTION"}]
        }]
    }
    r = requests.post(url, json=payload)
    try:
        return r.json()["responses"][0]["fullTextAnnotation"]["text"]
    except:
        return ""

def ocr_tesseract(img_bytes):
    img = Image.open(io.BytesIO(img_bytes))
    img = preprocess(img)
    return pytesseract.image_to_string(img, lang="ara+fra+eng")

# ================== PROMPT ==================
def build_prompt(sender, user_text):
    system = """
أنت مساعد تعليمي متخصص في حل تمارين الفيزياء والرياضيات والعلوم.
- اشرح بالعربية الفصحى المبسطة.
- حافظ على المصطلحات العلمية بالفرنسية كما هي.
- اشرح لماذا (why) قبل كيف (how).
- رقم الشرح: 1، 2، 3...
- ممنوع استخدام LaTeX أو رموز مثل frac أو {} أو [].
- اجعل الإجابة واضحة لطالب ثانوي.
"""
    history = ""
    for h in conversations.get(sender, []):
        role = "الطالب" if h["role"] == "user" else "المعلم"
        history += f"{role}: {h['text']}\n"

    return f"{system}\n{history}\nالطالب: {user_text}\nالمعلم:"

# ================== GEMINI ==================
def ask_gemini(sender, text):
    if any(x in text.lower() for x in ["من صنعك", "من برمجك", "who made you"]):
        return (
            "صنعني شخص اسمه محمد الأمين أحمد جدو.\n"
            "هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."
        )

    prompt = build_prompt(sender, text)
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    headers = {"x-goog-api-key": GEMINI_API_KEY}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "temperature": 0.15,
        "max_output_tokens": 1600
    }

    r = requests.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        return "❌ حدث خطأ تقني، أعد المحاولة."

    try:
        txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return txt.replace("{", "").replace("}", "").replace("[", "").replace("]", "")
    except:
        return "❌ لم أستطع توليد إجابة واضحة."

# ================== WEBHOOK ==================
@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "error", 403

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    for entry in data.get("entry", []):
        for msg in entry.get("messaging", []):
            sender = msg["sender"]["id"]

            text = msg.get("message", {}).get("text", "")

            for att in msg.get("message", {}).get("attachments", []):
                if att["type"] == "image":
                    img = requests.get(att["payload"]["url"]).content
                    text += "\n" + (ocr_google(img) or ocr_tesseract(img))

            if text:
                safe_push(sender, "user", text)
                reply = ask_gemini(sender, text)
                safe_push(sender, "assistant", reply)
                fb_send(sender, reply)

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
