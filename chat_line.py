from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import requests as requests_lib
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
ADMIN_USER_ID = os.getenv("bplpoon")  # LINE User ID ของผู้จัดการ
GOOGLE_SHEETS_CREDENTIALS = os.getenv("credentials/meta-vista-446710-b6-d2f76e23ec67.json.")  # ใส่ Path ไฟล์ JSON Credentials

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

# ฟังก์ชันดึงคะแนนจาก Google Sheets (รองรับ 2 อัน)
def get_user_score(user_id):
    try:
        for sheet in [SHEET_1, SHEET_2]:
            records = sheet.get_all_records()
            for row in records:
                if row["user_id"] == user_id:
                    return int(row["score"])
    except Exception as e:
        app.logger.error(f"Error fetching score from Google Sheets: {e}")
    return None

# ฟังก์ชันเลือกวิดีโอที่เหมาะสม
def get_relaxing_video(score):
    if score <= 9:
        return video_links["low"]
    elif score <= 19:
        return video_links["medium"]
    else:
        return video_links["high"]

# ฟังก์ชันส่งข้อความตอบกลับ
def ReplyMessage(reply_token, text_message):
    try:
        line_bot_api.reply_message(reply_token, TextSendMessage(text=text_message))
    except Exception as e:
        app.logger.error(f"Error sending reply to LINE API: {e}")
        return jsonify({"error": "Failed to send reply message"}), 500
    return 200

# ฟังก์ชันแจ้งเตือนผู้จัดการเมื่อพบความเสี่ยงสูง
def send_risk_alert(user_name, risk_level):
    message = f"แจ้งเตือน: ผู้ใช้งาน {user_name} มีความเสี่ยงระดับ {risk_level} กรุณาตรวจสอบข้อมูลในระบบ!"
    line_bot_api.push_message(ADMIN_USER_ID, TextSendMessage(text=message))

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

                        # ตรวจจับคะแนนจาก Google Sheets
                        score = get_user_score(user_id)
                        if score is not None:
                            video_url = get_relaxing_video(score)
                            ReplyMessage(reply_token, f"นี่คือวิดีโอที่เหมาะกับคุณ: {video_url}")
                        elif "แบบสอบถาม 1" in user_message:
                            ReplyMessage(reply_token, f"กรุณากรอกแบบสอบถามที่นี่: {GOOGLE_FORM_1}")
                        elif "แบบสอบถาม 2" in user_message:
                            ReplyMessage(reply_token, f"กรุณากรอกแบบสอบถามที่นี่: {GOOGLE_FORM_2}")
                        else:
                            response_message = get_openai_response(user_id, user_message)
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
