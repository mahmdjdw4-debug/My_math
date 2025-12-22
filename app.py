import os
import requests
from flask import Flask, request

app = Flask(__name__)

# الإعدادات من Render
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

def get_gemini_response(text):
    """
    محاولة استدعاء Gemini 2.0 Flash عبر مسار v1beta الموثق حديثاً.
    """
    # استخدام gemini-2.0-flash كما اقترح النموذج الآخر
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": text}]}]}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=25)
        response_data = response.json()
        
        # طباعة الحالة في سجلات Render للتشخيص
        print(f"Gemini Status: {response.status_code}")
        
        if response.status_code == 200 and 'candidates' in response_data:
            return response_data['candidates'][0]['content']['parts'][0]['text']
        else:
            # إذا فشل 2.0، نحاول العودة لـ 1.5 بشكل تلقائي
            return retry_with_15_flash(text)
            
    except Exception as e:
        return f"فشل في الاتصال: {str(e)}"

def retry_with_15_flash(text):
    """دالة احتياطية في حال عدم توفر إصدار 2.0"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    try:
        resp = requests.post(url, json={"contents": [{"parts": [{"text": text}]}]}, headers={'Content-Type': 'application/json'})
        data = resp.json()
        if 'candidates' in data:
            return data['candidates'][0]['content']['parts'][0]['text']
        return f"خطأ من جوجل (404): الموديل غير متاح لمفتاحك حالياً."
    except:
        return "عذراً، هناك مشكلة فنية في الوصول للنماذج."

def send_fb_message(recipient_id, text):
    fb_url = f"https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    requests.post(fb_url, params=params, json=payload)

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
