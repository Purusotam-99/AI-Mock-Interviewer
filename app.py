import os
import json
import random
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv

# Load API Key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise ValueError("No API key found! Check your .env file.")

genai.configure(api_key=api_key)

app = Flask(__name__)

# --- OPTIMIZED CONFIGURATION ---
# We force the model to output strict JSON. This combines 3 calls into 1.
generation_config = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 2000,
    "response_mime_type": "application/json", # <--- MAGIC LINE
}

# Updated System Instruction: Ask for everything in one go.
system_prompt = """
You are a professional technical interviewer. 
For every user input, you must return a JSON object with exactly these 3 fields:
1. "reply": Your conversational response to the candidate. Keep it professional but encouraging. Ask the next question here.
2. "feedback": Specific grammar or technical feedback on their last answer. If it was perfect, say "Excellent phrasing."
3. "score": An integer from 1 to 10 based on the quality of their answer.

Example Output:
{
    "reply": "That is correct. Now, can you explain polymorphism?",
    "feedback": "You missed the 'self' parameter in your class method.",
    "score": 7
}
"""

# Use the FLASH model for speed (it supports JSON mode natively)
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    generation_config=generation_config,
    system_instruction=system_prompt
)

# Store chat history in memory
chat_session = None
performance_data = []

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start_interview', methods=['POST'])
def start_interview():
    global chat_session, performance_data
    performance_data = [] # Reset data
    
    # Start a new chat session
    chat_session = model.start_chat(history=[])
    
    # Send an initial hidden prompt to kickstart the JSON behavior
    try:
        response = chat_session.send_message("The interview is starting. Introduce yourself and ask the first question.")
        data = json.loads(response.text)
        return jsonify(data)
    except Exception as e:
        print(f"Error starting interview: {e}")
        # Fallback if AI fails
        return jsonify({
            "reply": "Hello! I am ready. Let's start with a simple question: What is a variable?",
            "feedback": "None",
            "score": 0
        })

@app.route('/chat', methods=['POST'])
def chat():
    global performance_data
    user_input = request.json.get('message')
    
    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    try:
        # SINGLE API CALL (Replaces the 3 separate calls)
        response = chat_session.send_message(user_input)
        
        # Parse the JSON response
        data = json.loads(response.text)
        
        # Save data for analytics
        performance_data.append({
            "question": "Previous Question", # Simplified for now
            "answer": user_input,
            "score": data.get("score", 0),
            "feedback": data.get("feedback", "")
        })
        
        return jsonify({
            "reply": data.get("reply"),
            "feedback": data.get("feedback"),
            "score": data.get("score")
        })

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({
            "reply": "I am having trouble connecting. Please check the terminal.",
            "feedback": "Error",
            "score": 0
        }), 500

@app.route("/analytics", methods=["GET"])
def analytics():
    if not performance_data:
        return jsonify({"error": "No interview data"}), 400

    total_score = sum(item["score"] for item in performance_data)
    avg_score = round(total_score / len(performance_data), 2)

    rating = "Excellent" if avg_score >= 8 else "Good" if avg_score >= 6 else "Needs Improvement"
    hiring_probability = min(95, int(avg_score * 10))

    return jsonify({
        "average_score": avg_score,
        "total_questions": len(performance_data),
        "rating": rating,
        "hiring_probability": hiring_probability,
        "details": performance_data
    })

if __name__ == '__main__':
    app.run(debug=True)
