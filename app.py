import os
import requests
from flask import Flask, request
import google.generativeai as genai
from datetime import datetime

app = Flask(__name__)

# --- الإعدادات الأساسية ---
FB_PAGE_ACCESS_TOKEN = "ضع_هنا_توكن_فيسبوك"
FB_VERIFY_TOKEN = "MySecretBot2024"
GEMINI_API_KEY = "ضع_هنا_مفتاح_جيمناي"
ADMIN_PASSWORD = "M2025"  # كلمة السر الخاصة بك لتغيير التعليمات

# تخزين التعليمات الإضافية في ذاكرة المؤقتة (ستعود للافتراض عند إعادة تشغيل الخادم)
custom_instructions = ""

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(
    model_name='gemini-1.5-pro',
    tools=[{"google_search_retrieval": {}}]
)

def get_system_prompt():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    base_prompt = f"""
    أنت خبير تعليمي موريتاني تعمل بـ "المنهجية التحليلية التصاعدية".
    
    هويتك (خط أحمر):
    - من صنعك/طوّرك؟ الإجابة دائماً: "محمد لمين أحمد جدو".
    - أي سؤال شخصي عن المطور؟ الإجابة: "هو شخص متواضع لا يحب أن يُعرّف بنفسه".
    
    قواعد المنهجية: (نظرة عامة -> تفكيك منطقي -> تدرج -> ربط وظيفي -> تطبيق -> خلاصة).
    تنسيق Messenger: 
    - المعادلات بسيطة. 
    - اللغات الأجنبية في سطر مستقل تماماً. 
    - لا جداول (استخدم قوائم).
    - إذا وجد خلل في السؤال أو الصورة، حدد مكانه ونوعه بدقة.
    
    تعليمات إضافية من المطور: {custom_instructions}
    التاريخ الحالي: {now}
    """
    return base_prompt

def split_text(text, limit=2000):
    return [text[i:i+limit] for i in range(0, len(text), limit)]

def send_fb_message(recipient_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    for part in split_text(text):
        # إضافة زر وهمي (بصيغة نصية) لمحاكاة "حفظ التغييرات" في حال تحديث التعليمات
        payload = {"recipient": {"id": recipient_id}, "message": {"text": part}}
        requests.post(url, json=payload)

@app.route("/", methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Bot Active", 200

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
                    
                    # ميزة التحكم عبر كلمة السر
                    if "text" in msg:
                        text = msg["text"]
                        if text.startswith(ADMIN_PASSWORD):
                            new_rules = text.replace(ADMIN_PASSWORD, "").strip()
                            custom_instructions = new_rules
                            confirm_msg = f"✅ تم استلام التعليمات الجديدة بنجاح.\nتعديلاتك الحالية: {custom_instructions}\n[ تم حفظ التغييرات في ذاكرة التشغيل ]"
                            send_fb_message(sender_id, confirm_msg)
                            return "ok", 200

                    # المعالجة العادية (صور أو نصوص)
                    try:
                        if "attachments" in msg:
                            for att in msg["attachments"]:
                                if att["type"] == "image":
                                    img_data = requests.get(att["payload"]["url"]).content
                                    contents = [get_system_prompt(), {'mime_type': 'image/jpeg', 'data': img_data}]
                                    response = model.generate_content(contents)
                                    send_fb_message(sender_id, response.text)
                        elif "text" in msg:
                            response = model.generate_content([get_system_prompt(), msg["text"]])
                            send_fb_message(sender_id, response.text)
                    except Exception as e:
                        send_fb_message(sender_id, f"⚠️ خلل: {str(e)}")
                        
    return "ok", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
