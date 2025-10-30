from flask import Flask, render_template, request, jsonify
import os
import time
import threading
import requests
import config
import sqlite3
import datetime
from urllib.parse import urlparse
from google import genai
from google.genai import types
import json
import hashlib

# --- Import DSA components ---
from dsa import MerkleTree, job_queue, seen_hashes 

# --- Gemini Client Initialization ---
GEMINI_CLIENT = None
try:
    GEMINI_CLIENT = genai.Client(api_key=config.GEMINI_API_KEY)
except Exception as e:
    print(f"[ERROR] Failed to initialize Gemini Client: {e}")
# ------------------------------------

# --- Setup ---
TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_url_path='', static_folder=STATIC_DIR)

# --- Database & Config ---
DB_FILE = 'veri.db'
FALSE_RATINGS = ['false', 'pants on fire', 'mostly false', 'scam', 'fake', 'misleading']
TRUE_RATINGS = ['true', 'mostly true', 'correct attribution']

def init_database():
    """Initializes the SQLite database and table."""
    print("Initializing database...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analysis_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, query_text TEXT NOT NULL,
        text_hash TEXT NOT NULL UNIQUE, api_result_found BOOLEAN, rating TEXT,
        publisher TEXT, merkle_root_hash TEXT, original_url TEXT NULL, domain TEXT NULL,
        gemini_flag BOOLEAN NULL, gemini_confidence INTEGER NULL, gemini_reasoning TEXT NULL,
        final_verdict TEXT NULL
    )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

# --- Central Decision Logic ---
def determine_final_verdict(fc_rating, g_flag, g_conf):
    """Assigns a score to combine Fact Check and Gemini results."""
    score = 0
    fc_rating_lower = fc_rating.lower()
    
    if fc_rating_lower in TRUE_RATINGS: score += 10 
    elif fc_rating_lower in FALSE_RATINGS: score -= 15
    
    if g_flag is True and g_conf is not None and g_conf > 50:
        score -= (g_conf / 10) 
    elif g_flag is False and g_conf is not None and g_conf > 50:
        score += (g_conf / 20) 

    if score >= 5:
        return "VERIFIED_TRUE", "Strong agreement from human fact-checkers and/or high AI confidence."
    elif score <= -5:
        return "FLAGGED_FALSE", "Strong evidence from human fact-checkers and/or AI suggests misinformation."
    else:
        return "INCONCLUSIVE", "Mixed signals, low confidence, or no direct fact-check found."

# --- API Functions ---
def call_fact_check_api(query_text):
    """Calls Google Fact Check API."""
    API_KEY = config.GOOGLE_API_KEY; url = f"https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {'query': query_text, 'key': API_KEY, 'languageCode': 'en-US'}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json(); claims = data.get('claims')
            if claims:
                fc = claims[0]; pub = fc.get('claimReview', [{}])[0].get('publisher', {}).get('name', 'N/A')
                rate = fc.get('claimReview', [{}])[0].get('textualRating', 'N/A')
                return {"status": "success", "found": True, "publisher": pub, "rating": rate}
            else: return {"status": "success", "found": False, "publisher": "N/A", "rating": "Not Found"}
        elif response.status_code == 429: print(f"[FCAPI Err 429]: Rate limit hit. {response.text}"); return {"status": "error", "message": "Fact Check API quota exceeded."}
        else: print(f"[FCAPI Err {response.status_code}]: {response.text}"); return {"status": "error", "message": "Fact Check API failed."}
    except requests.exceptions.Timeout: return {"status": "error", "message": "Fact Check API timed out."}
    except Exception as e: print(f"[FCAPI Exc] {e}"); return {"status": "error", "message": "Fact Check API connection failed."}

def get_title_from_url(article_url):
    """Uses News API to get article title."""
    API_KEY = config.NEWS_API_KEY; url = f"https://newsapi.org/v2/everything"
    params = {'q': article_url, 'apiKey': API_KEY, 'searchIn': 'title,description,content', 'pageSize': 1}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json(); articles = data.get('articles')
            if articles: title = articles[0]['title']; return {"status": "success", "title": title}
            else: return {"status": "not_found", "message": "Article not found via News API."}
        elif response.status_code == 429: print(f"[NewsAPI Err 429]: Rate limit hit. {response.text}"); return {"status": "error", "message": "News API rate limit exceeded."}
        else: print(f"[NewsAPI Err {response.status_code}]: {response.text}"); return {"status": "error", "message": "News API failed."}
    except requests.exceptions.Timeout: return {"status": "error", "message": "News API timed out."}
    except Exception as e: return {"status": "error", "message": "News API connection failed."}

def check_credibility_with_gemini(text_to_analyze):
    """Uses Gemini to analyze text and provide a structured JSON response."""
    if GEMINI_CLIENT is None: return {"status": "error", "message": "Gemini client not initialized."}
    output_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={"misinformation_flag": types.Schema(type=types.Type.BOOLEAN), "simulated_confidence_score": types.Schema(type=types.Type.INTEGER), "reasoning_snippet": types.Schema(type=types.Type.STRING)},
        required=["misinformation_flag", "simulated_confidence_score", "reasoning_snippet"])
    prompt = (f"Analyze the following content for factual errors... Respond ONLY with the requested JSON object. Content to analyze: \"{text_to_analyze}\"")
    try:
        response = GEMINI_CLIENT.models.generate_content(
            model='gemini-2.5-flash', contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=output_schema, temperature=0.0)
        )
        gemini_result = json.loads(response.text)
        return {"status": "success", "data": gemini_result}
    except Exception as e: return {"status": "error", "message": f"Gemini analysis failed: {e}"}

# --- Background Worker Thread ---
def analysis_worker():
    """Processes jobs from queue, calls APIs, uses MerkleTree, saves."""
    print("Worker thread started. Waiting for jobs...")
    while True:
        if job_queue:
            job = job_queue.popleft(); text_to_analyze = job['text']; text_hash = job['hash']
            original_url = job.get('original_url'); domain = None
            if original_url:
                try:
                    parsed_uri = urlparse(original_url); domain = parsed_uri.netloc
                    if domain.startswith('www.'): domain = domain[4:]
                except Exception: pass

            print(f"\n--- [Worker] ---"); print(f"Got job (Hash: {text_hash[:8]}...): '{text_to_analyze}'")

            # 1. Fact Check API Call
            api_result_fc = call_fact_check_api(text_to_analyze)
            fc_rating = api_result_fc.get('rating', 'API Error')
            if api_result_fc.get('status') != 'success': api_result_fc = {"found": False, "publisher": "N/A", "rating": "API Error"}

            # 2. Gemini API Call
            api_result_gemini = check_credibility_with_gemini(text_to_analyze)
            gemini_data = api_result_gemini.get('data', {})
            g_flag = gemini_data.get('misinformation_flag'); g_conf = gemini_data.get('simulated_confidence_score'); g_reason = gemini_data.get('reasoning_snippet')
            print(f"Gemini Result: Flag={g_flag}, Conf={g_conf}")
            
            # 3. DETERMINE FINAL VERDICT
            final_verdict, final_reasoning = determine_final_verdict(fc_rating, g_flag, g_conf)
            print(f"FINAL VERDICT: {final_verdict}")
            
            # 4. Save to DB (FIXED INDENTATION AND ERROR HANDLING)
            conn = None
            try:
                conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
                timestamp = datetime.datetime.now().isoformat()
                
                # Merkle Tree data
                data_to_verify = [timestamp, text_to_analyze, fc_rating, api_result_fc['publisher'], str(g_conf)]
                tree = MerkleTree(data_to_verify); merkle_hash = tree.root_hash

                cursor.execute('''INSERT INTO analysis_results
                    (timestamp, query_text, text_hash, api_result_found, rating, publisher, merkle_root_hash, original_url, domain,
                     gemini_flag, gemini_confidence, gemini_reasoning, final_verdict)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (timestamp, text_to_analyze, text_hash, api_result_fc['found'], fc_rating,
                     api_result_fc['publisher'], merkle_hash, original_url, domain,
                     g_flag, g_conf, g_reason, final_verdict))
                conn.commit()
                print(f"[DB] Saved. Final Verdict: {final_verdict}. Hash: {merkle_hash[:8]}...")
            except sqlite3.IntegrityError: 
                print(f"[DB Error] Hash {text_hash[:8]}... exists.") 
                if conn: conn.rollback()
            except Exception as e: 
                print(f"[DB Error] Save failed: {e}")
            finally:
                if conn: conn.close()

            print(f"Finished: '{text_to_analyze}'"); print(f"--- [Worker] ---\n")
        else:
            time.sleep(1)

# --- Flask Routes ---
@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Receives text/URL, validates, checks duplicates, queues."""
    data = request.json; article_text = data.get('article_text'); article_url = data.get('article_url'); text_to_analyze = None

    if article_url:
        print(f"\nReceived URL: {article_url}"); title_result = get_title_from_url(article_url)
        if title_result['status'] == 'success': text_to_analyze = title_result['title']
        else: return jsonify({"status": "error", "message": title_result['message']}), 400
    elif article_text: text_to_analyze = article_text; print(f"\nReceived Text: {text_to_analyze[:60]}...")
    else: return jsonify({"status": "error", "message": "No text or URL"}), 400

    if not text_to_analyze: return jsonify({"status": "error", "message": "Analysis text missing"}), 500

    import hashlib
    text_hash = hashlib.sha256(text_to_analyze.encode('utf-8')).hexdigest()

    if text_hash in seen_hashes:
        print(f"Duplicate (Hash: {text_hash[:8]}...). Ignoring.")
        return jsonify({"status": "duplicate", "message": "Already analyzed.", "analyzed_text": text_to_analyze})

    print(f"New job (Hash: {text_hash[:8]}...). Queuing.")
    seen_hashes.add(text_hash)
    job_payload = {'text': text_to_analyze, 'hash': text_hash}
    if article_url: job_payload['original_url'] = article_url
    job_queue.append(job_payload)

    return jsonify({"status": "queued", "message": "Analysis queued.", "analyzed_text": text_to_analyze})

@app.route('/api/stats')
def get_stats():
    """Gets aggregate stats (uses final_verdict column)."""
    try:
        conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        tq = cursor.execute("SELECT COUNT(*) AS total FROM analysis_results").fetchone(); total = tq['total'] if tq else 0
        
        # Count based on FINAL VERDICT column
        false_c_q = cursor.execute("SELECT COUNT(*) AS total FROM analysis_results WHERE final_verdict = 'FLAGGED_FALSE'").fetchone()
        false_c = false_c_q['total'] if false_c_q else 0
        
        true_c_q = cursor.execute("SELECT COUNT(*) AS total FROM analysis_results WHERE final_verdict = 'VERIFIED_TRUE'").fetchone()
        true_c = true_c_q['total'] if true_c_q else 0
        
        conn.close(); return jsonify({"total_analyzed": total, "verified_true": true_c, "flagged_false": false_c})
    except Exception as e: print(f"[Stats Error] {e}"); return jsonify({"error": str(e)}), 500

@app.route('/api/history')
def get_history():
    """Gets all results for history page."""
    try:
        conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        results = cursor.execute("SELECT * FROM analysis_results ORDER BY id DESC").fetchall()
        conn.close(); history_list = [dict(row) for row in results]; return jsonify(history_list)
    except Exception as e: print(f"[History Error] {e}"); return jsonify({"error": str(e)}), 500

@app.route('/api/latest_result')
def get_latest_result():
    """Gets the most recent result."""
    try:
        conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        latest = cursor.execute("SELECT * FROM analysis_results ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if latest: return jsonify(dict(latest))
        else: return jsonify({"status": "empty", "message": "No results yet."})
    except Exception as e: print(f"[Latest Error] {e}"); return jsonify({"error": str(e)}), 500

# --- Start Server ---
if __name__ == '__main__':
    init_database()
    try: # Load existing hashes on startup
        conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
        hashes_in_db = cursor.execute("SELECT text_hash FROM analysis_results").fetchall()
        seen_hashes.update([row[0] for row in hashes_in_db])
        conn.close()
        print(f"Loaded {len(seen_hashes)} existing hashes from DB.")
    except Exception as e: print(f"[Startup Error] DB hash load failed: {e}")

    worker_thread = threading.Thread(target=analysis_worker, daemon=True)
    worker_thread.start()
    print("\nStarting Flask server on port 5001...")
    app.run(debug=True, port=5001, use_reloader=False)