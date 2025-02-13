from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import os
import json
import requests

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")  # URL ของ Google Apps Script

# ตรวจสอบว่าตั้งค่า ENV Variables ครบหรือยัง
if not all([LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, GOOGLE_SCRIPT_URL]):
    raise ValueError("Missing API keys. Please set all required environment variables.")

# ตั้งค่า LINE Bot API
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# ฟังก์ชันส่งข้อความกลับไปที่ LINE
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

# ฟังก์ชันค้นหาข้อมูลจาก Google Sheets
def get_user_info_from_sheets(name):
    try:
        response = requests.get(GOOGLE_SCRIPT_URL, params={"name": name})
        data = response.json()
        
        if data.get("status") == "success" and "user_info" in data:
            user_info = data["user_info"]
            message = (
                f"👤 ข้อมูลของ {user_info.get('ชื่อ', 'ไม่ระบุ')}\n"
                f"เพศ: {user_info.get('เพศ', 'ไม่ระบุ')}\n"
                f"อายุ: {user_info.get('อายุ', 'ไม่ระบุ')}\n"
                f"สถานะ: {user_info.get('สถานะ', 'ไม่ระบุ')}\n"
                f"คะแนนซึมเศร้า: {user_info.get('คะแนนซึมเศร้า', 'ไม่ระบุ')}\n"
                f"ระดับความเสี่ยงซึมเศร้า: {user_info.get('ระดับความเสี่ยงซึมเศร้า', 'ไม่ระบุ')}\n"
                f"คะแนนฆ่าตัวตาย: {user_info.get('คะแนนฆ่าตัวตาย', 'ไม่ระบุ')}\n"
                f"ระดับความเสี่ยงฆ่าตัวตาย: {user_info.get('ระดับความเสี่ยงฆ่าตัวตาย', 'ไม่ระบุ')}"
            )
            return message
        else:
            return f"❌ ไม่พบข้อมูลของ {name}"
    except Exception as e:
        return f"⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อกับฐานข้อมูล: {str(e)}"

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
                    event_mode = event.get('mode')
                    reply_token = event.get('replyToken')
                    message = event.get('message', {})
                    message_type = message.get('type')
                    user_message = message.get('text')
                    user_id = event.get('source', {}).get('userId')

                    if event_mode == "standby" or not reply_token or not user_message:
                        continue

                    # ค้นหาข้อมูลใน Google Sheets
                    response_message = get_user_info_from_sheets(user_message)

                    # ตอบกลับผู้ใช้
                    ReplyMessage(reply_token, response_message)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  
    app.run(debug=True, host="0.0.0.0", port=port)
