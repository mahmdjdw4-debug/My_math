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
VISION_API_KEY = os.environ.get("VISION_API_KEY")

# ====== ذاكرة بسيطة ======
conversations = {}
MAX_HISTORY_MESSAGES = 8

# ====== Utilities ======
def push_history(sender_id, role, text):
    history = conversations.get(sender_id, [])
    history.append({"role": role, "text": text})
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    conversations[sender_id] = history

def build_prompt_from_history(sender_id, user_text, extra_note=""):
    system_note = (
        "أنت مساعد ذكي متخصص في حل تمارين وشرح دروس الفيزياء، الرياضيات والعلوم. "
        "أجب باللغة العربية الفصحى المبسطة، وحافظ على المصطلحات العلمية باللغة الفرنسية كما هي. "
        "اشرح لماذا (why) قبل كيف (how). "
        "رقّم الشرح 1، 2، 3... "
        "لا تستخدم رموز LaTeX أو كلمات مثل frac أو {} أو []. "
        "اجعل الإجابة مفهومة لطالب ثانوي."
    )

    parts = [system_note, "\n--- محادثة سابقة ---\n"]
    for item in conversations.get(sender_id, []):
        role = "المستخدم" if item["role"] == "user" else "المساعد"
        parts.append(f"{role}: {item['text']}\n")

    parts.append("\nالمستخدم (الجديد): " + user_text)
    parts.append("\nالمطلوب: أجب بشرح تفصيلي مبسط ومُرقّم.")
    return "\n".join(parts)

def chunk_text(text, max_len=1900):
    chunks = []
    while len(text) > max_len:
        cut = text.rfind(" ", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:]
    chunks.append(text)
    return chunks

def fb_send_chunks(recipient_id, full_text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    for chunk in chunk_text(full_text):
        payload = {"recipient": {"id": recipient_id}, "message": {"text": chunk.strip()}}
        requests.post(url, params=params, json=payload)

# ====== OCR ======
def preprocess_image_for_ocr(image):
    image = ImageOps.grayscale(image)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageEnhance.Contrast(image).enhance(1.4)
    return image

def ocr_with_pytesseract(img_bytes):
    try:
        image = Image.open(io.BytesIO(img_bytes))
        image = preprocess_image_for_ocr(image)
        return pytesseract.image_to_string(image, lang="ara+fra+eng").strip()
    except:
        return ""

def ocr_with_google_vision(img_bytes):
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
    try:
        r = requests.post(url, json=payload, timeout=25)
        return r.json()["responses"][0]["fullTextAnnotation"]["text"]
    except:
        return ""

def image_url_to_text(url):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            return ""
        img_bytes = r.content
        return ocr_with_google_vision(img_bytes) or ocr_with_pytesseract(img_bytes)
    except:
        return ""

# ====== Gemini (المُعدل فقط) ======
def get_gemini_response(user_text, sender_id):
    try:
        if not user_text or not user_text.strip():
            return "لم أفهم السؤال، هل يمكنك توضيحه؟"

        lowered = user_text.lower()

        if ("من صنعك" in lowered) or ("من برمجك" in lowered) or ("who made you" in lowered):
            return (
                "صنعني شخص اسمه محمد الأمين أحمد جدو.\n"
                "هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."
            )

        prompt_text = build_prompt_from_history(sender_id, user_text)

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }

        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "temperature": 0.2
        }

        response = requests.post(url, json=payload, headers=headers, timeout=35)

        if response.status_code != 200:
            print("Gemini error:", response.text)
            return "حدث خطأ أثناء المعالجة، حاول مرة أخرى."

        data = response.json()

        if "candidates" not in data:
            print("No candidates:", data)
            return "لم أستطع توليد إجابة واضحة، أعد صياغة السؤال."

        ai_text = (
            data["candidates"][0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if not ai_text.strip():
            return "لم أتوصل لإجابة مناسبة."

        ai_text = ai_text.replace("{", "").replace("}", "").replace("[", "").replace("]", "")
        return ai_text.strip()

    except Exception as e:
        print("Gemini exception:", e)
        return "⚠️ خطأ تقني مؤقت."

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

                if "message" in event:
                    msg = event["message"]
                    user_text = msg.get("text", "")

                    for att in msg.get("attachments", []):
                        if att.get("type") == "image":
                            url = att.get("payload", {}).get("url")
                            if url:
                                user_text += "\n" + image_url_to_text(url)

                    if user_text:
                        push_history(sender_id, "user", user_text)
                        reply = get_gemini_response(user_text, sender_id)
                        push_history(sender_id, "assistant", reply)
                        fb_send_chunks(sender_id, reply)

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
