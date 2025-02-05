from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import os
import openai
import json
import requests

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
ADMIN_USER_ID = os.getenv("LINE_ADMIN_USER_ID")
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")  # URL ของ Google Apps Script
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")  # URL ของ Make.com Webhook

# ตรวจสอบว่าได้ตั้งค่า ENV Variables ครบหรือยัง
if not all([OPENAI_API_KEY, LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, ADMIN_USER_ID]):
    raise ValueError("Missing API keys. Please set all required environment variables.")

# ตั้งค่า OpenAI และ LINE Bot API
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# เก็บประวัติการสนทนา
conversation_history = {}

# ฟังก์ชันส่งข้อความตอบกลับ
def ReplyMessage(reply_token, text_message):
    LINE_API = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text_message}]
    }
    try:
        response = requests.post(LINE_API, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error sending reply to LINE API: {e}")

# ฟังก์ชันบันทึกข้อความลง Google Sheets ผ่าน Apps Script
def save_to_google_sheets(user_id, message):
    if not GOOGLE_SCRIPT_URL:
        app.logger.warning("GOOGLE_SCRIPT_URL is not set! Skipping Google Sheets logging.")
        return
    
    data = {"user_id": user_id, "message": message}
    try:
        response = requests.post(GOOGLE_SCRIPT_URL, json=data)
        response.raise_for_status()
        app.logger.info("Message saved to Google Sheets successfully.")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error sending data to Google Sheets: {e}")

# ฟังก์ชัน OpenAI สำหรับประมวลผลข้อความ
def get_openai_response(user_id, user_message):
    global conversation_history
    history = conversation_history.get(user_id, [])
    history.append({"role": "user", "content": user_message})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a helpful assistant, YOU MUST RESPOND IN THAI"}] + history,
            max_tokens=200,
            temperature=0.7,
            stop=["\n\n"]
        )
        bot_reply = response["choices"][0]["message"]["content"]
        history.append({"role": "assistant", "content": bot_reply})
        conversation_history[user_id] = history[-10:]  # เก็บประวัติแค่ 10 ข้อความล่าสุด
        return bot_reply
    except Exception as e:
        app.logger.error(f"Error from OpenAI API: {e}")
        return "เกิดข้อผิดพลาด กรุณาลองใหม่"

# ฟังก์ชันส่งข้อมูลไปยัง Make.com (ถ้าต้องการ)
def send_to_make(user_id, user_message, response_message):
    if not MAKE_WEBHOOK_URL:
        app.logger.warning("MAKE_WEBHOOK_URL is not set! Skipping sending to Make.com.")
        return
    
    data = {
        "user_id": user_id,
        "user_message": user_message,
        "response_message": response_message
    }
    try:
        response = requests.post(MAKE_WEBHOOK_URL, json=data)
        response.raise_for_status()
        app.logger.info("Data sent to Make.com successfully.")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error sending data to Make.com: {e}")

# Webhook สำหรับ LINE Bot
@app.route('/webhook', methods=['POST', 'GET']) 
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            app.logger.info(f"Received request: {json.dumps(req, ensure_ascii=False)}")  

            if 'events' in req:
                for event in req['events']:
                    event_type = event.get('type')
                    event_mode = event.get('mode')  # ตรวจสอบ mode
                    reply_token = event.get('replyToken')
                    message = event.get('message', {})
                    message_type = message.get('type')
                    user_message = message.get('text')
                    user_id = event.get('source', {}).get('userId')

                    # ตรวจสอบว่าเหตุการณ์อยู่ในโหมด standby หรือไม่
                    if event_mode == "standby":
                        app.logger.info("Skipping event in standby mode. No new user message.")
                        continue

                    # ข้าม event ถ้าไม่มีข้อความหรือ reply_token
                    if not reply_token or not user_message:
                        app.logger.info("Skipping event with no reply_token or text message")
                        continue

                    # บันทึกข้อความลง Google Sheets
                    save_to_google_sheets(user_id, user_message)

                    # ส่งข้อความจาก OpenAI
                    response_message = get_openai_response(user_id, user_message)
                    ReplyMessage(reply_token, response_message)

                    # ส่งข้อมูลไปยัง Make.com
                    send_to_make(user_id, user_message, response_message)
            
            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  
    app.run(debug=True, host="0.0.0.0", port=port)
