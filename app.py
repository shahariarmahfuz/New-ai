import os
import threading
import time
from datetime import datetime, timedelta
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Configure API keys directly in the code
API_KEY = "AIzaSyDaUj3swtOdBHSu-Jm_hP6nQuDiALHgsTY" # for /ai endpoint
API_KEY_TD = "AIzaSyDTovjgpg8zjzRFoCufjeYvRidcXSIInvQ" # for /td endpoint

genai.configure(api_key=API_KEY) # default api key configuration (for /ai)

# Set up the model with proper configuration for /ai endpoint
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp", # default model for /ai
    generation_config=generation_config,
)

# Set up the model with proper configuration for /td endpoint
generation_config_td = {
  "temperature": 0.2,
  "top_p": 0.85,
  "top_k": 30,
  "max_output_tokens": 50,  # আনুমানিক ২০ শব্দের মধ্যে রাখতে হলে ৫০ টোকেন যথেষ্ট
  "response_mime_type": "text/plain"
}

model_td = genai.GenerativeModel(
  model_name="gemini-2.0-flash", # model for /td
  generation_config=generation_config_td,
  api_key=API_KEY_TD # using different api key for /td endpoint
)

# Store user sessions and their last active time for /ai endpoint
user_sessions = {}

# Store user sessions and specific history for /td endpoint
td_histories = {}

SESSION_TIMEOUT = timedelta(hours=6)  # Set the session timeout to 6 hours

# Predefined history for /td endpoint, as provided in the second code snippet
TD_DEFAULT_HISTORY = [
    {
      "role": "user",
      "parts": [
        "Give me the title and episode 1 of Naruto Season 1.\n\nOf course, just remember that you can't add anything extra.\n",
      ],
    },
    {
      "role": "model",
      "parts": [
        "Enter: Naruto Uzumaki!\n",
      ],
    },
    {
      "role": "user",
      "parts": [
        "Give me the title and episode 1\n2 of Naruto Season 1.\n\nOf course, just remember that you can't add anything extra.",
      ],
    },
    {
      "role": "model",
      "parts": [
        "My Name Is Konohamaru!\n",
      ],
    },
    {
      "role": "user",
      "parts": [
        "Give me the title and episode 1 of one piece Season 1.\n\nOf course, just remember that you can't add anything extra.",
      ],
    },
    {
      "role": "model",
      "parts": [
        "Romance Dawn - The Adventure of Luffy!\n",
      ],
    },
]


@app.route("/ai", methods=["GET"])
def ai_response():
    """Handles AI response generation based on user input and session history for /ai endpoint."""
    question = request.args.get("q")
    user_id = request.args.get("id")

    if not question:
        return jsonify({"error": "Missing 'q' parameter"}), 400
    if not user_id:
        return jsonify({"error": "Missing 'id' parameter"}), 400

    # Initialize session history if user is new
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "history": [],
            "last_active": datetime.now()
        }

    # Update last active time
    user_sessions[user_id]["last_active"] = datetime.now()

    # Append user message to history
    user_sessions[user_id]["history"].append({"role": "user", "parts": [question]})

    try:
        # Create chat session with user's history
        chat_session = model.start_chat(history=user_sessions[user_id]["history"])

        # Get AI response
        response = chat_session.send_message(question)

        if response.text:
            # Append AI response to history
            user_sessions[user_id]["history"].append({"role": "model", "parts": [response.text]})
            return jsonify({"response": response.text})
        else:
            return jsonify({"error": "AI did not return any response"}), 500

    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route("/td", methods=["GET"])
def td_response():
    """Handles AI response generation for /td endpoint using gemini-2.0-flash model and specific history."""
    question = request.args.get("q")
    user_id = request.args.get("id")

    if not question:
        return jsonify({"error": "Missing 'q' parameter"}), 400
    if not user_id:
        return jsonify({"error": "Missing 'id' parameter"}), 400

    # Initialize session history with predefined history if user is new for /td endpoint
    if user_id not in td_histories:
        td_histories[user_id] = {
            "history": list(TD_DEFAULT_HISTORY), # Use a copy to avoid modifying the default history
            "last_active": datetime.now()
        }

    # Update last active time
    td_histories[user_id]["last_active"] = datetime.now()

    # Append user message to history
    td_histories[user_id]["history"].append({"role": "user", "parts": ["INSERT_INPUT_HERE".replace("INSERT_INPUT_HERE", question)]}) # Modified to replace placeholder

    try:
        # Create chat session with user's history using model_td and td_histories
        chat_session_td = model_td.start_chat(history=td_histories[user_id]["history"])

        # Get AI response using model_td
        response = chat_session_td.send_message("INSERT_INPUT_HERE".replace("INSERT_INPUT_HERE", question)) # Modified to replace placeholder

        if response.text:
            # Append AI response to history
            td_histories[user_id]["history"].append({"role": "model", "parts": [response.text]})
            return jsonify({"response": response.text})
        else:
            return jsonify({"error": "AI did not return any response from /td endpoint"}), 500

    except Exception as e:
        return jsonify({"error": f"Internal Server Error in /td endpoint: {str(e)}"}), 500


@app.route('/ping', methods=['GET'])
def ping():
    """Simple ping endpoint to check if server is alive."""
    return jsonify({"status": "alive"})

def clean_inactive_sessions():
    """Periodically checks and removes inactive user sessions for both /ai and /td."""
    while True:
        current_time = datetime.now()
        # Clean /ai sessions
        for user_id, session_data in list(user_sessions.items()):
            if current_time - session_data["last_active"] > SESSION_TIMEOUT:
                print(f"🧹 Removing inactive session for /ai endpoint user {user_id}")
                del user_sessions[user_id]
        # Clean /td sessions
        for user_id, session_data in list(td_histories.items()):
            if current_time - session_data["last_active"] > SESSION_TIMEOUT:
                print(f"🧹 Removing inactive session for /td endpoint user {user_id}")
                del td_histories[user_id]

        time.sleep(300)  # Check every 5 minutes

def keep_alive():
    """Periodically pings the server to keep it alive."""
    url = "https://new-ai-buxr.onrender.com/ping"  # Ping endpoint URL
    while True:
        time.sleep(300)  # Ping every 10 minutes
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("✅ Keep-Alive Ping Successful")
            else:
                print(f"⚠️ Keep-Alive Ping Failed: Status Code {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Keep-Alive Error: {e}")

# Run clean-up and keep-alive in separate threads
clean_up_thread = threading.Thread(target=clean_inactive_sessions, daemon=True)
clean_up_thread.start()

keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
