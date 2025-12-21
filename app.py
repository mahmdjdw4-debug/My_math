import os
import requests
from flask import Flask, request

app = Flask(__name__)

# الإعدادات - تأكد من إضافتها في Environment Variables على Render
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

def get_gemini_response(text):
    """
    الاتصال المباشر بـ Gemini API v1.
    هذه الطريقة تتجاوز مشاكل المكتبات وتضمن الوصول للموديل الصحيح.
    """
    # الرابط المباشر للإصدار المستقر v1
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [
            {
                "parts": [{"text": text}]
            }
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response_data = response.json()
        
        # 1. نجاح استخراج الرد
        if 'candidates' in response_data and len(response_data['candidates']) > 0:
            return response_data['candidates'][0]['content']['parts'][0]['text']
        
        # 2. تشخيص الخطأ القادم من جوجل (مثل مفتاح خاطئ أو منطقة محظورة)
        elif 'error' in response_data:
            error_msg = response_data['error'].get('message', 'Unknown Google Error')
            print(f"Google API Error: {error_msg}")
            return f"خطأ من جوجل: {error_msg}"
        
        # 3. أي استجابة أخرى غير متوقعة
        else:
            print(f"Unexpected JSON: {response_data}")
            return "استلمت رداً غير متوقع من الخادم."
            
    except Exception as e:
        print(f"Connection Error: {str(e)}")
        return f"خطأ في الاتصال: {str(e)}"

def send_fb_message(recipient_id, text):
    """إرسال الرسالة إلى فيسبوك Messenger"""
    fb_url = f"https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    try:
        r = requests.post(fb_url, params=params, json=payload)
        r.raise_for_status()
    except Exception as e:
        print(f"FB Send Error: {e}")

@app.route("/", methods=['GET'])
def verify():
    """التحقق من الـ Webhook عند الربط مع فيسبوك"""
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Bot is running...", 200

@app.route("/", methods=['POST'])
def webhook():
    """استقبال الرسائل من فيسبوك"""
    data = request.json
    if data and data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if sender_id and "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]
                    
                    # جلب الرد من Gemini
                    ai_reply = get_gemini_response(user_text)
                    
                    # إرسال الرد للمستخدم
                    send_fb_message(sender_id, ai_reply)
                            
    return "ok", 200

if __name__ == "__main__":
    # تشغيل السيرفر على المنفذ المخصص من Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
