from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import os
import openai
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# โหลดตัวแปรจากไฟล์ .env (ถ้ามี)
load_dotenv()

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_ADMIN_USER_ID = os.getenv("LINE_ADMIN_USER_ID")
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

# ตรวจสอบค่าที่ต้องใช้
missing_vars = [var for var, value in {
    "OPENAI_API_KEY": OPENAI_API_KEY,
    "LINE_ACCESS_TOKEN": LINE_ACCESS_TOKEN,
    "LINE_CHANNEL_SECRET": LINE_CHANNEL_SECRET,
    "LINE_ADMIN_USER_ID": LINE_ADMIN_USER_ID,
    "GOOGLE_SHEETS_CREDENTIALS": GOOGLE_SHEETS_CREDENTIALS,
}.items() if not value]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# ตั้งค่า OpenAI และ LINE Bot API
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# ตั้งค่า Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    credentials_json = json.loads(GOOGLE_SHEETS_CREDENTIALS)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json, scope)
    gc = gspread.authorize(credentials)
except json.JSONDecodeError:
    raise ValueError("Invalid JSON format in GOOGLE_SHEETS_CREDENTIALS")
except Exception as e:
    raise ValueError(f"Error loading Google Sheets credentials: {e}")

# เชื่อมต่อ Google Sheets (มี 2 อัน)
SHEET_1_ID = "1C7gh_EuNcSnYLDXB1Z681fLCf9f9kX6a0YN6otoElkg"
SHEET_2_ID = "1m1Pf7lxMNd4_WpAYvi3o0lBQcnmE-TgEtSpyqFAriJY"

try:
    SHEET_1 = gc.open_by_key(SHEET_1_ID).worksheet("แบบประเมินโรคซึมเศร้าด้วย 9 คำถาม (9Q)")
    SHEET_2 = gc.open_by_key(SHEET_2_ID).worksheet("แบบประเมินการฆ่าตัวตาย (8Q)")
except Exception as e:
    raise ValueError(f"Error accessing Google Sheets: {e}")

# Webhook สำหรับ LINE Bot
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            if 'events' in req:
                for event in req['events']:
                    if event['type'] == 'message' and event['message']['type'] == 'text':
                        user_message = event['message']['text']
                        reply_token = event['replyToken']
                        user_id = event['source']['userId']
                        
                        response_message = f"คุณส่งข้อความว่า: {user_message}"
                        ReplyMessage(reply_token, response_message)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500

    elif request.method == "GET":
        return "GET", 200

def ReplyMessage(reply_token, text):
    line_bot_api.reply_message(reply_token, TextSendMessage(text=text))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  
    app.run(debug=True, host="0.0.0.0", port=port)
