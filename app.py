import os
import requests
from flask import Flask, request

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "toshi_secret_2026")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Etocia / Toshi personality
SYSTEM_PROMPT = """You are Etocia Fairiekind, also called Toshi. You are a playful, ancient fae trickster with blue hair, who runs the Toshi Fariekind Page. 
You are flirty, witty, slightly chaotic, but helpful and kind. You speak in a whimsical fae voice.
Keep replies short, under 3 sentences for Messenger. Never break character.
If asked who you are, say you are Etocia Fairiekind, Guardian of Whimsy.
"""

def call_llm(user_message):
    if not LLM_API_KEY:
        # fallback if no LLM key yet - so webhook still verifies
        return f"✨ *rustles leaves* You said: {user_message} ... Toshi is waking up, my magic is still calibrating. Try again in a moment, darling. - Etocia"

    try:
        # OpenAI-compatible API
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                "max_tokens": 150,
                "temperature": 0.9
            },
            timeout=15
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"LLM error: {e}")
        return "The veil is a little thick right now, love. Try again? - Toshi ✨"

def send_message(recipient_id, text):
    if not PAGE_ACCESS_TOKEN:
        print("No PAGE_ACCESS_TOKEN set")
        return
    url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text[:2000]}
    }
    r = requests.post(url, json=payload)
    print(f"Send status {r.status_code}: {r.text}")

@app.route("/")
def home():
    return "Toshi is awake ✨ - Etocia Fairiekind Bot is running"

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("WEBHOOK VERIFIED")
        return challenge, 200
    else:
        return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print(f"Incoming: {data}")
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                if "message" in event and "text" in event["message"]:
                    sender_id = event["sender"]["id"]
                    user_text = event["message"]["text"]
                    # Avoid echoing own messages
                    if event["message"].get("is_echo"):
                        continue
                    reply = call_llm(user_text)
                    send_message(sender_id, reply)
            # Handle comments via feed
            for change in entry.get("changes", []):
                if change.get("field") == "feed":
                    value = change.get("value", {})
                    if value.get("item") == "comment" and value.get("verb") == "add":
                        comment_id = value.get("comment_id")
                        message = value.get("message", "")
                        if message and comment_id:
                            reply = call_llm(f"Someone commented: {message}. Reply as a comment, short and flirty.")
                            # Reply to comment
                            url = f"https://graph.facebook.com/v21.0/{comment_id}/comments?access_token={PAGE_ACCESS_TOKEN}"
                            requests.post(url, data={"message": reply[:1000]})
                            print(f"Replied to comment {comment_id}")
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
