import os
import random
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Load the secret .env file
load_dotenv()

# Get the key from the secret file, NOT from here
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("No API key found! Check your .env file.")

genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-2.5-flash-lite")

conversation_history = []
performance_data = []
user_sessions = []


def build_system_prompt(role, difficulty, topic):
    return f"""
You are a strict but helpful technical interviewer.

Interview Role: {role}
Difficulty Level: {difficulty}
Topic: {topic}

Rules:
1. Ask ONE question at a time.
2. Keep responses under 50 words.
3. Be realistic and professional.
"""


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start_interview", methods=["POST"])
def start_interview():
    global conversation_history, performance_data

    performance_data = []
    data = request.json

    role = data.get("role", "frontend")
    difficulty = data.get("difficulty", "easy")
    topic = data.get("topic", "javascript")

    system_prompt = build_system_prompt(role, difficulty, topic)

    conversation_history = [
        {"role": "user", "parts": [system_prompt]},
        {"role": "model", "parts": ["Understood. I will conduct the interview."]}
    ]

    try:
        response = model.generate_content(
            conversation_history + [
                {"role": "user", "parts": ["Start the interview. Ask the first question only."]}
            ]
        )
        bot_reply = response.text
    except Exception:
        bot_reply = "Let's begin. What is a variable in programming?"

    conversation_history.append({"role": "model", "parts": [bot_reply]})
    return jsonify({"response": bot_reply})


@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"error": "No input provided"}), 400
    # --- PAUSE LOGIC START ---
    wait_keywords = ['wait', 'hold on', 'give me a minute', 'need some time', 'thinking', 'just a sec']
    if any(keyword in user_input.lower() for keyword in wait_keywords):
        return jsonify({
            "response": "Sure, take your time. I am listening.",
            "score": 0,
            "feedback": "Paused",
            "filler_count": 0
        })
    # --- PAUSE LOGIC END ---
    filler_words = ["um", "uh", "like", "actually"]
    fillers_count = sum(user_input.lower().count(w) for w in filler_words)

    conversation_history.append({"role": "user", "parts": [user_input]})

    try:
        response = model.generate_content(conversation_history)
        bot_reply = response.text
        # --- EMPTY FIX START ---
        if not bot_reply or not bot_reply.strip():
            bot_reply = "I didn't quite catch that. Could you repeat?"
        # --- EMPTY FIX END ---
    except Exception as e:
        print(f"SERVER ERROR: {e}")  # <--- This prints the red error to your terminal
        bot_reply = "I am having trouble connecting. Please check the terminal for the error."
    
    # Simple local scoring (quota safe)
    score = random.randint(6, 9)
    feedback = "Good structure. Add clearer examples."

    performance_data.append({
        "question": conversation_history[-2]["parts"][0],
        "answer": user_input,
        "score": score,
        "feedback": feedback,
        "filler_words": fillers_count
    })

    conversation_history.append({"role": "model", "parts": [bot_reply]})

    return jsonify({
        "response": bot_reply,
        "score": score,
        "feedback": feedback,
        "filler_count": fillers_count
    })


@app.route("/analytics", methods=["GET"])
def analytics():
    if not performance_data:
        return jsonify({"error": "No interview data"}), 400

    total_score = sum(item["score"] for item in performance_data)
    avg_score = round(total_score / len(performance_data), 2)
    total_fillers = sum(item["filler_words"] for item in performance_data)

    rating = "Excellent" if avg_score >= 8 else "Good" if avg_score >= 6 else "Needs Improvement"
    hiring_probability = min(95, int(avg_score * 10 + random.randint(-5, 5)))

    user_sessions.append({
        "avg_score": avg_score,
        "hiring_probability": hiring_probability
    })

    return jsonify({
        "average_score": avg_score,
        "total_questions": len(performance_data),
        "total_filler_words": total_fillers,
        "rating": rating,
        "hiring_probability": hiring_probability,
        "details": performance_data,
        "chart_scores": [item["score"] for item in performance_data],
        "sessions": user_sessions
    })


if __name__ == "__main__":
    app.run(debug=True)
