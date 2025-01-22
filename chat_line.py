from flask import Flask, request, jsonify
import os
import json
import requests as requests_lib
from openai import OpenAI
from flask_cors import CORS

# Load environment variables
OPENAI_API_KEY = os.environ.get("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")
LINE_ACCESS_TOKEN = os.environ.get("CgVwlTUniQ4pJs+zMMCbXVRqceu67LMtO5HfBlu5zqWU/1h8ywBJIX84r3pSXYnJB6cDiGx4dRo643V/Z/jZ6I0OO6DEMH7cNPcI1R6WeZo4ICdF4J8MYzShfnoEM1SikseUwu6PNPc8q1IKNtqS2gdB04t89/1O/w1cDnyilFU=")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

def get_openai_response(user_message):
    try:
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
    except Exception as e:
        app.logger.error(f"Error calling OpenAI API: {e}")
        return "ขออภัย มีข้อผิดพลาดในการให้บริการ"

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    if request.method == "POST":
        try:
            req = request.json
            if 'events' in req:
                for event in req.get('events', []):
                    if event.get('type') == 'message' and event['message'].get('type') == 'text':
                        user_message = event['message']['text']
                        response_message = get_openai_response(user_message)
                        reply_token = event['replyToken']
                        send_line_reply(reply_token, response_message)
            return jsonify({"status": "success"}), 200
        except Exception as e:
            app.logger.error(f"Error processing POST request: {e}")
            return jsonify({"error": str(e)}), 500

    elif request.method == "GET":
        return "Webhook is running!", 200

def send_line_reply(reply_token, text_message):
    LINE_API_URL = 'https://api.line.me/v2/bot/message/reply'
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'
    }

    data = {
        "replyToken": reply_token,
        "messages": [{
            "type": "text",
            "text": text_message
        }]
    }

    try:
        response = requests_lib.post(LINE_API_URL, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        app.logger.info("Message sent successfully")
    except requests_lib.exceptions.RequestException as e:
        app.logger.error(f"Failed to send LINE message: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use PORT from environment variable
    app.run(debug=True, host="0.0.0.0", port=port)