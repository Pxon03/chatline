from flask import Flask, request, jsonify
from flask_cors import CORS
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

# ตั้งค่าลิงก์ Google Forms
GOOGLE_FORM_1 = "https://forms.gle/va6VXDSw9fTayVDD6"  # แบบประเมินโรคซึมเศร้า (9Q)
GOOGLE_FORM_2 = "https://forms.gle/irMiKifUYYKYywku5"  # แบบประเมินการฆ่าตัวตาย (8Q)

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

# Google Sheet ID
SHEET_1_ID = "1C7gh_EuNcSnYLDXB1Z681fLCf9f9kX6a0YN6otoElkg"  # ซึมเศร้า (9Q)
SHEET_2_ID = "1m1Pf7lxMNd4_WpAYvi3o0lBQcnmE-TgEtSpyqFAriJY"  # การฆ่าตัวตาย (8Q)

# เปิด Google Sheets
spreadsheet_1 = gc.open_by_key(SHEET_1_ID)
spreadsheet_2 = gc.open_by_key(SHEET_2_ID)

sheet_1 = spreadsheet_1.worksheet("แบบประเมินโรคซึมเศร้า (9Q) (การตอบกลับ)")
sheet_2 = spreadsheet_2.worksheet("แบบประเมินการฆ่าตัวตาย (8Q) (การตอบกลับ)")

# ตั้งค่า LINE API
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")

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
                        # บันทึกข้อความของผู้ใช้ลง Google Sheets
                        log_to_google_sheets(user_id, user_message)

                        # ตรวจสอบว่าผู้ใช้ต้องการทำแบบสอบถามหรือไม่
                        if "ทำแบบทดสอบ" in user_message or "แบบสอบถาม" in user_message:
                            form_message = f"📝 คุณสามารถทำแบบประเมินได้ที่นี่:\n- แบบประเมินโรคซึมเศร้า (9Q): {GOOGLE_FORM_1}\n- แบบประเมินความเสี่ยงฆ่าตัวตาย (8Q): {GOOGLE_FORM_2}"
                            ReplyMessage(reply_token, form_message)
                        else:
                            response_message = generate_ai_response(user_message)
                            ReplyMessage(reply_token, response_message)

                            # ดึงคะแนนจาก Google Sheets และแจ้งผลให้ผู้ใช้
                            result_message = get_user_score(user_id)
                            if result_message:
                                ReplyMessage(reply_token, result_message)

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
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
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

# ฟังก์ชันดึงคะแนนจาก Google Sheets และส่งผลลัพธ์กลับไปให้ผู้ใช้
def get_user_score(user_id):
    try:
        records_1 = sheet_1.get_all_records()
        records_2 = sheet_2.get_all_records()

        score_1, risk_1, score_2, risk_2 = None, None, None, None

        for row in records_1:
            if row['ชื่อ'] == user_id:
                score_1 = row['คะแนนซึมเศร้า']
                risk_1 = row['ระดับความเสี่ยงซึมเศร้า']

        for row in records_2:
            if row['ชื่อ'] == user_id:
                score_2 = row['คะแนนฆ่าตัวตาย']
                risk_2 = row['ระดับความเสี่ยงฆ่าตัวตาย']

        if score_1 is not None or score_2 is not None:
            message = "📊 ผลการประเมินของคุณ:\n"
            if score_1 is not None:
                message += f"- ซึมเศร้า (9Q): {score_1} คะแนน (ระดับ: {risk_1})\n"
            if score_2 is not None:
                message += f"- ความเสี่ยงฆ่าตัวตาย (8Q): {score_2} คะแนน (ระดับ: {risk_2})\n"
            
            message += "🎥 วิดีโอแนะนำ: " + get_video_recommendation(risk_1, risk_2)
            return message
    except Exception as e:
        print(f"Error fetching user score: {e}")
    return None

# ฟังก์ชันเลือกวิดีโอตามระดับความเสี่ยง
def get_video_recommendation(risk_1, risk_2):
    return "https://youtu.be/example"

# ฟังก์ชันบันทึกข้อความของผู้ใช้ลง Google Sheets
def log_to_google_sheets(user_id, user_message):
    try:
        sheet_1.append_row([user_id, user_message])
        sheet_2.append_row([user_id, user_message])
        print("✅ Data logged successfully to both sheets")
    except Exception as e:
        print(f"❌ Error logging data: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
