import os
import requests
from flask import Flask, request
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

app = Flask(__name__)

FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# 1. تهيئة Gemini مع فرض استخدام REST بدلاً من GRPC لتجنب مشاكل المنافذ في Render
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY, transport='rest')

# 2. إعدادات الأمان: السماح بكل شيء (للتجربة والتشخيص)
# هذا يمنع النموذج من حجب الردود مما يسبب خطأ عند طلب .text
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

model = genai.GenerativeModel(
    'gemini-1.5-flash',
    safety_settings=safety_settings
)

def send_fb_message(recipient_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    try:
        requests.post(url, params=params, json=payload)
    except Exception as e:
        print(f"Facebook Send Error: {e}")

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
                        
                        try:
                            # طباعة النص الواصل في الـ Log للتأكد
                            print(f"Received text: {user_text}")
                            
                            response = model.generate_content(user_text)
                            
                            # التحقق الآمن من الرد
                            # إذا تم الحجب، response.text ترمي خطأ، لذلك نتحقق من الأجزاء
                            if response.candidates and response.candidates[0].content.parts:
                                reply_text = response.text
                            else:
                                # في حال رد النموذج فارغاً أو محجوباً رغم الإعدادات
                                reply_text = "وصلت رسالتك لكن لم أستطع توليد رد (Blocked/Empty)."
                                print(f"Feedback: {response.prompt_feedback}")

                            send_fb_message(sender_id, reply_text)
                            
                        except Exception as e:
                            # هذا السطر هو الأهم: سيطبع الخطأ الحقيقي في Render Logs
                            print(f"CRITICAL GEMINI ERROR: {str(e)}")
                            # إرسال رسالة الخطأ للمستخدم أيضاً للمساعدة في التشخيص السريع
                            send_fb_message(sender_id, f"Error: {str(e)}")
                            
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
