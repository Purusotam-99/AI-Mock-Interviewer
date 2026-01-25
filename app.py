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

# --- 1. KNOWLEDGE BASE ---
KNOWLEDGE_BASE = {
    "javascript": {
        "concepts": [
            "Closure", "Event Loop", "Hoisting", "Promise", "Async/Await", 
            "Prototype Chain", "Shadow DOM", "Event Bubbling", "Currying", 
            "Memoization", "Debouncing", "Throttling", "Service Worker",
            "CORS", "Strict Mode", "IIFE", "This Keyword", "Generators", 
            "WeakMap", "Set", "Proxy Object", "Event Delegation", 
            "Higher-Order Functions", "Temporal Dead Zone", "Destructuring"
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

# --- 2. TEMPLATE POOLS ---
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
        "Can you explain potential pitfalls or edge cases when using '{concept}'?"
    ],
    "practical": [
        "Can you describe a real-world scenario where you would use '{concept}'?",
        "If you were optimizing a system for performance, how would '{concept}' help?"
    ]
}

# --- 3. LOGIC GENERATOR ---
def get_distribution(count):
    if count == 5:  return {"easy": 2, "medium": 2, "hard": 1, "practical": 0}
    if count == 8:  return {"easy": 2, "medium": 3, "hard": 2, "practical": 1}
    if count == 12: return {"easy": 3, "medium": 4, "hard": 3, "practical": 2}
    return {"easy": count, "medium": 0, "hard": 0, "practical": 0}

def generate_interview_questions(topic, count):
    data = KNOWLEDGE_BASE.get(topic, KNOWLEDGE_BASE["javascript"])
    dist = get_distribution(count)
    questions = [] # Will store objects: {"text": "...", "difficulty": "easy"}
    
    # Shuffle concepts to ensure no repeats
    available_concepts = data["concepts"][:]
    random.shuffle(available_concepts)
    
    def get_concept():
        if available_concepts: return available_concepts.pop()
        return "Core Concept" 

    # Helper to create the question object
    def add_question(diff):
        # Comparison logic for Hard questions
        if diff == "hard" and random.random() < 0.5 and "comparisons" in data and data["comparisons"]:
            pair = random.choice(data["comparisons"])
            text = f"What is the key technical difference between '{pair[0]}' and '{pair[1]}'?"
        else:
            # Standard Template logic
            template = random.choice(TEMPLATE_POOLS[diff])
            text = template.format(concept=get_concept())
            
        questions.append({"text": text, "difficulty": diff})

    # Generate based on distribution
    for _ in range(dist["easy"]): add_question("easy")
    for _ in range(dist["medium"]): add_question("medium")
    for _ in range(dist["hard"]): add_question("hard")
    for _ in range(dist["practical"]): add_question("practical")
    
    return questions

# --- FLASK ROUTES ---

generation_config = { "temperature": 0.7, "response_mime_type": "application/json" }
model = genai.GenerativeModel("gemini-3-flash-preview", generation_config=generation_config)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start_interview', methods=['POST'])
def start_interview():
    data = request.json
    topic = data.get("topic", "javascript")
    count = int(data.get("length", 8))
    
    # Generate the List of Objects
    interview_queue = generate_interview_questions(topic, count)
    
    session['questions_queue'] = interview_queue
    session['current_index'] = 0
    session['history'] = [] 
    
    # Get the first question object
    first_q = interview_queue[0]
    
    return jsonify({
        "reply": f"Hello! I have prepared a {count}-question {topic} interview. Let's begin.",
        "next_question": first_q  # Sends {text: "...", difficulty: "..."}
    })

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    questions_queue = session.get('questions_queue', [])
    idx = session.get('current_index', 0)
    history = session.get('history', [])
    
    # 1. Record Answer
    if idx < len(questions_queue):
        current_q_text = questions_queue[idx]['text'] # Access the text property
        history.append(f"Q: {current_q_text}\nA: {user_input}")
        session['history'] = history
    
    # 2. Move Index
    idx += 1
    session['current_index'] = idx
    
    # 3. Check if done
    if idx >= len(questions_queue):
        return jsonify({
            "finished": True,
            "reply": "That concludes our interview! Click 'End & Analyze' to see your report."
        })
        
    # 4. Get Next Question Object
    next_q = questions_queue[idx]
    
    return jsonify({
        "reply": "Thank you.", # Optional filler text
        "next_question": next_q # Sends {text: "...", difficulty: "..."}
    })

@app.route('/analytics', methods=['GET'])
def analytics():
    history = session.get("history", [])
    if not history: return jsonify({"error": "No history"}), 400
    
    full_transcript = "\n".join(history)
    
    prompt = f"""
    Analyze this technical interview transcript.
    Return a JSON object with:
    1. "average_score": (Integer 1-10)
    2. "hiring_probability": (Integer 0-100)
    3. "rating": (String: "Excellent", "Good", etc)
    4. "details": List of objects {{"score": int, "feedback": string}} for each question.
    5. "weak_concepts": List of strings (Topics struggled with).
    6. "strong_concepts": List of strings (Topics explained well).
    7. "missed_keywords": List of strings (Key terms missing).
    
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
