from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
import os
import json
import requests
import openai

# ตั้งค่าตัวแปร Environment
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, GOOGLE_SCRIPT_URL, OPENAI_API_KEY]):
    raise ValueError("Missing API keys. Please set all required environment variables.")

# ตั้งค่า API Keys
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# ตัวแปรเก็บประวัติการสนทนา
conversation_history = {}

# ✅ ฟังก์ชันส่ง Flex Message สำหรับแบบประเมิน
def ReplyAssessmentMessage(reply_token):
    print("✅ Sending Assessment Message")  # Debug log
    
    flex_message = {
        "type": "flex",
        "altText": "เลือกแบบประเมินที่ต้องการ 📋",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "เลือกแบบประเมินที่ต้องการ 📋", "weight": "bold", "size": "lg"},
                    {"type": "text", "text": "กรุณาเลือกแบบประเมินที่ต้องการ", "size": "md", "margin": "md"},
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#5AACFF",
                        "action": {
                            "type": "uri",
                            "label": "แบบประเมินโรคซึมเศร้า",
                            "uri": "https://forms.gle/ZmUfLVDKkjBXAVbx8"
                        }
                    },
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#FF6B6B",
                        "action": {
                            "type": "uri",
                            "label": "แบบประเมินการฆ่าตัวตาย",
                            "uri": "https://forms.gle/jxurYZrY4dGgPUKJA"
                        }
                    }
                ]
            }
        }
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {
        "replyToken": reply_token,
        "messages": [flex_message]
    }

    print(f"📤 Flex Message JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")  # Debug JSON
    
    response = requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)
    print(f"🔄 LINE API Response: {response.status_code} {response.text}")  # Debug Response

# ✅ ฟังก์ชันส่งข้อความกลับไปยัง LINE
def ReplyMessage(reply_token, message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": message}] if isinstance(message, str) else [message]
    }
    
    response = requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)
    print(f"🔄 LINE API Response: {response.status_code} {response.text}")  # Debug Response

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            print(f"📩 Received Request: {json.dumps(req, indent=2, ensure_ascii=False)}")  # Debug Request

            for event in req.get('events', []):
                reply_token = event.get('replyToken')
                user_id = event.get('source', {}).get('userId')
                user_message = event.get('message', {}).get('text', "").strip()

                print(f"📩 Received message: {user_message}")  # Debug message

                if not reply_token or not user_message:
                    continue

                if user_message == "พูดคุย":
                    conversation_history[user_id] = []
                    ReplyMessage(reply_token, "เริ่มต้นการพูดคุยกันเถอะ! 😊")
                elif user_message == "แบบประเมิน":
                    ReplyAssessmentMessage(reply_token)
                else:
                    ReplyMessage(reply_token, "ขออภัย ฉันไม่เข้าใจคำสั่งนี้ 😔")

            return 'OK'
        except Exception as e:
            app.logger.error(f"🔥 Error in webhook handler: {e}")
            return 'ERROR'
    return 'Hello World'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
