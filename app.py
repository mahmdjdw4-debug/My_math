import os
import requests
from flask import Flask, request

app = Flask(__name__)

# الإعدادات - تأكد من تحديث GOOGLE_API_KEY بالمفتاح الجديد في Render
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

def get_gemini_response(text):
    """
    دالة ذكية تحاول الوصول للموديل عبر مسارين مختلفين لتجاوز خطأ الـ 404.
    """
    # قائمة بالروابط المحتملة (المستقرة والبيتا)
    endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    ]
    
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": text}]}]}
    
    last_error = ""
    
    for url in endpoints:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response_data = response.json()
            
            # إذا نجح الاستخراج من هذا الرابط
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                return response_data['candidates'][0]['content']['parts'][0]['text']
            
            # تخزين الخطأ وتجربة الرابط التالي
            if 'error' in response_data:
                last_error = response_data['error'].get('message', 'Unknown Error')
        except Exception as e:
            last_error = str(e)
            continue
            
    return f"عذراً، لم أستطع الوصول للموديل. آخر خطأ: {last_error}"

def send_fb_message(recipient_id, text):
    fb_url = f"https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    try:
        requests.post(fb_url, params=params, json=payload)
    except Exception as e:
        print(f"FB Send Error: {e}")

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
                    ai_reply = get_gemini_response(user_text)
                    send_fb_message(sender_id, ai_reply)
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
