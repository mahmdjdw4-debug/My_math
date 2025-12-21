import os
import requests
from flask import Flask, request

app = Flask(__name__)

# جلب الإعدادات من بيئة Render
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

def get_gemini_response(text):
    """طلب مباشر لـ Gemini لضمان العمل وتجنب خطأ 404"""
    # الرابط يستخدم v1 صراحة لتجاوز مشكلة v1beta
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": text}]}]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response_data = response.json()
        
        # استخراج الرد
        if 'candidates' in response_data:
            return response_data['candidates'][0]['content']['parts'][0]['text']
        else:
            return "عذراً، واجهت مشكلة في فهم الرسالة."
    except Exception as e:
        return "حدث خطأ في الاتصال بالذكاء الاصطناعي."

def send_fb_message(recipient_id, text):
    """إرسال الرد لفيسبوك"""
    url = f"https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(url, params=params, json=payload)

@app.route("/", methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Bot Online", 200

@app.route("/", methods=['POST'])
def webhook():
    data = request.json
    if data and data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event.get("sender", {}).get("id")
                if sender_id and "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]
                    # جلب الرد وإرساله
                    reply = get_gemini_response(user_text)
                    send_fb_message(sender_id, reply)
    return "ok", 200

if __name__ == "__main__":
    # هذا التنسيق ضروري لـ Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
