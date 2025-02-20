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

if not all([LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, GOOGLE_SCRIPT_URL]):
    raise ValueError("Missing API keys. Please set all required environment variables.")

# ตั้งค่า LINE Bot API
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

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

def get_user_info(name, sheet_name):
    try:
        params = {
            "name": name,
            "sheetName": sheet_name
        }
        response = requests.get(GOOGLE_SCRIPT_URL, params=params)
        data = response.json()

        if data.get("status") == "success" and "user_info" in data:
            return data["user_info"]
        else:
            return None
    except Exception as e:
        app.logger.error(f"Error fetching user info: {e}")
        return None

def format_user_info(name, depression_info, suicide_info):
    if not depression_info and not suicide_info:
        return f"❌ ไม่พบข้อมูลของ {name}"

    message = f"👤 ข้อมูลของ {name}\n"

    if depression_info:
        message += (
            f"[แบบประเมินโรคซึมเศร้า]\n"
            f"เพศ: {depression_info.get('เพศ', 'ไม่ระบุ')}\n"
            f"อายุ: {depression_info.get('อายุ', 'ไม่ระบุ')}\n"
            f"สถานะ: {depression_info.get('สถานะ', 'ไม่ระบุ')}\n"
            f"คะแนนซึมเศร้า: {depression_info.get('คะแนนซึมเศร้า', 'ไม่ระบุ')}\n"
            f"ระดับความเสี่ยงซึมเศร้า: {depression_info.get('ระดับความเสี่ยงซึมเศร้า', 'ไม่ระบุ')}\n\n"
        )

    if suicide_info:
        message += (
            f"[แบบประเมินการฆ่าตัวตาย]\n"
            f"เพศ: {suicide_info.get('เพศ', 'ไม่ระบุ')}\n"
            f"อายุ: {suicide_info.get('อายุ', 'ไม่ระบุ')}\n"
            f"สถานะ: {suicide_info.get('สถานะ', 'ไม่ระบุ')}\n"
            f"คะแนนฆ่าตัวตาย: {suicide_info.get('คะแนนฆ่าตัวตาย', 'ไม่ระบุ')}\n"
            f"ระดับความเสี่ยงฆ่าตัวตาย: {suicide_info.get('ระดับความเสี่ยงฆ่าตัวตาย', 'ไม่ระบุ')}"
        )

    return message

@app.route('/webhook', methods=['POST', 'GET']) 
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            app.logger.info(f"Received request: {json.dumps(req, ensure_ascii=False)}")

            if 'events' in req:
                for event in req['events']:
                    reply_token = event.get('replyToken')
                    message = event.get('message', {})
                    user_message = message.get('text')

                    if not reply_token or not user_message:
                        continue

                    # ค้นหาข้อมูลจากแต่ละแผ่น
                    depression_info = get_user_info(user_message, "ซึมเศร้า")
                    suicide_info = get_user_info(user_message, "ฆ่าตัวตาย")

                    # สร้างข้อความตอบกลับ
                    response_message = format_user_info(user_message, depression_info, suicide_info)

                    # ส่งข้อความกลับไป
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
