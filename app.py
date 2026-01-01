import os
import requests
import base64
import threading
from flask import Flask, request

app = Flask(__name__)

# ====== إعدادات البيئة (ENV) ======
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# ====== وظيفة إرسال الرسائل (تقسيم النص التلقائي) ======
def send_fb_message(sender_id, text):
    if not text: return
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    
    # تقسيم النص إذا تجاوز 2000 حرف (قيد فيسبوك)
    limit = 1900
    parts = [text[i:i+limit] for i in range(0, len(text), limit)]
    
    for part in parts:
        payload = {
            "recipient": {"id": sender_id},
            "message": {"text": part.strip()}
        }
        try:
            requests.post(url, params=params, json=payload, timeout=10)
        except Exception as e:
            print(f"Error sending message: {e}")

# ====== محرك الذكاء الاصطناعي (الرؤية والفهم التعليمي) ======
def ai_logic_background(sender_id, user_text, image_url=None):
    """ هذه الوظيفة تعمل في الخلفية لضمان عدم تأخير الرد على فيسبوك """
    try:
        # المنهجية التي طلبتها في سياق التعليمات
        system_instruction = (
            "أنت أستاذ خبير. اتبع هذه الخطوات في الإجابة:\n"
            "1. نظرة شاملة (الكل قبل الجزء): وضح السياق والهدف أولاً.\n"
            "2. التفكيك الوظيفي: اشرح ماذا وكيف ولماذا يعمل الشيء.\n"
            "3. التصاعد المنطقي: تدرج من البسيط للاستثناءات.\n"
            "4. فقه السؤال: اربط المعلومة بطريقة الامتحان والأخطاء الشائعة.\n"
            "ملاحظة: استخدم لغة عربية بسيطة ومصطلحات فرنسية علمية. "
            "ممنوع استخدام رموز LaTeX المعقدة (مثل \frac أو {}). استخدم رموزاً نصية بسيطة."
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        parts = [{"text": f"{system_instruction}\n\nسؤال المستخدم: {user_text}"}]
        
        # إذا أرسل المستخدم صورة، يتم دمجها مباشرة في الطلب
        if image_url:
            image_resp = requests.get(image_url, timeout=15)
            if image_resp.status_code == 200:
                img_base64 = base64.b64encode(image_resp.content).decode('utf-8')
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": img_base64
                    }
                })

        payload = {"contents": [{"parts": parts}]}
        response = requests.post(url, json=payload, timeout=35)
        
        if response.status_code == 200:
            res_json = response.json()
            answer = res_json['candidates'][0]['content']['parts'][0]['text']
            send_fb_message(sender_id, answer)
        else:
            send_fb_message(sender_id, "عذراً، يواجه الدماغ الرقمي ضغطاً حالياً. حاول مجدداً.")
            
    except Exception as e:
        print(f"Background Process Error: {e}")
        send_fb_message(sender_id, "حدث خطأ فني أثناء تحليل طلبك.")

# ====== Webhook (الاستلام والرد الفوري) ======
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

                # التقاط أول صورة في المرفقات إن وجدت
                if "attachments" in msg:
                    for att in msg["attachments"]:
                        if att["type"] == "image":
                            image_url = att["payload"]["url"]
                            break

                if user_text or image_url:
                    # السر هنا: تشغيل المعالجة في Thread والرد فوراً بـ 200 OK
                    thread = threading.Thread(
                        target=ai_logic_background, 
                        args=(sender_id, user_text, image_url)
                    )
                    thread.start()

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
