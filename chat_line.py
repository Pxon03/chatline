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

# ✅ ฟังก์ชันส่ง Flex Message สำหรับคำถามและตัวเลือก
def send_question(reply_token, question, options):
    flex_message = {
        "type": "flex",
        "altText": question,
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": question, "weight": "bold", "size": "lg"},
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#5AACFF", "action": {"type": "message", "label": option, "text": option}} 
                    for option in options
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

# ฟังก์ชันส่ง Flex Message สำหรับแบบประเมิน
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

# ส่งข้อความตอบกลับไปที่ LINE
def ReplyMessage(reply_token, text_message):
    if not text_message.strip():
        return  # ถ้าไม่มีข้อความ ไม่ต้องส่งอะไรกลับไป

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
        response = requests.post(LINE_API, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error sending reply to LINE API: {e}")

# ดึงข้อมูลจาก Google Apps Script
def get_user_info(name):
    try:
        params = {"name": name}
        response = requests.get(GOOGLE_SCRIPT_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("user_info") if data.get("status") == "success" else None
    except Exception as e:
        app.logger.error(f"Error fetching user info: {e}")
        return None

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

# ฟังก์ชัน OpenAI สำหรับประมวลผลข้อความ
def get_openai_response(user_id, user_message):
    global conversation_history
    history = conversation_history.get(user_id, [])
    history.append({"role": "user", "content": user_message})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "You are a helpful assistant, YOU MUST RESPOND IN THAI"}] + history,
            max_tokens=150,
            temperature=0.7,
            stop=["\n\n"]
        )
        bot_reply = response["choices"][0]["message"]["content"]
        history.append({"role": "assistant", "content": bot_reply})
        conversation_history[user_id] = history[-10:]  # เก็บประวัติแค่ 10 ข้อความล่าสุด
        return bot_reply
    except Exception as e:
        app.logger.error(f"Error from OpenAI API: {e}")
        return "เกิดข้อผิดพลาด กรุณาลองใหม่"

# สถานะคำถามที่กำลังถาม
question_flow = {
    "ถาม1": ("วันนี้เป็นยังไงบ้าง?", ["โอเคอยู่ มีพลังใช้ได้", "เหนื่อยนิดหน่อย อยากพัก"]),
    "ถาม2": ("ถ้าตอนนี้มีใครสักคนบอกอะไรให้คุณรู้สึกดีขึ้น คุณอยากได้ยินคำไหนมากกว่า?", ["ไม่เป็นไรนะ คุณเก่งมากแล้ว", "พักก่อนก็ได้ เดี๋ยวค่อยไปต่อ"]),
    "ถาม3": ("เวลารู้สึกเครียด ๆ คุณอยากให้ตัวเองลองทำอะไร?", ["หลับตาแล้วหายใจลึก ๆ สัก 5 ครั้ง", "ฟังเพลงเงียบ ๆ ให้ใจได้พัก"]),
    "ถาม4": ("ถ้าต้องเปรียบเทียบความรู้สึกตอนนี้เป็นสีหนึ่งสี คิดว่ามันเป็นสีอะไร?", ["ฟ้า สงบขึ้นมาหน่อย สบาย ๆ", "เทา เหนื่อย ๆ ไม่แน่ใจว่ารู้สึกยังไง"]),
    "ถาม5": ("ถ้าคุณต้องเขียนจดหมายสั้น ๆ ให้ตัวเองในวันนี้ คุณจะเริ่มต้นด้วยคำว่าอะไร?", ["ขอบคุณที่ยังพยายามอยู่ตรงนี้", "ขอให้พรุ่งนี้ใจดีกับเราหน่อยนะ"]),
    "ถาม6": ("บางครั้งความเครียดก็มาโดยไม่บอกกล่าว ถ้าต้องเลือกสักอย่าง คุณอยากลอง…", ["หยุดคิดทุกอย่างสักแป๊บ แล้วปล่อยให้ตัวเองพัก", "หาอะไรเล็ก ๆ ที่ทำให้ตัวเองมีความสุข"])
}

# ตัวแปรเก็บสถานะของผู้ใช้
user_status = {}

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
                    user_id = event.get('source', {}).get('userId')
                    user_message = event.get('message', {}).get('text')

                    if not reply_token or not user_message:
                        continue

                    # เริ่มคำถามแรกหากผู้ใช้เริ่มต้นใหม่
                    if user_message.lower() == "เริ่มต้นใหม่":
                        user_status[user_id] = "ถาม1"  # กำหนดสถานะเริ่มจากคำถามแรก
                        send_question(reply_token, *question_flow["ถาม1"])

                    elif user_id in user_status:
                        current_question = user_status[user_id]
                        next_question = None
                        if current_question == "ถาม1":
                            next_question = "ถาม2"
                        elif current_question == "ถาม2":
                            next_question = "ถาม3"
                        elif current_question == "ถาม3":
                            next_question = "ถาม4"
                        elif current_question == "ถาม4":
                            next_question = "ถาม5"
                        elif current_question == "ถาม5":
                            next_question = "ถาม6"
                        elif current_question == "ถาม6":
                            next_question = None  # ไม่มีคำถามถัดไป

                        if next_question:
                            user_status[user_id] = next_question
                            send_question(reply_token, *question_flow[next_question])
                        else:
                            # ถ้าไม่มีคำถามถัดไปแสดงข้อความว่าเสร็จสิ้น
                            ReplyMessage(reply_token, "คุณตอบคำถามทั้งหมดเสร็จสิ้นแล้ว ขอบคุณค่ะ!")

            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
