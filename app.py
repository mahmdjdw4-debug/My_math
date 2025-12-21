import os
import requests
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

# إعداد المكتبة
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY, transport='rest')

# دالة ذكية لاختيار النموذج المتاح
def get_response_from_gemini(text):
    try:
        # المحاولة الأولى: النموذج السريع والاقتصادي
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(text)
        return response.text
    except Exception as e_flash:
        print(f"Flash Failed: {e_flash}")
        try:
            # المحاولة الثانية: النموذج القياسي (أكثر استقراراً في بعض المناطق)
            model_backup = genai.GenerativeModel('gemini-pro')
            response = model_backup.generate_content(text)
            return response.text
        except Exception as e_pro:
            # إذا فشل الاثنان، نعيد رسالة الخطأ التقنية للتشخيص
            return f"Error: Models failed. Flash: {str(e_flash)} | Pro: {str(e_pro)}"

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
                        
                        # --- كود التشخيص السري ---
                        # إذا أرسلت كلمة /debug للبوت، سيرد عليك بقائمة النماذج المتاحة
                        if user_text.strip() == "/debug":
                            try:
                                available_models = [m.name for m in genai.list_models()]
                                debug_msg = "Available Models:\n" + "\n".join(available_models)
                                send_fb_message(sender_id, debug_msg[:1900]) # قص الرسالة لتناسب فيسبوك
                            except Exception as e:
                                send_fb_message(sender_id, f"Debug Error: {str(e)}")
                            continue
                        # -------------------------

                        # معالجة الرسالة العادية
                        ai_reply = get_response_from_gemini(user_text)
                        send_fb_message(sender_id, ai_reply)
                            
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
