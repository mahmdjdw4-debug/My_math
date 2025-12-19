import os
import requests
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

# سحب المفاتيح من Render
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # التصحيح: استهداف النسخة المستقرة مباشرة
    model = genai.GenerativeModel('gemini-1.5-flash')

def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
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
        for entry in data["entry"]:
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                if "message" in event and "text" in event["message"]:
                    user_text = event["message"]["text"]
                    try:
                        # تعديل بسيط لضمان التوافق
                        response = model.generate_content(user_text)
                        if response.text:
                            send_fb_message(sender_id, response.text)
                        else:
                            send_fb_message(sender_id, "لم أستطع معالجة هذا الطلب، حاول مرة أخرى.")
                    except Exception as e:
                        # إرسال الخطأ الحقيقي للمتابعة
                        send_fb_message(sender_id, f"Error Detail: {str(e)}")
    return "ok", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
