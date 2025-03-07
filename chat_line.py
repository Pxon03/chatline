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

# ฟังก์ชันส่ง Flex Message สำหรับการพูดคุย
def ReplyChatMessage(reply_token, question, options):
    buttons = [
        {
            "type": "button",
            "style": "primary",
            "color": "#5AACFF",
            "action": {"type": "message", "label": option, "text": option}
        } for option in options
    ]
    flex_message = {
        "type": "flex",
        "altText": question,
        "contents": {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": question, "weight": "bold", "size": "xl", "align": "center"}
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": buttons
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

# ✅ ฟังก์ชันตอบกลับเมื่อพิมพ์ "พูดคุย"
def handle_chat(reply_token, step):
    if step == 1:
        question = "วันนี้เป็นยังไงบ้าง?"
        options = ["โอเคอยู่ มีพลังใช้ได้", "เหนื่อยนิดหน่อย อยากพัก"]
        ReplyChatMessage(reply_token, question, options)
    elif step == 2:
        question = "ถ้าตอนนี้มีใครสักคนบอกอะไรให้คุณรู้สึกดีขึ้น คุณอยากได้ยินคำไหนมากกว่า?"
        options = ["ไม่เป็นไรนะ คุณเก่งมากแล้ว", "พักก่อนก็ได้ เดี๋ยวค่อยไปต่อ"]
        ReplyChatMessage(reply_token, question, options)
    elif step == 3:
        question = "เวลารู้สึกเครียด ๆ คุณอยากให้ตัวเองลองทำอะไร?"
        options = ["หลับตาแล้วหายใจลึก ๆ สัก 5 ครั้ง", "ฟังเพลงเงียบ ๆ ให้ใจได้พัก"]
        ReplyChatMessage(reply_token, question, options)
    elif step == 4:
        question = "ถ้าต้องเปรียบเทียบความรู้สึกตอนนี้เป็นสีหนึ่งสี คิดว่ามันเป็นสีอะไร?"
        options = ["ฟ้า สงบขึ้นมาหน่อย สบาย ๆ", "เทา เหนื่อย ๆ ไม่แน่ใจว่ารู้สึกยังไง"]
        ReplyChatMessage(reply_token, question, options)
    elif step == 5:
        question = "ถ้าคุณต้องเขียนจดหมายสั้น ๆ ให้ตัวเองในวันนี้ คุณจะเริ่มต้นด้วยคำว่าอะไร?"
        options = ["ขอบคุณที่ยังพยายามอยู่ตรงนี้", "ขอให้พรุ่งนี้ใจดีกับเราหน่อยนะ"]
        ReplyChatMessage(reply_token, question, options)
    elif step == 6:
        question = "บางครั้งความเครียดก็มาโดยไม่บอกกล่าว ถ้าต้องเลือกสักอย่าง คุณอยากลอง…"
        options = ["หยุดคิดทุกอย่างสักแป๊บ แล้วปล่อยให้ตัวเองพัก", "หาอะไรเล็ก ๆ ที่ทำให้ตัวเองมีความสุข"]
        ReplyChatMessage(reply_token, question, options)

# ฟังก์ชันค้นหาข้อมูลของผู้ใช้จากชื่อ
def get_user_info(name):
    # ตัวอย่างการดึงข้อมูลจาก Google Sheets หรือ API อื่น ๆ
    # ฟังก์ชันนี้ต้องเปลี่ยนตามวิธีที่คุณใช้ดึงข้อมูล
    response = requests.get(f"{GOOGLE_SCRIPT_URL}?name={name}")
    if response.status_code == 200:
        return response.json()  # สมมติว่าได้ข้อมูลในรูปแบบ JSON
    return []

# สร้างข้อความตอบกลับ
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

# รับข้อมูลจาก LINE Webhook
@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            app.logger.debug(f"Received full request: {json.dumps(req, indent=2, ensure_ascii=False)}")

            if 'events' in req:
                for event in req['events']:
                    reply_token = event.get('replyToken')
                    user_message = event.get('message', {}).get('text')

                    if not reply_token or not user_message:
                        continue

                    if user_message == "แบบประเมิน":
                        ReplyAssessmentMessage(reply_token)
                    elif user_message == "พูดคุย":
                        handle_chat(reply_token, 1)  # เริ่มต้นที่คำถามแรก
                    else:
                        # ค้นหาข้อมูลผู้ใช้จากชื่อที่พิมพ์มา
                        user_info_list = get_user_info(user_message)
                        formatted_info = format_user_info(user_message, user_info_list)
                        if formatted_info:
                            line_bot_api.reply_message(reply_token, TextSendMessage(text=formatted_info))
                        else:
                            # หากไม่มีข้อมูลแสดงข้อความที่เหมาะสม
                            line_bot_api.reply_message(reply_token, TextSendMessage(text="ไม่พบข้อมูลของผู้ใช้ที่คุณค้นหา"))
                        
                        # การสนทนาอื่นๆ
                        if user_message in ["โอเคอยู่ มีพลังใช้ได้", "เหนื่อยนิดหน่อย อยากพัก"]:
                            handle_chat(reply_token, 2)  # ถามคำถามถัดไป
                        elif user_message in ["ไม่เป็นไรนะ คุณเก่งมากแล้ว", "พักก่อนก็ได้ เดี๋ยวค่อยไปต่อ"]:
                            handle_chat(reply_token, 3)
                        elif user_message in ["หลับตาแล้วหายใจลึก ๆ สัก 5 ครั้ง", "ฟังเพลงเงียบ ๆ ให้ใจได้พัก"]:
                            handle_chat(reply_token, 4)
                        elif user_message in ["ฟ้า สงบขึ้นมาหน่อย สบาย ๆ", "เทา เหนื่อย ๆ ไม่แน่ใจว่ารู้สึกยังไง"]:
                            handle_chat(reply_token, 5)
                        elif user_message in ["ขอบคุณที่ยังพยายามอยู่ตรงนี้", "ขอให้พรุ่งนี้ใจดีกับเราหน่อยนะ"]:
                            handle_chat(reply_token, 6)
                        elif user_message in ["หยุดคิดทุกอย่างสักแป๊บ แล้วปล่อยให้ตัวเองพัก", "หาอะไรเล็ก ๆ ที่ทำให้ตัวเองมีความสุข"]:
                            # เมื่อเลือกเสร็จแล้ว จบการสนทนา
                            line_bot_api.reply_message(reply_token, TextSendMessage(text="ขอบคุณที่ร่วมสนทนาด้วยกันค่ะ ขอให้คุณรู้สึกดีขึ้นนะคะ 😊"))
        except Exception as e:
            app.logger.error(f"Error processing webhook: {e}")

    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if not specified
    app.run(host="0.0.0.0", port=port)
