import os
import mimetypes
import uuid
import json
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from dotenv import load_dotenv
import google.generativeai as genai
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename

load_dotenv()

mimetypes.add_type('application/javascript', '.js')

app = Flask(__name__)

# --- CONFIGURATION ---
app.config.update(
    UPLOAD_FOLDER='uploads',
    SECRET_KEY=os.getenv("SECRET_KEY", "dev_secret_key_998877"),
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=5 * 1024 * 1024 
)

# --- AI Configuration ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash') # Recommended stable model

def extract_text_from_pdf(pdf_file):
    """Utility to extract text from an uploaded PDF file safely."""
    text = ""
    try:
        if not pdf_file or pdf_file.filename == '':
            return "No resume provided."
        pdf_reader = PdfReader(pdf_file)
        for page in pdf_reader.pages:
            content = page.extract_text()
            if content:
                text += content
        return text.strip() if text else "PDF was empty or unreadable."
    except Exception as e:
        print(f"PDF Error: {e}")
        return "Error reading PDF."

# --- AUTH & SESSION ROUTES ---

@app.route('/')
def auth_page():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

@app.route('/set_session', methods=['POST'])
def set_session():
    data = request.json
    session.permanent = True
    session['user_id'] = data.get('uid')
    session['role'] = data.get('role') # Crucial for dashboard logic
    session['user_name'] = data.get('displayName') or "User"
    return jsonify({"status": "success"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth_page'))

@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('auth_page'))
    return render_template('index.html', user_name=session.get('user_name', 'User'))

# --- UPDATED INTERVIEW LOGIC ---

# Inside main.py - update the /generate route prompt
@app.route('/generate', methods=['POST'])
def generate_questions():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        job_role = request.form.get('job_role', 'Software Developer')
        difficulty = request.form.get('difficulty', 'Entry Level')
        num_questions = request.form.get('num_questions', '5')
        job_desc = request.form.get('job_description', '')
        q_type = request.form.get('q_type', 'technical')

        category_instructions = {
            "technical": "Focus on coding logic and CS fundamentals.",
            "behavioral": "Focus on past experiences using the STAR method.",
            "situational": "Focus on hypothetical problem-solving.",
            "system_design": "Focus on architecture and scalability."
        }

        resume_file = request.files.get('resume')
        resume_text = extract_text_from_pdf(resume_file)

        # UPDATED PROMPT: Requesting Questions AND Answers
        prompt = (
            f"You are a Senior Interviewer. Generate {num_questions} {q_type} questions "
            f"for a {difficulty} {job_role}. Context: JD({job_desc}), Resume({resume_text}). "
            f"For EACH question, provide a detailed 'Ideal Answer' that a top candidate would give. "
            f"Format like this:\n"
            f"1. [Question Text]\n"
            f"**Ideal Answer:** [Detailed Answer Text]\n\n"
            f"Return the output in Markdown."
        )
        
        response = model.generate_content(prompt)
        return jsonify({"questions": response.text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/evaluate', methods=['POST'])
def evaluate():
    if not session.get('user_id'):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json.get('data', [])
    if not data:
        return jsonify({"error": "No interview data"}), 400

    transcript = "\n".join([f"Q: {i['question']}\nA: {i['answer']}" for i in data])

    # Structured prompt to support the Performance Dashboard
    # Inside evaluation_prompt in main.py
    evaluation_prompt = f"""
    Analyze this interview transcript: {transcript}
    Return ONLY a JSON object:
    {{
      "scores": {{
        "tech": 0-10,
       "comm": 0-10,
    "conf": 0-10
  }},
  "report": "### \\n* Strength points \\n### \\n* Improvement points"
}}
"""
    
    try:
        response = model.generate_content(evaluation_prompt)
        # Clean JSON from markdown markers
        json_text = response.text.strip().removeprefix('```json').removesuffix('```').strip()
        return jsonify(json.loads(json_text))
    except Exception as e:
        print(f"Evaluation Error: {e}")
        return jsonify({"error": "Evaluation failed."}), 500

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)