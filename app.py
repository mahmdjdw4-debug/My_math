import os
import requests
from flask import Flask, request
from google import genai

app = Flask(__name__)

# جلب المفاتيح من إعدادات Render
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# إعداد عميل Gemini الجديد
client = genai.Client(api_key=GEMINI_API_KEY)

def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    r = requests.post(url, params=params, json=payload)
    print(f"FB STATUS: {r.status_code}")

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
                        # الطريقة الصحيحة للمكتبة الجديدة
                        response = client.models.generate_content(
                            model="gemini-1.5-flash", 
                            contents=user_text
                        )
                        send_fb_message(sender_id, response.text)
                    except Exception as e:
                        print(f"Error: {str(e)}")
                        send_fb_message(sender_id, "أهلاً! المحرك يستعد، حاول مرة أخرى.")
    return "ok", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
