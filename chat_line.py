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

# ✅ ฟังก์ชันส่ง Flex Message สำหรับการพูดคุย
def ReplyChatMessage(reply_token):
    flex_message = {
        "type": "flex",
        "altText": "มาพูดคุยกันหน่อย 😊",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "😊 วันนี้เป็นยังไงบ้าง?", "weight": "bold", "size": "xl", "align": "center"}
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
                        "action": {"type": "message", "label": "โอเคอยู่ มีพลังใช้ได้", "text": "โอเคอยู่ มีพลังใช้ได้"}
                    },
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#FF6B6B",
                        "action": {"type": "message", "label": "เหนื่อยนิดหน่อย อยากพัก", "text": "เหนื่อยนิดหน่อย อยากพัก"}
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

# ✅ ฟังก์ชันส่ง Flex Message สำหรับคำถามต่อไปในพูดคุย
def ReplyFollowUpQuestion(reply_token, question, options):
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
                        ReplyChatMessage(reply_token)
                    elif user_message.startswith("ดูข้อมูลของ "):  # ตรวจสอบว่าเป็นคำว่า "ดูข้อมูลของ"
                        name = user_message.replace("ดูข้อมูลของ ", "")  # เอาคำว่า "ดูข้อมูลของ" ออก
                        user_info_list = get_user_info(name)
                        formatted_info = format_user_info(name, user_info_list)
                        if formatted_info:
                            line_bot_api.reply_message(reply_token, TextSendMessage(text=formatted_info))
                    elif user_message == "โอเคอยู่ มีพลังใช้ได้" or user_message == "เหนื่อยนิดหน่อย อยากพัก":
                        ReplyFollowUpQuestion(reply_token, "ถ้าตอนนี้มีใครสักคนบอกอะไรให้คุณรู้สึกดีขึ้น คุณอยากได้ยินคำไหนมากกว่า?", ["ไม่เป็นไรนะ คุณเก่งมากแล้ว", "พักก่อนก็ได้ เดี๋ยวค่อยไปต่อ"])


                    elif user_message == "ไม่เป็นไรนะ คุณเก่งมากแล้ว" or user_message == "พักก่อนก็ได้ เดี๋ยวค่อยไปต่อ":
                        ReplyFollowUpQuestion(reply_token, "คุณต้องการให้เราช่วยเหลืออะไรไหม?", ["ส่งคำแนะนำให้", "ให้คำปรึกษาเพิ่มเติม"])
        except Exception as e:
            app.logger.error(f"Error processing webhook: {e}")

    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if not specified
    app.run(host="0.0.0.0", port=port)
