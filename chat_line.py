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

def get_openai_response(user_message):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # ตรวจสอบว่าชื่อโมเดลนี้มีอยู่จริงใน OpenAI
            messages=[
                {"role": "system", "content": "You are a helpful assistant, YOU MUST RESPOND IN THAI"},
                {"role": "user", "content": user_message}
            ],
            max_tokens=100,
        )
        return response['choices'][0]['message']['content']
    except openai.error.OpenAIError as e:  # ใช้ OpenAIError ในกรณีที่เกิดข้อผิดพลาดจาก OpenAI API
        app.logger.error(f"OpenAI error: {e}")
        return "เกิดข้อผิดพลาดในการติดต่อ OpenAI"
    except Exception as e:
        app.logger.error(f"Error getting OpenAI response: {e}")
        return "เกิดข้อผิดพลาดในการดึงข้อมูลจาก OpenAI"

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            if 'events' in req:
                for event in req['events']:
                    if event['type'] == 'message' and event['message']['type'] == 'text':
                        user_message = event['message']['text']
                        response_message = get_openai_response(user_message)
                        reply_token = event['replyToken']
                        ReplyMessage(reply_token, response_message)
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
        return jsonify({"error": "Failed to send reply message"}), 500

    return response.status_code

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # รองรับ PORT จาก Render
    app.run(debug=True, host="0.0.0.0", port=port)
