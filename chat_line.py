from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
import os
import json
import requests
import openai

# ตั้งค่าตัวแปร Environment
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, GOOGLE_SCRIPT_URL, OPENAI_API_KEY]):
    raise ValueError("Missing API keys. Please set all required environment variables.")

# ตั้งค่า API Keys
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# ตัวแปรเก็บประวัติการสนทนา
conversation_history = {}

# ✅ ฟังก์ชันส่งข้อความไปยัง Google Apps Script เพื่อดึงข้อมูลผู้ใช้
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

# ✅ ฟังก์ชันส่ง Flex Message สำหรับแบบประเมิน
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
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#5AACFF",
                        "action": {
                            "type": "uri",
                            "label": "แบบประเมินโรคซึมเศร้า",
                            "uri": "https://forms.gle/ZmUfLVDKkjBXAVbx8"
                        }
                    },
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#FF6B6B",
                        "action": {
                            "type": "uri",
                            "label": "แบบประเมินการฆ่าตัวตาย",
                            "uri": "https://forms.gle/jxurYZrY4dGgPUKJA"
                        }
                    }
                ]
            }
        }
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {
        "replyToken": reply_token,
        "messages": [flex_message]
    }
    requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)

# คำถามสำหรับ "พูดคุย"
conversation_questions = [
    ("วันนี้เป็นยังไงบ้าง?", ["โอเคอยู่ มีพลังใช้ได้", "เหนื่อยนิดหน่อย อยากพัก"]),
    ("ถ้าตอนนี้มีใครสักคนบอกอะไรให้คุณรู้สึกดีขึ้น คุณอยากได้ยินคำไหนมากกว่า?", ["ไม่เป็นไรนะ คุณเก่งมากแล้ว", "พักก่อนก็ได้ เดี๋ยวค่อยไปต่อ"]),
    ("เวลารู้สึกเครียด ๆ คุณอยากให้ตัวเองลองทำอะไร?", ["หลับตาแล้วหายใจลึก ๆ สัก 5 ครั้ง", "ฟังเพลงเงียบ ๆ ให้ใจได้พัก"]),
    ("ถ้าต้องเปรียบเทียบความรู้สึกตอนนี้เป็นสีหนึ่งสี คิดว่ามันเป็นสีอะไร?", ["ฟ้า สงบขึ้นมาหน่อย สบาย ๆ", "เทา เหนื่อย ๆ ไม่แน่ใจว่ารู้สึกยังไง"]),
    ("ถ้าคุณต้องเขียนจดหมายสั้น ๆ ให้ตัวเองในวันนี้ คุณจะเริ่มต้นด้วยคำว่าอะไร?", ["ขอบคุณที่ยังพยายามอยู่ตรงนี้", "ขอให้พรุ่งนี้ใจดีกับเราหน่อยนะ"]),
    ("บางครั้งความเครียดก็มาโดยไม่บอกกล่าว ถ้าต้องเลือกสักอย่าง คุณอยากลอง…", ["หยุดคิดทุกอย่างสักแป๊บ แล้วปล่อยให้ตัวเองพัก", "หาอะไรเล็ก ๆ ที่ทำให้ตัวเองมีความสุข"])
]

def handle_conversation(user_id, reply_token, user_message):
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    conversation_history[user_id].append(user_message)
    next_question_index = len(conversation_history[user_id])
    
    if next_question_index < len(conversation_questions):
        question, options = conversation_questions[next_question_index]
        flex_message = {
            "type": "flex",
            "altText": question,
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": question, "weight": "bold", "size": "lg"}
                    ]
                },
                "footer": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {"type": "button", "action": {"type": "message", "label": option, "text": option}} 
                        for option in options
                    ]
                }
            }
        }
        ReplyMessage(reply_token, flex_message)
    else:
        ReplyMessage(reply_token, "ขอบคุณที่พูดคุยกับเรานะ 💙")
        conversation_history.pop(user_id, None)

# ✅ ฟังก์ชันส่งข้อความกลับไปยัง LINE
def ReplyMessage(reply_token, message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": message}] if isinstance(message, str) else [message]
    }
    requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)

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
                elif user_message == "ดูข้อมูลของฉัน":
                    user_data = FetchUserData(user_id)
                    ReplyMessage(reply_token, json.dumps(user_data, indent=2, ensure_ascii=False))
                elif user_id in conversation_history:
                    handle_conversation(user_id, reply_token, user_message)
                else:
                    ReplyMessage(reply_token, "ขออภัย ฉันไม่เข้าใจคำสั่งนี้")
            return 'OK'
        except Exception as e:
            app.logger.error(f"Error in webhook handler: {e}")
            return 'ERROR'
    return 'Hello World'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
