import os
import requests
from flask import Flask, request
import google.generativeai as genai  # استخدام المكتبة القياسية

app = Flask(__name__)

# إعدادات البيئة
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# تهيئة Gemini SDK
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY is missing!")

# إعداد النموذج (يمكنك تغيير generation_config هنا إذا أردت)
model = genai.GenerativeModel('gemini-1.5-flash')

def send_fb_message(recipient_id, text):
    # استخدام الإصدار الأحدث من Graph API (v21.0 جيد، لكن v19.0+ كافٍ)
    url = f"https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    # فيسبوك يتطلب أحياناً تقسيم الرسائل الطويلة (أكثر من 2000 حرف)
    # لكن سنرسلها كما هي للتبسيط الآن
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    
    try:
        r = requests.post(url, params=params, json=payload)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message: {e}")

@app.route("/", methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Bot Online", 200

@app.route("/", methods=['POST'])
def webhook():
    data = request.json
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                if "sender" in event and "message" in event:
                    sender_id = event["sender"]["id"]
                    if "text" in event["message"]:
                        user_text = event["message"]["text"]
                        
                        # -- بداية منطق Gemini --
                        try:
                            # استدعاء مباشر وسلس للنموذج
                            response = model.generate_content(user_text)
                            
                            # التأكد من وجود نص في الرد (أحياناً يتم حجب الرد بسبب Safety Filters)
                            if response.text:
                                reply_text = response.text
                            else:
                                reply_text = "عذراً، لم أتمكن من صياغة رد مناسب."
                                
                            send_fb_message(sender_id, reply_text)
                            
                        except Exception as e:
                            print(f"Gemini API Error: {e}")
                            send_fb_message(sender_id, "واجهت مشكلة تقنية بسيطة، حاول مرة أخرى لاحقاً.")
                        # -- نهاية منطق Gemini --
                        
    return "ok", 200

if __name__ == "__main__":
    # استخدام المنفذ الذي تحدده Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
