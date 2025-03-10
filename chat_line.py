from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
import os
import json
import requests

# ตั้งค่าตัวแปร Environment
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")

if not all([LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, GOOGLE_SCRIPT_URL]):
    raise ValueError("Missing API keys. Please set all required environment variables.")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
app = Flask(__name__)

# ตัวแปรเก็บประวัติการสนทนา
conversation_history = {}

# สร้างข้อความตอบกลับสำหรับข้อมูลของผู้ใช้
def format_user_info(name, user_info_list):
    if not user_info_list:
        return ""  # ส่งข้อความว่าง เพื่อให้ ReplyMessage() ไม่ส่งอะไรกลับไป

    message = f"👤 ข้อมูลของ {name}\n"
    for info in user_info_list:
        if info.get("sheet") == "ซึมเศร้า":
            message += (
                "\n[แบบประเมินโรคซึมเศร้า]\n"
                f"เพศ: {info.get('เพศ', 'ไม่ระบุ')}\n"
                f"อายุ: {info.get('อายุ', 'ไม่ระบุ')}\n"
                f"สถานะ: {info.get('สถานะ', 'ไม่ระบุ')}\n"
                f"คะแนนซึมเศร้า: {info.get('คะแนนซึมเศร้า', 'ไม่ระบุ')}\n"
                f"ระดับความเสี่ยงซึมเศร้า: {info.get('ระดับความเสี่ยงซึมเศร้า', 'ไม่ระบุ')}\n"
            )
        elif info.get("sheet") == "ฆ่าตัวตาย":
            message += (
                "\n[แบบประเมินการฆ่าตัวตาย]\n"
                f"เพศ: {info.get('เพศ', 'ไม่ระบุ')}\n"
                f"อายุ: {info.get('อายุ', 'ไม่ระบุ')}\n"
                f"สถานะ: {info.get('สถานะ', 'ไม่ระบุ')}\n"
                f"คะแนนฆ่าตัวตาย: {info.get('คะแนนฆ่าตัวตาย', 'ไม่ระบุ')}\n"
                f"ระดับความเสี่ยงฆ่าตัวตาย: {info.get('ระดับความเสี่ยงฆ่าตัวตาย', 'ไม่ระบุ')}\n"
            )

    return message

# ฟังก์ชันดึงข้อมูลผู้ใช้จาก Google Apps Script โดยใช้ชื่อผู้ใช้
def FetchUserData(name):
    response = requests.get(f"{GOOGLE_SCRIPT_URL}?userName={name}")  # ส่งชื่อผู้ใช้แทน user_id
    if response.status_code == 200:
        user_info_list = response.json()
        return format_user_info(name, user_info_list)  # ใช้ฟังก์ชัน format_user_info ในการจัดรูปแบบข้อมูล
    return "ไม่สามารถดึงข้อมูลได้"

# ✅ คำถามสำหรับ "พูดคุย"
conversation_questions = [
    ("วันนี้เป็นยังไงบ้าง?", ["โอเคอยู่ มีพลังใช้ได้", "เหนื่อยนิดหน่อย อยากพัก"]),
    ("ถ้าตอนนี้มีใครสักคนบอกอะไรให้คุณรู้สึกดีขึ้น คุณอยากได้ยินคำว่าอะไร?", ["ไม่เป็นไรนะ คุณเก่งมากแล้ว", "พักก่อนก็ได้ เดี๋ยวค่อยไปต่อ"]),
    ("เวลารู้สึกเครียด ๆ คุณอยากให้ตัวเองลองทำอะไร?", ["หลับตาแล้วหายใจลึก ๆ สัก 5 ครั้ง", "ฟังเพลงเงียบ ๆ ให้ใจได้พัก"]),
    ("ถ้าต้องเปรียบเทียบความรู้สึกตอนนี้เป็นสีหนึ่งสี คิดว่ามันเป็นสีอะไร?", ["ฟ้า สงบขึ้นมาหน่อย สบาย ๆ", "เทา เหนื่อย ๆ ไม่แน่ใจว่ารู้สึกยังไง"]),
    ("ถ้าคุณอยากอะไรสั้น ๆ ให้ตัวเองในวันนี้ คุณจะบอกว่าอะไร?", ["ขอบคุณที่ยังพยายามอยู่ตรงนี้", "ขอให้พรุ่งนี้ใจดีกับเราหน่อยนะ"]),
    ("บางครั้งความเครียดก็มาโดยไม่บอกกล่าว คุณมีวิธีรับมืออย่างไร?", ["หยุดคิดทุกอย่างสักแป๊บ แล้วปล่อยให้ตัวเองพัก", "หาอะไรเล็ก ๆ ที่ทำให้ตัวเองมีความสุข"]),
]

# ✅ ฟังก์ชันพูดคุย
def handle_conversation(user_id, reply_token, user_message):
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append(user_message)
    next_question_index = len(conversation_history[user_id]) - 1

    if next_question_index < len(conversation_questions):
        question, options = conversation_questions[next_question_index]

        ReplyMessage(reply_token, question)
        flex_message = {
            "type": "flex",
            "altText": "❓ มีคำถามใหม่ กรุณาเปิดดูใน LINE",
            "contents": {
                "type": "bubble",
                "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": question, "weight": "bold", "size": "lg"}]},
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [{"type": "button", "action": {"type": "message", "label": option, "text": option}} for option in options]
                }
            }
        }
        ReplyMessage(reply_token, flex_message)
    else:
        ReplyMessage(reply_token, "ขอบคุณที่พูดคุยกับเรานะ 💙")
        conversation_history.pop(user_id, None)

# ✅ ฟังก์ชันส่งแบบประเมิน (Flex Message)
def ReplyAssessmentMessage(reply_token):
    flex_message = {
        "type": "flex",
        "altText": "เลือกแบบประเมินที่ต้องการ 📋",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "เลือกแบบประเมินที่ต้องการ 📋", "weight": "bold", "size": "lg"},
                    {"type": "text", "text": "กรุณาเลือกแบบประเมินที่ต้องการ", "size": "md", "margin": "md"},
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#5AACFF", "action": {"type": "uri", "label": "แบบประเมินโรคซึมเศร้า", "uri": "https://forms.gle/ZmUfLVDKkjBXAVbx8"}},
                    {"type": "button", "style": "primary", "color": "#FF6B6B", "action": {"type": "uri", "label": "แบบประเมินการฆ่าตัวตาย", "uri": "https://forms.gle/jxurYZrY4dGgPUKJA"}}
                ]
            }
        }
    }
    ReplyMessage(reply_token, flex_message)

# ✅ ฟังก์ชันดึงข้อมูลผู้ใช้จาก Google Apps Script
def FetchUserData(user_id):
    response = requests.get(f"{GOOGLE_SCRIPT_URL}?userId={user_id}")
    if response.status_code == 200:
        return response.json()
    return {"error": "ไม่สามารถดึงข้อมูลได้"}

# ✅ ฟังก์ชันส่งข้อความกลับไปยัง LINE
def ReplyMessage(reply_token, message):
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}
    data = {"replyToken": reply_token, "messages": [{"type": "text", "text": message}] if isinstance(message, str) else [message]}
    requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)

# ✅ Webhook ของ Flask
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            for event in req.get('events', []):
                reply_token = event.get('replyToken')
                user_id = event.get('source', {}).get('userId')
                user_message = event.get('message', {}).get('text')

                if not reply_token or not user_message:
                    continue

                if user_message == "พูดคุย":
                    conversation_history[user_id] = []
                    handle_conversation(user_id, reply_token, user_message)
                elif user_message == "แบบประเมิน":
                    ReplyAssessmentMessage(reply_token)
                elif user_message.startswith("ดูข้อมูลของ"):  # หากข้อความเริ่มต้นด้วย 'ดูข้อมูลของ'
                    name = user_message.replace("ดูข้อมูลของ", "").strip()  # ดึงชื่อจากข้อความ
                    if name:
                        user_data = FetchUserData(name)
                        ReplyMessage(reply_token, user_data)  # ส่งข้อความที่จัดรูปแบบแล้วกลับไป
                    else:
                        ReplyMessage(reply_token, "กรุณาระบุชื่อที่ถูกต้อง")
                elif user_id in conversation_history:
                    handle_conversation(user_id, reply_token, user_message)
                else:
                    ReplyMessage(reply_token, "ขออภัย ฉันไม่เข้าใจคำสั่งนี้")

            return 'OK'
        except Exception as e:
            app.logger.error(f"Error in webhook handler: {e}")
            return 'ERROR'
    return 'Hello World'
