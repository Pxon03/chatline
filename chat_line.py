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

if not all([LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, GOOGLE_SCRIPT_URL]):
    raise ValueError("Missing API keys. Please set all required environment variables.")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
app = Flask(__name__)

# ตัวแปรเก็บประวัติการสนทนา
conversation_history = {}

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
        return f"ไม่พบข้อมูลของ {name} ในระบบ ❌"
    
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
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    if isinstance(message, str):  # ถ้าเป็นข้อความธรรมดา
        data = {"replyToken": reply_token, "messages": [{"type": "text", "text": message}]}
    else:  # ถ้าเป็น Flex Message
        data = {"replyToken": reply_token, "messages": [message]}

    response = requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)
    print("LINE API Response:", response.status_code, response.text)  # Debug ดู Response

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

if not all([LINE_ACCESS_TOKEN, LINE_CHANNEL_SECRET, GOOGLE_SCRIPT_URL]):
    raise ValueError("Missing API keys. Please set all required environment variables.")

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
app = Flask(__name__)

# ตัวแปรเก็บประวัติการสนทนา
conversation_history = {}

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
        return f"ไม่พบข้อมูลของ {name} ในระบบ ❌"
    
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

# ฟังก์ชัน OpenAI สำหรับประมวลผลข้อความ
 def get_openai_response(user_id, user_message):
     global conversation_history
     history = conversation_history.get(user_id, [])
     history.append({"role": "user", "content": user_message})
    
     try:
         response = openai.ChatCompletion.create(
             model="gpt-4o mini",
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


# ✅ ฟังก์ชันส่งข้อความกลับไปยัง LINE
def ReplyMessage(reply_token, message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }
    if isinstance(message, str):  # ถ้าเป็นข้อความธรรมดา
        data = {"replyToken": reply_token, "messages": [{"type": "text", "text": message}]}
    else:  # ถ้าเป็น Flex Message
        data = {"replyToken": reply_token, "messages": [message]}

    response = requests.post('https://api.line.me/v2/bot/message/reply', headers=headers, json=data)
    print("LINE API Response:", response.status_code, response.text)  # Debug ดู Response

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            app.logger.debug(f"Received full request: {json.dumps(req, indent=2, ensure_ascii=False)}")

            if 'events' in req:
                for event in req['events']:
                    reply_token = event.get('replyToken')
                    user_id = event.get('source', {}).get('userId', "")
                    user_message = event.get('message', {}).get('text', "")

                    if not reply_token or not user_message:
                        continue

                    # ✅ ตรวจสอบว่าผู้ใช้อยู่ในโหมดพูดคุยหรือไม่
                    if user_id in conversation_history:
                        handle_conversation(user_id, reply_token, user_message)  # ดำเนินการพูดคุยต่อ
                    elif user_message == "พูดคุย":
                        conversation_history[user_id] = []  # เริ่มต้นประวัติการสนทนาใหม่
                        handle_conversation(user_id, reply_token, user_message)
                    elif user_message == "แบบประเมิน":
                        ReplyAssessmentMessage(reply_token)
                    else:
                        user_info_list = get_user_info(user_message)
                        response_message = format_user_info(user_message, user_info_list) if user_info_list else "ไม่พบข้อมูล"
                        ReplyMessage(reply_token, response_message)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

# ✅ รัน Flask บน Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render จะกำหนด PORT ผ่าน Environment Variables
    app.run(host="0.0.0.0", port=port, debug=True)


@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            app.logger.debug(f"Received full request: {json.dumps(req, indent=2, ensure_ascii=False)}")

            if 'events' in req:
                for event in req['events']:
                    reply_token = event.get('replyToken')
                    user_id = event.get('source', {}).get('userId', "")
                    user_message = event.get('message', {}).get('text', "")

                    if not reply_token or not user_message:
                        continue

                    # ✅ ตรวจสอบว่าผู้ใช้อยู่ในโหมดพูดคุยหรือไม่
                    if user_id in conversation_history:
                        handle_conversation(user_id, reply_token, user_message)  # ดำเนินการพูดคุยต่อ
                    elif user_message == "พูดคุย":
                        conversation_history[user_id] = []  # เริ่มต้นประวัติการสนทนาใหม่
                        handle_conversation(user_id, reply_token, user_message)
                    elif user_message == "แบบประเมิน":
                        ReplyAssessmentMessage(reply_token)
                    else:
                        user_info_list = get_user_info(user_message)
                        response_message = format_user_info(user_message, user_info_list) if user_info_list else "ไม่พบข้อมูล"
                        ReplyMessage(reply_token, response_message)

            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

# ✅ รัน Flask บน Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render จะกำหนด PORT ผ่าน Environment Variables
    app.run(host="0.0.0.0", port=port, debug=True)
