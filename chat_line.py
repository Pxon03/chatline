from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import requests as requests_lib
import os
import openai
import json

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
ADMIN_USER_ID = os.getenv("LINE_ADMIN_USER_ID")

# ตรวจสอบค่า ENV Variables
if not all([OPENAI_API_KEY, LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, ADMIN_USER_ID]):
    raise ValueError("Missing API keys. Please set required environment variables.")

# ตั้งค่า OpenAI และ LINE Bot API
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

conversation_history = {}
GOOGLE_FORM_URL = "https://forms.gle/bVhHWbuNLPYrqqjG7"

# ฟังก์ชันส่งข้อความตอบกลับ
def ReplyMessage(reply_token, text_message):
    if not reply_token:
        app.logger.error("Missing replyToken")
        return
    
    LINE_API = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = json.dumps({"replyToken": reply_token, "messages": [{"type": "text", "text": text_message}]})
    
    try:
        response = requests_lib.post(LINE_API, headers=headers, data=data)
        response.raise_for_status()
    except requests_lib.exceptions.RequestException as e:
        app.logger.error(f"Error sending reply: {e}")
        return

# ฟังก์ชัน OpenAI
def get_openai_response(user_id, user_message):
    history = conversation_history.get(user_id, [])
    history.append({"role": "user", "content": user_message})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a helpful assistant, respond in Thai."}] + history,
            max_tokens=200,
            temperature=0.7
        )
        bot_reply = response["choices"][0]["message"]["content"]
        history.append({"role": "assistant", "content": bot_reply})
        conversation_history[user_id] = history[-10:]
        return bot_reply
    except Exception as e:
        app.logger.error(f"OpenAI error: {e}")
        return "เกิดข้อผิดพลาด กรุณาลองใหม่"

# Webhook สำหรับ LINE Bot
@app.route('/', methods=['GET'])
def home():
    return "Line Bot Running", 200

@app.route('/webhook', methods=['POST']) 
def webhook():
    try:
        req = request.json
        if not req or 'events' not in req:
            return jsonify({"error": "Invalid request"}), 400
        
        for event in req['events']:
            if event.get('type') == 'message' and event['message'].get('type') == 'text':
                reply_token = event.get('replyToken')
                user_message = event['message']['text']
                user_id = event['source'].get('userId')
                
                if not reply_token or not user_id:
                    app.logger.error("Missing replyToken or userId")
                    continue
                
                if "แบบสอบถาม" in user_message:
                    ReplyMessage(reply_token, f"กรุณากรอกแบบสอบถามที่นี่: {GOOGLE_FORM_URL}")
                else:
                    response_message = get_openai_response(user_id, user_message)
                    ReplyMessage(reply_token, response_message)
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app.logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
