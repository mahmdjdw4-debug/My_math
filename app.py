import os
import requests
import google.generativeai as genai
from flask import Flask, request
from PIL import Image
import io

app = Flask(__name__)

# ====== الإعدادات والمفاتيح ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# إعداد مكتبة Gemini الرسمية
genai.configure(api_key=GOOGLE_API_KEY)

# إعدادات الموديل (تخفيف القيود ليشرح العلوم بحرية)
generation_config = {
    "temperature": 0.3,  # دقة أعلى للإجابات العلمية
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 4000, # نسمح بإجابات طويلة جداً ليتم تقطيعها لاحقاً
    "response_mime_type": "text/plain",
}

# إعدادات الأمان (مهم جداً لأسئلة مثل نظرية التطور)
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash", # موديل سريع وذكي جداً مع الصور
    generation_config=generation_config,
    safety_settings=safety_settings
)

# ====== ذاكرة المؤقتة (اختيارية) ======
# ملاحظة: في Render النسخة المجانية، الذاكرة تمحى عند إعادة التشغيل.
# لغرض التبسيط سنعتمد على سياق الرسالة الحالية والصورة.
conversations = {} 

# ====== دوال المساعدة ======

def get_sender_identity_response():
    return "صنعني شخص اسمه محمد الامين احمد جدو. هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."

def split_message(text, limit=1900):
    """تقسيم النص الطويل إلى أجزاء آمنة لفيسبوك"""
    chunks = []
    while len(text) > limit:
        # حاول القص عند أقرب سطر جديد لتكون القراءة مريحة
        split_index = text.rfind('\n', 0, limit)
        if split_index == -1:
            split_index = text.rfind(' ', 0, limit)
        
        if split_index == -1:
            split_index = limit
            
        chunks.append(text[:split_index])
        text = text[split_index:].strip()
    
    if text:
        chunks.append(text)
    return chunks

def send_fb_message(recipient_id, text):
    """إرسال الرسالة مقسمة إلى فيسبوك"""
    if not text: return
    
    chunks = split_message(text)
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    
    for chunk in chunks:
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": chunk}
        }
        try:
            r = requests.post(url, json=payload)
            if r.status_code != 200:
                print(f"Error sending to FB: {r.text}")
        except Exception as e:
            print(f"Exception sending to FB: {e}")

def get_image_from_url(url):
    """تحميل الصورة وتجهيزها لجيمناي"""
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            image_data = response.content
            return Image.open(io.BytesIO(image_data))
    except Exception as e:
        print(f"Error downloading image: {e}")
    return None

def generate_gemini_response(user_text, image_obj=None):
    # 1. التحقق من سؤال الهوية أولاً
    if user_text:
        check_text = user_text.lower()
        if any(x in check_text for x in ["من صنعك", "من برمجك", "who made you", "خالقك", "مطورك"]):
            return get_sender_identity_response()

    # 2. بناء "السيستم برومبت" القوي
    system_instruction = """
    أنت معلم ذكي ومتميز متخصص في الفيزياء، الرياضيات، والعلوم.
    
    القواعد الصارمة لإجابتك:
    1. **اللغة:** اشرح باللغة العربية الفصحى المبسطة جداً، ولكن احتفظ بالمصطلحات العلمية (Scientific Terms) باللغة الفرنسية (مثل: Force, Vitesse, Energie).
    2. **الأسلوب:** لا تكتفِ بشرح "كيف" (How) بل اشرح "لماذا" (Why) دائماً. فصّل الإجابة تفصيلاً دقيقاً ومملاً.
    3. **التنسيق:** - استخدم الترقيم (1- ، 2- ...) للخطوات.
       - **ممنوع تماماً** استخدام كود LaTeX أو رموز مثل `\\frac`, `^{}`, `[]`, `{}`.
       - اكتب المعادلات بشكل نصي مفهوم (مثال: بدلاً من كسر، اكتب "القوة مقسومة على الكتلة").
       - اجعل النص مقروءاً لرسائل فيسبوك.
    4. **حل التمارين:** إذا أُرسلت صورة تمرين، استخرج المعطيات، اشرح القانون المستخدم، ثم الحل خطوة بخطوة.
    5. **الشخصية:** أنت صبور، ودود، وتحب التفاصيل.
    """
    
    prompts = [system_instruction]
    
    # إضافة الصورة إذا وجدت
    if image_obj:
        prompts.append("هذه صورة تمرين أو سؤال علمي. قم بتحليلها بدقة وحل ما فيها.")
        prompts.append(image_obj)
    
    if user_text:
        prompts.append(f"\nسؤال المستخدم: {user_text}")

    # طلب الإجابة من Gemini
    try:
        response = model.generate_content(prompts)
        return response.text
    except Exception as e:
        print(f"Gemini Error: {e}")
        # إذا كان الخطأ بسبب المحتوى، نحاول رسالة عامة
        return "واجهت مشكلة تقنية في معالجة هذا الطلب، حاول إعادة صياغة السؤال."

# ====== Webhook Handlers ======

@app.route("/", methods=["GET"])
def verify():
    # تأكيد ربط فيسبوك
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
                
                # نتجاهل رسائل البوت لنفسه أو حالات التسليم
                if not sender_id or "delivery" in event or "read" in event:
                    continue

                if "message" in event:
                    msg = event["message"]
                    user_text = msg.get("text", "")
                    
                    # التعامل مع الصور
                    image_obj = None
                    attachments = msg.get("attachments", [])
                    for att in attachments:
                        if att.get("type") == "image":
                            img_url = att.get("payload", {}).get("url")
                            image_obj = get_image_from_url(img_url)
                            # نأخذ أول صورة فقط حالياً
                            break 
                    
                    # نرسل "جاري الكتابة..." لأن الإجابة قد تتأخر
                    # (يمكن إضافة action: typing_on هنا اختيارياً)

                    # معالجة الطلب
                    if user_text or image_obj:
                        ai_reply = generate_gemini_response(user_text, image_obj)
                        send_fb_message(sender_id, ai_reply)

    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
