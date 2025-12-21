import os
import requests
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# إعداد المكتبة مع فرض الإصدار المستقر v1
if GEMINI_API_KEY:
    genai.configure(
        api_key=GEMINI_API_KEY, 
        transport='rest',
        client_options={'api_version': 'v1'}
    )

def get_response_from_gemini(text):
    try:
        # استخدام موديل فلاش في الإصدار المستقر
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(text)
        return response.text
    except Exception as e:
        return f"Gemini API Error (v1): {str(e)}"

def send_fb_message(recipient_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages"
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
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                if "sender" in event and "message" in event:
                    sender_id = event["sender"]["id"]
                    if "text" in event["message"]:
                        user_text = event["message"]["text"]
                        
                        # تشخيص سريع للنماذج المتاحة عند طلب debug
                        if user_text.strip().lower() == "/debug":
                            try:
                                models = [m.name for m in genai.list_models()]
                                send_fb_message(sender_id, f"Models on v1: {models}")
                            except Exception as e:
                                send_fb_message(sender_id, f"Debug Error: {str(e)}")
                            continue

                        ai_reply = get_response_from_gemini(user_text)
                        send_fb_message(sender_id, ai_reply)
                            
    return "ok", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
