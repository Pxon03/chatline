from flask import Flask, request, jsonify
from flask_cors import CORS
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import requests as requests_lib
import os
import openai
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# โหลดค่าตัวแปรจาก .env
load_dotenv()

# Decode Base64 credentials
credentials_base64 = os.getenv("GOOGLE_SHEETS_CREDENTIALS_BASE64")
if not credentials_base64:
    raise ValueError("❌ GOOGLE_SHEETS_CREDENTIALS_BASE64 is not set!")

try:
    credentials_json = base64.b64decode(credentials_base64).decode("utf-8")
    creds_dict = json.loads(credentials_json)
except Exception as e:
    raise ValueError(f"❌ Google Sheets Credentials Error: {str(e)}")

# ใช้ Credentials จาก JSON
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])

# เชื่อมต่อ Google Sheets
gc = gspread.authorize(creds)

# ตั้งค่า Google Sheets
SHEET_1_ID = "1C7gh_EuNcSnYLDXB1Z681fLCf9f9kX6a0YN6otoElkg"
spreadsheet_1 = gc.open_by_key(SHEET_1_ID)

# สร้างแอป Flask
app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def home():
    return "Flask App is running!", 200

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            print(f"Received request: {json.dumps(req, ensure_ascii=False)}")
            
            if 'events' in req:
                for event in req['events']:
                    reply_token = event.get('replyToken')
                    message = event.get('message', {})
                    user_message = message.get('text')
                    user_id = event.get('source', {}).get('userId')
                    
                    if reply_token and user_message:
                        response_message = generate_ai_response(user_message)
                        ReplyMessage(reply_token, response_message)
                        log_to_google_sheet(user_id, user_message)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            print(f"Error processing request: {e}")
            return jsonify({"error": str(e)}), 500
    return "GET", 200

# ฟังก์ชันส่งข้อความกลับไปที่ LINE
def ReplyMessage(reply_token, text_message):
    LINE_API = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {os.getenv("LINE_ACCESS_TOKEN")}'
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text_message}]
    }
    try:
        requests_lib.post(LINE_API, headers=headers, json=data)
    except requests_lib.exceptions.RequestException as e:
        print(f"Error sending message: {e}")

# ฟังก์ชันให้บอทใช้ OpenAI GPT ในการตอบข้อความ
def generate_ai_response(user_message):
    openai.api_key = os.getenv("OPENAI_API_KEY")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "คุณคือแชทบอทที่เป็นมิตรและช่วยเหลือผู้ใช้"},
            {"role": "user", "content": user_message}
        ]
    )
    return response["choices"][0]["message"]["content"]

# ฟังก์ชันบันทึกข้อมูลไปยัง Google Sheets
def log_to_google_sheet(user_id, user_message):
    google_script_url = 'https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec'
    data = {'user_id': user_id, 'message': user_message}
    try:
        requests_lib.post(google_script_url, data=data)
    except Exception as e:
        print(f"Error logging data: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
