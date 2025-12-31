import os
import requests
import base64
import io
from PIL import Image, ImageOps, ImageFilter, ImageEnhance
import pytesseract  # اختياري، يستخدم فقط إذا لم يتوفر Google Vision
from flask import Flask, request

app = Flask(__name__)

# ====== إعدادات البيئة المطلوبة ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# (اختياري لكن موصى به لمعالجة الصور)
VISION_API_KEY = os.environ.get("VISION_API_KEY")  # Google Cloud Vision REST API key (اختياري)

# ====== ذاكرة محادثات بسيطة في الذاكرة ======
conversations = {}
MAX_HISTORY_MESSAGES = 8  # حافظ على بعض السياق، لا تكبر كثيراً لتفادي تجاوز حدود المدخلات

# ====== Utilities ======
def push_history(sender_id, role, text):
    history = conversations.get(sender_id, [])
    history.append({"role": role, "text": text})
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    conversations[sender_id] = history

def build_prompt_from_history(sender_id, user_text, extra_note=""):
    # نظام/تعليمات أساسية تحكم سلوك المساعد:
    system_note = (
        "أنت مساعد ذكي متخصص في حل تمارين وشرح دروس الفيزياء، الرياضيات والعلوم. "
        "أجب باللغة العربية الفصحى المبسطة، وحافظ دائماً على المصطلحات العلمية باللغة الفرنسية كما هي (مثلاً: 'force', 'énergie', 'accélération'). "
        "عند الشرح لا تكتفِ بكيف (how) فقط، بل اشرح السبب (why) أيضاً. "
        "أجب بطريقة مُرقَّمة (1., 2., 3., ...) إذا كان الشرح يحتوي على خطوات أو نقاط. "
        "لا تستخدم رموز تقنية غير مفهومة مثل []{}fraq. ردودك يجب أن تكون مفهومة للطالب."
    )
    if extra_note:
        system_note += " " + extra_note

    parts = [system_note, "\n--- محادثة سابقة ---\n"]
    history = conversations.get(sender_id, [])
    for item in history:
        role = "المستخدم" if item["role"] == "user" else "المساعد"
        parts.append(f"{role}: {item['text']}\n")
    parts.append("\nالمستخدم (الجديد): " + user_text + "\n")
    parts.append("\nالمطلوب: أجب بشمولية وتفصيل مبسّط، رَقّم النقاط، واذكر السبب والتوضيح. إن كان هناك معادلات اشرح خطوات الحل. احرص أن تكون الإجابة نصاً واضحاً قابلاً للنسخ.")
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
    fb_url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    for chunk in chunk_text(full_text, max_len=1900):
        payload = {"recipient": {"id": recipient_id}, "message": {"text": chunk}}
        r = requests.post(fb_url, params=params, json=payload)
        print("FB send status:", r.status_code, r.text)

# ====== Image OCR helpers ======
def preprocess_image_for_ocr(image: Image.Image) -> Image.Image:
    # تحويل إلى رمادي، تحسين التباين، إزالة الضوضاء الخفيفة
    img = ImageOps.grayscale(image)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.4)
    img = img.resize((int(img.width*1.5), int(img.height*1.5)), Image.LANCZOS)
    return img

def ocr_with_pytesseract(image_content_bytes):
    try:
        image = Image.open(io.BytesIO(image_content_bytes))
        image = preprocess_image_for_ocr(image)
        text = pytesseract.image_to_string(image, lang='eng+fra+ara')  # إن وُجدت اللغات
        return text.strip()
    except Exception as e:
        print("pytesseract error:", e)
        return ""

def ocr_with_google_vision(image_content_bytes):
    # يستخدم Google Cloud Vision REST API (تحتاج VISION_API_KEY)
    try:
        encoded = base64.b64encode(image_content_bytes).decode('utf-8')
        url = f"https://vision.googleapis.com/v1/images:annotate?key={VISION_API_KEY}"
        payload = {
            "requests": [
                {
                    "image": {"content": encoded},
                    "features": [{"type": "TEXT_DETECTION", "maxResults": 1}]
                }
            ]
        }
        r = requests.post(url, json=payload, timeout=30)
        print("Vision status:", r.status_code)
        data = r.json()
        text = ""
        try:
            text = data["responses"][0].get("fullTextAnnotation", {}).get("text", "")
        except Exception as e:
            print("Vision parse error:", e, data)
        return text.strip()
    except Exception as e:
        print("Vision API error:", e)
        return ""

def image_url_to_text(image_url):
    try:
        r = requests.get(image_url, timeout=20)
        if r.status_code != 200:
            print("Image download failed", r.status_code)
            return ""
        img_bytes = r.content

        # إذا كان مفتاح Vision معرفًا نستخدمه (مفضل على Render)
        if VISION_API_KEY:
            text = ocr_with_google_vision(img_bytes)
            if text:
                return text

        # فالاً باك: استخدم pytesseract إن متاح
        text = ocr_with_pytesseract(img_bytes)
        return text
    except Exception as e:
        print("image_url_to_text exception:", e)
        return ""

# ====== Gemini interaction (نفس واجهة generateContent مع تحسينات) ======
def get_gemini_response(user_text, sender_id, allow_long=True):
    # إذا المستخدم سأل "من صنعك" أو "من برمجك" نجاوب بصياغة محددة
    lowered = user_text.strip().lower()
    if ("من صنعك" in lowered) or ("من برمجك" in lowered) or ("who made you" in lowered):
        # إجابة مُحددة كما طلبت
        return "صنعني شخص اسمه محمد الأمين أحمد جدو. هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."

    prompt_text = build_prompt_from_history(sender_id, user_text)

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    # نطلب إجابات أطول وشاملة: زيادة max_output_tokens ودرجة عشوائية منخفضة
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "temperature": 0.2,
        "max_output_tokens": 1200  # إن بقيت الواجهة تدعم هذا الحقل
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=40)
        print("Gemini status:", response.status_code)
        print("Gemini raw:", response.text[:2000])  # لا نطبع كل شيء في اللوج لو طويل

        if response.status_code == 200:
            data = response.json()
            try:
                ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                print("Parsing error:", e)
                return "❌ لم أفهم رد النموذج تمامًا."
            # نظف النص: إزالة أي رموز غريبة بداية/نهاية
            ai_text = ai_text.replace("[", "").replace("]", "").replace("{", "").replace("}", "")
            return ai_text.strip()
        else:
            # طباعة الخطأ الكامل سيساعد في التشخيص
            print("Gemini error response:", response.text)
            return f"❌ خطأ من موديل Gemini: {response.status_code}. راجع سجلات الخادم."
    except Exception as e:
        print("Gemini exception:", e)
        return f"⚠️ خطأ تقني في الاتصال بـ Gemini: {str(e)}"

# ====== Webhook handlers ======
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
    print("Webhook data:", data)

    if data and data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if not sender_id:
                    continue

                # 1) إذا الرسالة تحتوي نص
                if "message" in event:
                    msg = event["message"]
                    # معالجة الصور المرفقة أولاً (إن وُجدت)
                    extracted_texts = []
                    attachments = msg.get("attachments", [])
                    for att in attachments:
                        if att.get("type") == "image":
                            # بعض الويبهوك يعطي url في payload->url
                            url = att.get("payload", {}).get("url")
                            if url:
                                ocr_text = image_url_to_text(url)
                                if ocr_text:
                                    extracted_texts.append(ocr_text)

                    # لو يوجد نص تعبيري من الصورة، ندمجه مع نص المستخدم ليكون السؤال واضحًا
                    user_text = msg.get("text", "")
                    if extracted_texts:
                        # نلصق النص المستخرج مع تحفيز واضح
                        combined = user_text + "\n\n" + "نص الصورة المستخرج:\n" + "\n---\n".join(extracted_texts)
                        user_text = combined

                    if user_text:
                        push_history(sender_id, "user", user_text)
                        ai_reply = get_gemini_response(user_text, sender_id)
                        push_history(sender_id, "assistant", ai_reply)
                        fb_send_chunks(sender_id, ai_reply)

    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
