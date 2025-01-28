from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import requests as requests_lib
import os
import openai

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
ADMIN_USER_ID = os.getenv("LINE_ADMIN_USER_ID")  # LINE User ID ของผู้จัดการ

# ตรวจสอบว่ามีการตั้งค่า ENV Variable หรือไม่
if not OPENAI_API_KEY or not LINE_ACCESS_TOKEN or not LINE_CHANNEL_SECRET or not ADMIN_USER_ID:
    raise ValueError("Missing API keys. Please set OPENAI_API_KEY, LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, and LINE_ADMIN_USER_ID as environment variables.")

# ตั้งค่า OpenAI และ LINE Bot API
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# เก็บประวัติการสนทนา
conversation_history = {}

# ลิงก์ Google Form
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSd9pRGR6-s7B1PaIr-69y_dB9UZlzuSg_-fIpmQBi5_Q22BMA/viewform?usp=header"  # แทนที่ด้วยลิงก์ Google Form ของคุณ

# ฟังก์ชันส่งข้อความตอบกลับ
def ReplyMessage(reply_token, text_message):
    LINE_API = 'https://api.line.me/v2/bot/message/reply'
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text_message}]
    }

    try:
        response = requests_lib.post(LINE_API, headers=headers, data=json.dumps(data))
        response.raise_for_status()  # ถ้าเกิดข้อผิดพลาดจาก LINE API จะทำให้เกิด exception
    except requests_lib.exceptions.RequestException as e:
        app.logger.error(f"Error sending reply to LINE API: {e}")
        return jsonify({"error": "Failed to send reply message"}), 500  # ตอบกลับ 500 ถ้ามีข้อผิดพลาด

    return response.status_code

# ฟังก์ชัน OpenAI สำหรับประมวลผลข้อความ
def get_openai_response(user_id, user_message):
    global conversation_history
    
    if user_id in conversation_history:
        history = conversation_history[user_id]
    else:
        history = []

    history.append({"role": "user", "content": user_message})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant, YOU MUST RESPOND IN THAI"}
            ] + history,
            max_tokens=200,
        )

        bot_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": bot_reply})
        conversation_history[user_id] = history

        # ตรวจสอบคำตอบที่บ่งบอกความเสี่ยง และแจ้งเตือนผู้จัดการ
        if "เสี่ยงสูง" in bot_reply:  # ปรับตามเงื่อนไขที่คุณต้องการ
            send_risk_alert(user_id, "รุนแรง")

        if len(history) > 10:
            history.pop(0)

        return bot_reply
    except Exception as e:
        app.logger.error(f"Error: {e}")
        return "เกิดข้อผิดพลาด กรุณาลองใหม่"

# ฟังก์ชันส่งลิงก์ Google Form
def send_survey_link(reply_token):
    message = f"กรุณากรอกแบบสอบถามที่นี่: {GOOGLE_FORM_URL}"
    ReplyMessage(reply_token, message)

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

                        # หากข้อความคือ "แบบสอบถาม" ให้ส่งลิงก์ Google Form
                        if "แบบสอบถาม" in user_message:
                            send_survey_link(reply_token)
                        else:
                            # เรียกฟังก์ชัน AI สำหรับตอบคำถามทั่วไป
                            user_id = event['source']['userId']
                            response_message = get_openai_response(user_id, user_message)
                            ReplyMessage(reply_token, response_message)

            return jsonify({"status": "success"}), 200  # ตอบกลับ 200 OK
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # รองรับ PORT จาก Render
    app.run(debug=True, host="0.0.0.0", port=port)
