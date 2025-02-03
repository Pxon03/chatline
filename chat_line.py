from openai import OpenAI
from flask import Flask, request, jsonify
import json
import requests as requests_lib
import os
import openai

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")

# ตรวจสอบว่ามีการตั้งค่า ENV Variable หรือไม่
if not OPENAI_API_KEY or not LINE_ACCESS_TOKEN:
    raise ValueError("Missing API keys. Please set OPENAI_API_KEY and LINE_ACCESS_TOKEN as environment variables.")

# ตั้งค่า API Key ของ OpenAI
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

# เก็บประวัติการสนทนา
conversation_history = {}

def get_openai_response(user_id, user_message):
    global conversation_history
    
    # ดึงประวัติการสนทนาของผู้ใช้จาก memory
    if user_id in conversation_history:
        history = conversation_history[user_id]
    else:
        history = []

    # เพิ่มข้อความของผู้ใช้
    history.append({"role": "user", "content": user_message})

    try:
        # เรียก OpenAI API เพื่อให้คำตอบ
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # ใช้โมเดล gpt-4o-mini
            messages=[
                {"role": "system", "content": "You are a helpful assistant, YOU MUST RESPOND IN THAI"}
            ] + history,
            max_tokens=200,  # กำหนดจำนวนโทเค็นสูงสุด
        )

        bot_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": bot_reply})
        
        # เก็บประวัติการสนทนาใหม่กลับไปยัง memory
        conversation_history[user_id] = history

        # จำกัดจำนวนประวัติการสนทนาเพื่อประหยัดโทเค็น
        if len(history) > 10:
            history.pop(0)

        return bot_reply
    except Exception as e:
        app.logger.error(f"Error: {e}")
        return "เกิดข้อผิดพลาด กรุณาลองใหม่"

@app.route('/webhook', methods=['POST', 'GET']) 
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            if 'events' in req:
                for event in req['events']:
                    if event['type'] == 'message' and event['message']['type'] == 'text':
                        user_message = event['message']['text']
                        user_id = event['source']['userId']
                        response_message = get_openai_response(user_id, user_message)
                        reply_token = event['replyToken']
                        ReplyMessage(reply_token, response_message)
            return jsonify({"status": "success"}), 200  # ตอบกลับ 200 OK
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # รองรับ PORT จาก Render
    app.run(debug=True, host="0.0.0.0", port=port)





