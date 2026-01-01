import os
import requests
import base64
import threading # أضفت هذا لضمان عدم توقف البوت عند فيسبوك (Timeout)
from flask import Flask, request

app = Flask(__name__)

# ====== ENV ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# ====== مساعدات فيسبوك (نفس كودك الأصلي مع تحسين بسيط) ======
def send_fb_message(sender_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    # تقسيم النص لضمان وصول الرسائل الطويلة
    limit = 1900
    for i in range(0, len(text), limit):
        payload = {
            "recipient": {"id": sender_id},
            "message": {"text": text[i:i+limit].strip()}
        }
        requests.post(url, params=params, json=payload)

# ====== المحرك الذكي الجديد (هنا التطوير الحقيقي) ======
def get_ai_reply_multimodal(user_text, image_url=None):
    # المنهجية التعليمية التي طلبتها في الـ Prompt
    system_prompt = """
أنت مساعد تعليمي خبير. اتبع المنهجية التالية في الشرح بدقة:
1. الكل قبل الجزء: ابدأ بنظرة شاملة للسؤال وسياقه العلمي (الهدف النهائي).
2. التفكيك (ماذا، كيف، لماذا):
   - ماذا: ما هو المفهوم المستخدم؟
   - كيف: كيف نطبق القوانين خطوة بخطوة؟
   - لماذا: لماذا اخترنا هذا الطريق للحل؟
3. فقه السؤال: اربط الحل بكيفية الإجابة في الامتحان وتجنب الأخطاء الشائعة.

قواعد صارمة:
- اللغة: العربية المبسطة مع المصطلحات العلمية بالفرنسية.
- التنسيق: ممنوع استخدام رموز LaTeX مثل [ ] { } \frac. استخدم رموزاً بسيطة (مثلاً: / للقسمة، * للضرب).
- إذا كانت هناك صورة: حللها بصرياً بدقة (رسوم، جداول، معادلات).
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    parts = [{"text": f"{system_prompt}\n\nسؤال المستخدم: {user_text}"}]
    
    if image_url:
        try:
            img_data = requests.get(image_url).content
            encoded_img = base64.b64encode(img_data).decode()
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": encoded_img
                }
            })
        except:
            pass # في حال فشل جلب الصورة نعتمد على النص

    payload = {"contents": [{"parts": parts}]}
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        response_data = r.json()
        return response_data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"عذراً، واجهت مشكلة في معالجة الطلب. (Error: {str(e)})"

# وظيفة وسيطة للتعامل مع التوقيت (Threading)
def handle_async_reply(sender_id, user_text, image_url):
    reply = get_ai_reply_multimodal(user_text, image_url)
    send_fb_message(sender_id, reply)

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
                if not sender_id: continue

                msg = event.get("message", {})
                user_text = msg.get("text", "")
                image_url = None

                # التقاط الصورة مباشرة
                for att in msg.get("attachments", []):
                    if att.get("type") == "image":
                        image_url = att["payload"]["url"]

                if user_text or image_url:
                    # نستخدم threading هنا لأن معالجة الصور تأخذ وقتاً
                    # وبدونها سيعتقد فيسبوك أن البوت تعطل (Timeout)
                    thread = threading.Thread(target=handle_async_reply, args=(sender_id, user_text, image_url))
                    thread.start()

    return "ok", 200 # نرد فوراً على فيسبوك لتجنب قطع الاتصال

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
