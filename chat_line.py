from flask import Flask, request, jsonify
from flask_cors import CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import requests as requests_lib
import os
import openai
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# โหลดตัวแปรจากไฟล์ .env (ถ้ามี)
load_dotenv()

# ตรวจสอบว่าไฟล์ .env มีอยู่ในไดเรกทอรีปัจจุบันหรือไม่
env_path = os.path.join(os.getcwd(), '.env')
if not os.path.exists(env_path):
    raise FileNotFoundError(f".env file not found at: {env_path}")

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

# ตรวจสอบค่าที่ต้องใช้
missing_vars = [var for var in ["OPENAI_API_KEY", "LINE_ACCESS_TOKEN", "LINE_CHANNEL_SECRET", "ADMIN_USER_ID", "GOOGLE_SHEETS_CREDENTIALS"] if not locals()[var]]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# ตรวจสอบว่าไฟล์ JSON Credentials มีอยู่จริง
if not os.path.isfile(GOOGLE_SHEETS_CREDENTIALS):
    raise FileNotFoundError(f"Google Sheets credentials file not found: {GOOGLE_SHEETS_CREDENTIALS}")

# กำหนดค่า LineBotApi และ WebhookHandler
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# สร้างแอปพลิเคชัน Flask
app = Flask(__name__)
CORS(app)

# ตั้งค่า Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS, scope)
gc = gspread.authorize(credentials)

# เชื่อมต่อ Google Sheets
SHEET_1_ID = "1C7gh_EuNcSnYLDXB1Z681fLCf9f9kX6a0YN6otoElkg"
SHEET_2_ID = "1m1Pf7lxMNd4_WpAYvi3o0lBQcnmE-TgEtSpyqFAriJY"

spreadsheet_1 = gc.open_by_key(SHEET_1_ID)
spreadsheet_2 = gc.open_by_key(SHEET_2_ID)

worksheet_title = 'การตอบแบบฟอร์ม 1'

# ตรวจสอบว่า worksheet มีอยู่หรือไม่
try:
    worksheet_1 = next(ws for ws in spreadsheet_1.worksheets() if ws.title == worksheet_title)
except StopIteration:
    raise ValueError(f"Worksheet '{worksheet_title}' not found in Spreadsheet 1")

try:
    worksheet_2 = next(ws for ws in spreadsheet_2.worksheets() if ws.title == worksheet_title)
except StopIteration:
    raise ValueError(f"Worksheet '{worksheet_title}' not found in Spreadsheet 2")

# Google Forms
GOOGLE_FORM_1 = "https://forms.gle/va6VXDSw9fTayVDD6"
GOOGLE_FORM_2 = "https://forms.gle/irMiKifUYYKYywku5"

# ลิงก์วิดีโอที่เหมาะสมตามระดับคะแนน
video_links = {
    "low": "https://youtu.be/zr3quEuGSAE?si=U_jj_2lrITdbuef4",
    "medium": "https://youtu.be/TYSrIpdd2n4?si=stRQ-szINeeo6rdj",
    "high": "https://youtu.be/wVCtz5nwB0I?si=2dxTcWtcJOHbkq2H"
}

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
        response = requests_lib.post(LINE_API, headers=headers, json=data)
        response.raise_for_status()
    except requests_lib.exceptions.RequestException as e:
        app.logger.error(f"Error sending reply to LINE API: {e}")

# ฟังก์ชัน OpenAI
def get_openai_response(user_id, user_message):
    history = []
    history.append({"role": "user", "content": user_message})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You are a helpful assistant, YOU MUST RESPOND IN THAI"}] + history,
            max_tokens=200,
            temperature=0.7
        )
        bot_reply = response["choices"][0]["message"]["content"]
        return bot_reply
    except Exception as e:
        app.logger.error(f"Error: {e}")
        return "เกิดข้อผิดพลาด กรุณาลองใหม่"

# Webhook สำหรับ LINE Bot
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            if 'events' in req:
                for event in req['events']:
                    event_mode = event.get('mode')
                    reply_token = event.get('replyToken')
                    user_message = event.get('message', {}).get('text')
                    user_id = event.get('source', {}).get('userId')

                    if event_mode == "standby" or not reply_token or not user_message:
                        continue

                    if user_message.lower() in ["แบบสอบถาม", "แบบทดสอบ", "แบบประเมิน"]:
                        response_message = f"กรุณากรอกแบบสอบถามที่นี่:\n1. {GOOGLE_FORM_1}\n2. {GOOGLE_FORM_2}"
                    else:
                        response_message = get_openai_response(user_id, user_message)

                    ReplyMessage(reply_token, response_message)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

# ✅ แก้ไขให้ `if __name__ == "__main__":` อยู่ท้ายสุดของไฟล์หลัก
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
