from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import os
import openai
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv  # นำเข้า dotenv เพื่อโหลดไฟล์ .env

# โหลดตัวแปรจากไฟล์ .env (ถ้ามี)
load_dotenv()

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
ADMIN_USER_ID = os.getenv("LINE_ADMIN_USER_ID")  # LINE User ID ของผู้จัดการ
GOOGLE_SHEETS_CREDENTIALS = os.getenv("path_to_your_credentials.json")  # ใส่ Path ไฟล์ JSON Credentials จาก Environment Variables

# ตรวจสอบค่าที่ต้องใช้
print(OPENAI_API_KEY, LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, ADMIN_USER_ID, GOOGLE_SHEETS_CREDENTIALS)  # ตรวจสอบค่าตัวแปร

if not all([OPENAI_API_KEY, LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, ADMIN_USER_ID, GOOGLE_SHEETS_CREDENTIALS]):
    raise ValueError("Missing required environment variables!")

# ตั้งค่า OpenAI และ LINE Bot API
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# ตั้งค่า Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# แก้ไขตรงนี้ให้ตรงกับ path ของไฟล์ JSON ที่ถูกต้อง
credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS, scope)
gc = gspread.authorize(credentials)

# เชื่อมต่อ Google Sheets (มี 2 อัน)
SHEET_1_ID = "1C7gh_EuNcSnYLDXB1Z681fLCf9f9kX6a0YN6otoElkg"  # ใส่ Google Sheet ID อันแรก
SHEET_2_ID = "1m1Pf7lxMNd4_WpAYvi3o0lBQcnmE-TgEtSpyqFAriJY"  # ใส่ Google Sheet ID แบบประเมินการฆ่าตัวตาย (8Q)

SHEET_1 = gc.open_by_key(SHEET_1_ID).worksheet("แบบประเมินโรคซึมเศร้าด้วย 9 คำถาม (9Q)")  # เปลี่ยนชื่อชีตถ้าจำเป็น
SHEET_2 = gc.open_by_key(SHEET_2_ID).worksheet("แบบประเมินการฆ่าตัวตาย (8Q)")

# Google Forms
GOOGLE_FORM_1 = "https://forms.gle/va6VXDSw9fTayVDD6"  # แบบประเมินโรคซึมเศร้าด้วย 9 คำถาม
GOOGLE_FORM_2 = "https://forms.gle/irMiKifUYYKYywku5"  # แบบประเมินการฆ่าตัวตาย (8Q)

# ลิงก์วิดีโอที่เหมาะสมตามระดับคะแนน
video_links = {
    "low": "https://youtu.be/zr3quEuGSAE?si=U_jj_2lrITdbuef4",  # ปกติ
    "medium": "https://youtu.be/TYSrIpdd2n4?si=stRQ-szINeeo6rdj",  # มีภาวะเครียด
    "high": "https://youtu.be/wVCtz5nwB0I?si=2dxTcWtcJOHbkq2H"  # ซึมเศร้ารุนแรง
}

# Webhook สำหรับ LINE Bot
@app.route('/webhook', methods=['POST', 'GET']) 
def webhook():
    # โค้ดสำหรับ webhook และฟังก์ชันอื่นๆ ...
    pass
