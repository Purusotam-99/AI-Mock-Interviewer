import os
import json
import random
from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
from dotenv import load_dotenv

# Load API Key
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key: raise ValueError("No API key found! Check your .env file.")

genai.configure(api_key=api_key)
app = Flask(__name__)
app.secret_key = "super_secret_key_for_session" 

# --- KNOWLEDGE BASE (Concepts & Comparisons) ---
KNOWLEDGE_BASE = {
    "javascript": {
        "concepts": [
            "Closure", "Event Loop", "Hoisting", "Promise", "Async/Await", 
            "Prototype Chain", "Shadow DOM", "Event Bubbling", "Event Capturing",
            "Currying", "Memoization", "Debouncing", "Throttling", "Service Worker",
            "Web Worker", "CORS", "Strict Mode", "IIFE", "This Keyword", 
            "Generators", "WeakMap", "Set", "Proxy Object", "Event Delegation", 
            "Higher-Order Functions", "Temporal Dead Zone", "Destructuring", 
            "Rest/Spread Operator", "Modules (ES6)", "Callback Hell"
        ],
        "comparisons": [
            ("var", "let"), ("var", "const"), ("let", "const"),
            ("==", "==="), ("null", "undefined"), ("Arrow Function", "Regular Function"),
            ("Map", "Object"), ("Promise", "Callback"), ("localStorage", "sessionStorage")
        ]
    },
    "dsa": {
        "concepts": [
            "Array", "Linked List", "Stack", "Queue", "Hash Table", 
            "Binary Search Tree", "Min Heap", "Max Heap", "Graph", "Trie", 
            "Quick Sort", "Merge Sort", "Binary Search", "BFS", "DFS", 
            "Dynamic Programming", "Greedy Algorithm", "Recursion", 
            "Two Pointers", "Sliding Window", "Backtracking"
        ],
        "comparisons": [
            ("Array", "Linked List"), ("Stack", "Queue"), ("BFS", "DFS"),
            ("Quick Sort", "Merge Sort"), ("Hash Map", "BST"),
            ("Recursion", "Iteration"), ("Time Complexity", "Space Complexity")
        ]
    },
    "sql": {
        "concepts": [
            "Primary Key", "Foreign Key", "Indexing", "Normalization", "ACID", 
            "View", "Stored Procedure", "Trigger", "Cursor", "Subquery", 
            "Window Functions", "CTE", "Inner Join", "Left Join", "Union", 
            "Group By", "Order By"
        ],
        "comparisons": [
            ("WHERE", "HAVING"), ("DELETE", "TRUNCATE"), ("CHAR", "VARCHAR"),
            ("SQL", "NoSQL"), ("Clustered Index", "Non-Clustered Index"),
            ("Inner Join", "Outer Join"), ("Union", "Union All")
        ]
    },
    "python": {
        "concepts": ["Decorator", "Generator", "Lambda", "GIL", "List Comprehension"],
        "comparisons": [("List", "Tuple"), ("is", "=="), ("Deep Copy", "Shallow Copy")]
    }
}

TEMPLATE_POOLS = {
    "easy": [
        "Can you explain the concept of '{concept}' in simple terms?",
        "What is the fundamental purpose of '{concept}'?",
        "In your own words, define '{concept}'."
    ],
    "medium": [
        "What are the main use cases for '{concept}'?",
        "Why would a developer choose to use '{concept}' over alternatives?",
        "What are the advantages and disadvantages of using '{concept}'?"
    ],
    "hard": [
        "How does '{concept}' work internally under the hood?",
        "Can you explain the potential pitfalls or edge cases when using '{concept}'?"
    ],
    "practical": [
        "Can you describe a real-world scenario where you would use '{concept}'?",
        "If you were optimizing a system for performance, how would '{concept}' help?"
    ]
}

def get_distribution(count):
    if count == 5:  return {"easy": 2, "medium": 2, "hard": 1, "practical": 0}
    if count == 8:  return {"easy": 2, "medium": 3, "hard": 2, "practical": 1}
    if count == 12: return {"easy": 3, "medium": 4, "hard": 3, "practical": 2}
    return {"easy": count, "medium": 0, "hard": 0, "practical": 0}

def generate_interview_questions(topic, count):
    data = KNOWLEDGE_BASE.get(topic, KNOWLEDGE_BASE["javascript"])
    dist = get_distribution(count)
    questions = []
    
    # --- FIX: NO REPEATS GUARANTEED ---
    # We grab ALL concepts, shuffle them, and then pop them one by one.
    available_concepts = data["concepts"][:]
    random.shuffle(available_concepts)
    
    def get_concept():
        if available_concepts:
            return available_concepts.pop()
        return "Generic Concept" # Fallback if we run out (unlikely)

    # 1. Easy
    for _ in range(dist["easy"]):
        questions.append(random.choice(TEMPLATE_POOLS["easy"]).format(concept=get_concept()))

    # 2. Medium
    for _ in range(dist["medium"]):
        questions.append(random.choice(TEMPLATE_POOLS["medium"]).format(concept=get_concept()))

    # 3. Hard
    for _ in range(dist["hard"]):
        if random.random() < 0.5 and "comparisons" in data and data["comparisons"]:
            pair = random.choice(data["comparisons"])
            questions.append(f"What is the key technical difference between '{pair[0]}' and '{pair[1]}'?")
        else:
            questions.append(random.choice(TEMPLATE_POOLS["hard"]).format(concept=get_concept()))

    # 4. Practical
    for _ in range(dist["practical"]):
        questions.append(random.choice(TEMPLATE_POOLS["practical"]).format(concept=get_concept()))
    
    return questions

# --- FLASK ROUTES ---
generation_config = { "temperature": 0.7, "response_mime_type": "application/json" }
model = genai.GenerativeModel("gemini-3-flash-preview", generation_config=generation_config)

@app.route('/')
def home(): return render_template('index.html')

@app.route('/start_interview', methods=['POST'])
def start_interview():
    data = request.json
    topic = data.get("topic", "javascript")
    count = int(data.get("length", 8))
    
    interview_questions = generate_interview_questions(topic, count)
    
    session['questions_queue'] = interview_questions
    session['current_index'] = 0
    session['history'] = [] 
    
    return jsonify({"reply": f"Hello! I've prepared {count} unique {topic} questions. Let's begin. {interview_questions[0]}"})

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    questions_queue = session.get('questions_queue', [])
    idx = session.get('current_index', 0)
    history = session.get('history', [])
    
    if idx < len(questions_queue):
        current_q = questions_queue[idx]
        history.append(f"Q: {current_q}\nA: {user_input}")
        session['history'] = history
    
    idx += 1
    session['current_index'] = idx
    
    if idx >= len(questions_queue):
        return jsonify({"reply": "Interview Complete! Click End to see your Heatmap.", "feedback": "Done"})
        
    return jsonify({"reply": questions_queue[idx]})

@app.route('/analytics', methods=['GET'])
def analytics():
    history = session.get("history", [])
    if not history: return jsonify({"error": "No history"}), 400
    
    full_transcript = "\n".join(history)
    
    # --- NEW: ADVANCED ANALYTICS PROMPT ---
    prompt = f"""
    Analyze this technical interview transcript.
    Return a JSON object with:
    1. "average_score": (Integer 1-10)
    2. "hiring_probability": (Integer 0-100)
    3. "rating": (String)
    4. "details": List of objects {{"score": int, "feedback": string}} for each question.
    5. "weak_concepts": List of strings (The specific topics the candidate struggled with).
    6. "strong_concepts": List of strings (Topics they explained well).
    7. "missed_keywords": List of strings (Important technical terms they forgot to mention).
    
    TRANSCRIPT:
    {full_transcript}
    """
    
    try:
        response = model.generate_content(prompt)
        return jsonify(json.loads(response.text))
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to generate report"}), 500

if __name__ == '__main__':
    app.run(debug=True)
