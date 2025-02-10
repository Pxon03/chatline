from flask import Flask, request, jsonify
from flask_cors import CORS  # นำเข้า CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import requests as requests_lib
import os
import openai
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
#from dotenv import load_dotenv  # นำเข้า dotenv เพื่อโหลดไฟล์ .env

# โหลดตัวแปรจากไฟล์ .env (ถ้ามี)
#load_dotenv()

# ตรวจสอบว่าไฟล์ .env มีอยู่ในไดเรกทอรีปัจจุบันหรือไม่
#env_path = os.path.join(os.getcwd(), '.env')
#print(f"Looking for .env file at: {env_path}")
#if not os.path.exists(env_path):
    #raise FileNotFoundError(f".env file not found at: {env_path}")

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")  # LINE User ID ของผู้จัดการ
GOOGLE_SHEETS_CREDENTIALS = os.getenv("GOOGLE_SHEETS_CREDENTIALS")  # ใส่ Path ไฟล์ JSON Credentials
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

# พิมพ์ค่าตัวแปรเพื่อตรวจสอบ
print(f"OPENAI_API_KEY: {OPENAI_API_KEY}")
print(f"LINE_ACCESS_TOKEN: {LINE_ACCESS_TOKEN}")
print(f"LINE_CHANNEL_SECRET: {LINE_CHANNEL_SECRET}")
print(f"ADMIN_USER_ID: {ADMIN_USER_ID}")
print(f"GOOGLE_SHEETS_CREDENTIALS: {GOOGLE_SHEETS_CREDENTIALS}")
print(f"DATABASE_URL: {DATABASE_URL}")
print(f"SECRET_KEY: {SECRET_KEY}")

# ตรวจสอบว่าอ่านค่าได้จริง
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is not set in the environment variables!")

if not SECRET_KEY:
    raise ValueError("❌ SECRET_KEY is not set in the environment variables!")

# ตรวจสอบค่าที่ต้องใช้
missing_vars = []
if not OPENAI_API_KEY:
    missing_vars.append("OPENAI_API_KEY")
if not LINE_ACCESS_TOKEN:
    missing_vars.append("LINE_ACCESS_TOKEN")
if not LINE_CHANNEL_SECRET:
    missing_vars.append("LINE_CHANNEL_SECRET")
if not ADMIN_USER_ID:
    missing_vars.append("ADMIN_USER_ID")
if not GOOGLE_SHEETS_CREDENTIALS:
    missing_vars.append("GOOGLE_SHEETS_CREDENTIALS")

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# ตรวจสอบว่าไฟล์ JSON Credentials มีอยู่จริง
print(f"Google Sheets credentials file path: {GOOGLE_SHEETS_CREDENTIALS}")
if not os.path.isfile(GOOGLE_SHEETS_CREDENTIALS):
    raise FileNotFoundError(f"Google Sheets credentials file not found: {GOOGLE_SHEETS_CREDENTIALS}")

# กำหนดค่า LineBotApi และ WebhookHandler
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# สร้างแอปพลิเคชัน Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY  # ตั้งค่า Secret Key ในแอปพลิเคชัน Flask
CORS(app)  # กำหนดค่า CORS

# ตั้งค่า Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS, scope)
gc = gspread.authorize(credentials)

# เชื่อมต่อ Google Sheets (มี 2 อัน)
SHEET_1_ID = "1C7gh_EuNcSnYLDXB1Z681fLCf9f9kX6a0YN6otoElkg"  # ใส่ Google Sheet ID อันแรก
SHEET_2_ID = "1m1Pf7lxMNd4_WpAYvi3o0lBQcnmE-TgEtSpyqFAriJY"  # ใส่ Google Sheet ID แบบประเมินการฆ่าตัวตาย (8Q)

# เปิด Google Sheets โดยใช้ key
spreadsheet_1 = gc.open_by_key(SHEET_1_ID)
spreadsheet_2 = gc.open_by_key(SHEET_2_ID)

# พิมพ์ชื่อของทุก worksheet ใน Google Sheets
worksheets_1 = spreadsheet_1.worksheets()
worksheets_2 = spreadsheet_2.worksheets()

print("Worksheets in Spreadsheet 1:")
for worksheet in worksheets_1:
    print(worksheet.title)

print("Worksheets in Spreadsheet 2:")
for worksheet in worksheets_2:
    print(worksheet.title)

worksheet_title = 'การตอบแบบฟอร์ม 1'

# ตรวจสอบว่า worksheet ที่ต้องการมีอยู่หรือไม่
try:
    worksheet_1 = next(ws for ws in spreadsheet_1.worksheets() if ws.title == worksheet_title)
    print(f"Worksheet '{worksheet_title}' found in Spreadsheet 1")
except StopIteration:
    print(f"Worksheet '{worksheet_title}' not found in Spreadsheet 1")
    worksheet_1 = None

try:
    worksheet_2 = next(ws for ws in spreadsheet_2.worksheets() if ws.title == worksheet_title)
    print(f"Worksheet '{worksheet_title}' found in Spreadsheet 2")
except StopIteration:
    print(f"Worksheet '{worksheet_title}' not found in Spreadsheet 2")
    worksheet_2 = None

# อ่านข้อมูลจาก worksheet ถ้ามี
if worksheet_1:
    data_1 = worksheet_1.get_all_values()
    print("Data from Worksheet 1:")
    for row in data_1:
        print(row)
else:
    print("No data from Worksheet 1")

if worksheet_2:
    data_2 = worksheet_2.get_all_values()
    print("Data from Worksheet 2:")
    for row in data_2:
        print(row)
else:
    print("No data from Worksheet 2")

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

# ฟังก์ชัน OpenAI สำหรับประมวลผลข้อความ
def get_openai_response(user_id, user_message):
    global conversation_history
    history = conversation_history.get(user_id, [])
    history.append({"role": "user", "content": user_message})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
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
        app.logger.error(f"Error: {e}")
        return "เกิดข้อผิดพลาด กรุณาลองใหม่"

# ฟังก์ชันบันทึกข้อมูลการพูดคุยลง Google Sheets
def log_to_google_sheet(user_id, user_message):
    # Webhook URL ของ Google Apps Script
    google_script_url = 'https://script.google.com/macros/s/AKfycbzRW7Ca_vRHLk_oK0ZlTNtGYllRwQ67Y887UC9Kn9tiu0ffe5orohsDVr0Q-5HC-Z_e/exec'  # ใส่ URL ของ Apps Script ที่คุณใช้
    
    # ข้อมูลที่ต้องการส่งไป
    data = {
        'user_id': user_id,
        'message': user_message
    }

    try:
        response = requests_lib.post(google_script_url, data=data)
        if response.status_code == 200:
            print("Data logged successfully")
        else:
            print("Failed to log data")
    except Exception as e:
        print(f"Error logging data to Google Sheet: {e}")

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
                    if not reply_token:
                        app.logger.error("Missing 'replyToken' in event")
                        continue
                    
                    if not user_message:
                        app.logger.info("Skipping event with no text message")
                        continue
                    
                    # ตรวจสอบว่า LINE Bot ตอบหรือยัง
                    if user_message.lower() in ["แบบสอบถาม", "แบบทดสอบ", "แบบประเมิน"]:
                        response_message = "กรุณากรอกแบบสอบถามที่นี่\n1.แบบประเมินโรคซึมเศร้า (9Q)\nhttps://forms.gle/DcpjMHV5Fda9GwvN7\n\n2.แบบประเมินการฆ่าตัวตาย (8Q)\nhttps://forms.gle/aG7TChRr4R9FtTMTA"
                        ReplyMessage(reply_token, response_message)
                    else:
                        # หาก LINE Bot ยังไม่ได้ตอบ ก็ให้ GPT ตอบ
                        response_message = get_openai_response(user_id, user_message)
                        ReplyMessage(reply_token, response_message)
                    
                    # บันทึกข้อมูลการพูดคุยลง Google Sheets
                    log_to_google_sheet(user_id, user_message)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  
    app.run(debug=True, host="0.0.0.0", port=port)
