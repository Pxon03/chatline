from flask import Flask, request, jsonify
import json
import requests as requests_lib
import os
from openai import OpenAI

# ดึงค่า API Key และ Line Access Token จาก Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_ACCESS_TOKEN = os.getenv("LINE_ACCESS_TOKEN")

# ตรวจสอบว่ามีการตั้งค่า ENV Variable หรือไม่
if not OPENAI_API_KEY or not LINE_ACCESS_TOKEN:
    raise ValueError("Missing API keys. Please set OPENAI_API_KEY and LINE_ACCESS_TOKEN as environment variables.")

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

def get_openai_response(user_message):
    payload = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant, YOU MUST RESPOND IN THAI"},
            {"role": "user", "content": user_message}
        ],
        max_tokens=100,
    )
    response = payload.choices[0].message.content
    return response

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
                        Reply_token = event['replyToken']
                        ReplyMessage(Reply_token, response_message)
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500
    elif request.method == "GET":
        return "GET", 200

def ReplyMessage(Reply_token, TextMessage):
    LINE_API = 'https://api.line.me/v2/bot/message/reply'

    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }

    data = {
        "replyToken": Reply_token,
        "messages": [{
            "type": "text",
            "text": TextMessage
        }]
    }
    response = requests_lib.post(LINE_API, headers=headers, data=json.dumps(data))
    return response.status_code

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # รองรับ PORT จาก Render
    app.run(debug=True, host="0.0.0.0", port=port)