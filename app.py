import os
import requests
from flask import Flask, request
import google.generativeai as genai
from datetime import datetime

app = Flask(__name__)

# --- الحل 1: قراءة المفاتيح من متغيرات بيئة Render (إلزامي) ---
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
ADMIN_PASSWORD = "M2025"

custom_instructions = ""

# --- الحل 3: استخدام Gemini Flash لسرعة الاستجابة (مجاني تماماً) ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # استخدمنا flash لأنه أسرع ولا يسبب Timeout
    model = genai.GenerativeModel("gemini-1.5-flash")

def get_system_prompt():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"أنت خبير تعليمي موريتاني. المطور: محمد لمين أحمد جدو. تعليمات: {custom_instructions}. التاريخ: {now}"

# --- الحل 2: طباعة رد فيسبوك للتشخيص (مهم جداً) ---
def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    
    r = requests.post(url, params=params, json=payload)
    # سيظهر هذا في Logs بـ Render لنعرف سبب الفشل
    print(f"FB STATUS: {r.status_code}")
    print(f"FB RESPONSE: {r.text}")

@app.route("/", methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Bot Online", 200

@app.route("/", methods=['POST'])
def webhook():
    global custom_instructions
    data = request.json
    
    if data.get("object") == "page":
        for entry in data["entry"]:
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                if "message" in event:
                    msg = event["message"]
                    
                    if "text" in msg:
                        user_text = msg["text"]
                        
                        # اختبار سريع: رد تلقائي للتأكد من التوكن
                        # send_fb_message(sender_id, "✅ استلمت رسالتك، جاري التفكير...")

                        if user_text.startswith(ADMIN_PASSWORD):
                            custom_instructions = user_text.replace(ADMIN_PASSWORD, "").strip()
                            send_fb_message(sender_id, "✅ تم تحديث التعليمات.")
                            return "ok", 200

                        try:
                            # معالجة جيميناي
                            response = model.generate_content([get_system_prompt(), user_text])
                            send_fb_message(sender_id, response.text)
                        except Exception as e:
                            print(f"ERROR: {e}")
                            send_fb_message(sender_id, "⚠️ حدث ضغط على المحرك، حاول لاحقاً.")
                            
    return "ok", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
