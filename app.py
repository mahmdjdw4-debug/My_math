import os
import requests
import base64
from flask import Flask, request

app = Flask(__name__)

# =======================
# إعدادات البيئة
# =======================
FB_PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "MySecretBot2024")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")

FB_MAX_CHUNK = 1900
MAX_HISTORY_MESSAGES = 4
conversation_memory = {}

# =======================
# أدوات مساعدة
# =======================
def chunk_text(text, max_len=FB_MAX_CHUNK):
    text = (text or "").strip()
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        cut = max(
            text.rfind("\n", 0, max_len),
            text.rfind(". ", 0, max_len),
            text.rfind(" ", 0, max_len),
        )
        if cut <= 0:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].strip()
    return chunks


def send_fb_message(recipient_id, text):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": FB_PAGE_ACCESS_TOKEN}
    for chunk in chunk_text(text):
        requests.post(
            url,
            params=params,
            json={"recipient": {"id": recipient_id}, "message": {"text": chunk}},
            timeout=15,
        )


def clean_math_text(text):
    bad = ["{", "}", "[", "]", "\\frac"]
    for b in bad:
        text = text.replace(b, "")
    return text


# =======================
# Prompt ذكي
# =======================
def build_prompt(sender_id, user_text):
    history = conversation_memory.get(sender_id, [])
    context = ""
    for h in history[-MAX_HISTORY_MESSAGES:]:
        context += f"المستخدم: {h['user']}\nالمساعد: {h['bot']}\n"

    system = """
أنت مساعد تعليمي متخصص في الفيزياء والرياضيات والعلوم.
الشرح بالعربية، والمصطلحات العلمية بالفرنسية.
اشرح لماذا قبل كيف.
أسلوب مبسط، مفصل، مرقم.
اكتب المعادلات بالكلمات فقط.
"""

    return system + "\n" + context + "\nسؤال المستخدم:\n" + user_text


# =======================
# Gemini (نص + صورة)
# =======================
def gemini_generate(parts):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    payload = {
        "contents": [{"parts": parts}],
        "temperature": 0.2,
        "max_output_tokens": 700,
    }

    r = requests.post(url, json=payload, headers=headers, timeout=40)
    if r.status_code != 200:
        print("Gemini error:", r.text)
        return "❌ حدث خطأ أثناء معالجة السؤال."
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def get_gemini_response(sender_id, user_text):
    if "من صنعك" in user_text or "من برمجك" in user_text:
        return (
            "صنعني شخص اسمه محمد الأمين أحمد جدو.\n"
            "هو شخص متواضع ولا يحب إعطاء معلومات عن نفسه."
        )

    prompt = build_prompt(sender_id, user_text)
    answer = gemini_generate([{"text": prompt}])
    answer = clean_math_text(answer)

    conversation_memory.setdefault(sender_id, []).append(
        {"user": user_text, "bot": answer}
    )

    return answer


# =======================
# Webhook
# =======================
@app.route("/", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "ok", 200


@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    if data and data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                sender_id = event["sender"]["id"]
                msg = event.get("message", {})

                # نص
                if "text" in msg:
                    reply = get_gemini_response(sender_id, msg["text"])
                    send_fb_message(sender_id, reply)

                # صورة
                if "attachments" in msg:
                    for att in msg["attachments"]:
                        if att["type"] == "image":
                            image_url = att["payload"]["url"]
                            img = requests.get(image_url).content
                            b64 = base64.b64encode(img).decode()

                            prompt = build_prompt(
                                sender_id,
                                "اشرح التمرين الموجود في الصورة شرحًا مفصلاً."
                            )

                            answer = gemini_generate([
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": b64,
                                    }
                                },
                            ])

                            send_fb_message(sender_id, clean_math_text(answer))

    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
