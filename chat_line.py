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
from google.oauth2.service_account import Credentials

# Decode Base64 credentials
credentials_base64 = os.getenv("GOOGLE_SHEETS_CREDENTIALS_BASE64")
if not credentials_base64:
    raise ValueError("❌ GOOGLE_SHEETS_CREDENTIALS_BASE64 is not set!")

# ถอดรหัส Base64 เป็น JSON
try:
    credentials_json = base64.b64decode(credentials_base64).decode("utf-8")
    creds_dict = json.loads(credentials_json)
except Exception as e:
    raise ValueError(f"❌ Google Sheets Credentials Error: {str(e)}")

# ใช้ Credentials จาก JSON (ไม่ต้องเปิดไฟล์)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])

# เชื่อมต่อ Google Sheets
gc = gspread.authorize(creds)

# ตรวจสอบ Google Sheets
SHEET_1_ID = "1C7gh_EuNcSnYLDXB1Z681fLCf9f9kX6a0YN6otoElkg"
spreadsheet_1 = gc.open_by_key(SHEET_1_ID)

# พิมพ์ชื่อของทุก worksheet ใน Google Sheets
worksheets_1 = spreadsheet_1.worksheets()
print("Worksheets in Spreadsheet 1:")
for worksheet in worksheets_1:
    print(worksheet.title)

# สร้างแอป Flask
app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def home():
    return "Flask App is running!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
