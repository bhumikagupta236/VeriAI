from flask import Flask, render_template, request, jsonify
import os
import time
import threading
import requests
# Robust config import: fall back to env vars if config.py missing
try:
    import config
except Exception:
    class _Cfg:
        GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
        GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
        NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
        GNEWS_API_KEY = os.environ.get('GNEWS_API_KEY')
    config = _Cfg()
import sqlite3
import datetime
from urllib.parse import urlparse
try:
    from google import genai
    from google.genai import types
except Exception as e:
    genai = None
    types = None
    print(f"[WARN] Gemini SDK not available: {e}")
import json
import hashlib
import re

# --- Import DSA components ---
from dsa import MerkleTree, job_queue, seen_hashes 

# --- Gemini Client Initialization ---
GEMINI_CLIENT = None
try:
    if 'genai' in globals() and genai is not None:
        GEMINI_CLIENT = genai.Client(api_key=getattr(config, 'GEMINI_API_KEY', None))
except Exception as e:
    print(f"[ERROR] Failed to initialize Gemini Client: {e}")
# ------------------------------------

# --- Setup ---
TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_url_path='', static_folder=STATIC_DIR)

# --- Database & Config ---
DB_FILE = os.path.join(os.path.dirname(__file__), 'vri.db')
FALSE_RATINGS = ['false', 'pants on fire', 'mostly false', 'scam', 'fake', 'incorrect', 'not true', 'debunked']
TRUE_RATINGS = ['true', 'mostly true', 'correct attribution', 'accurate', 'correct', 'verified']

# Trusted domains bias: reputable news sources reduce false positives from AI-only verdicts
TRUSTED_DOMAINS = {
    'indianexpress.com', 'bbc.com', 'nytimes.com', 'cnn.com', 'reuters.com', 'apnews.com',
    'theguardian.com', 'washingtonpost.com', 'wsj.com', 'aljazeera.com', 'npr.org',
    'latimes.com', 'hindustantimes.com', 'thehindu.com', 'timesofindia.indiatimes.com',
    'financialexpress.com', 'business-standard.com'
}

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
def determine_final_verdict(fc_rating, g_flag, g_conf, domain=None):
    """Fusion of Fact-Check, AI signals, and domain trust to avoid false positives on reputable sites."""
    fc = (fc_rating or '').lower()
    dom = (domain or '').lower()
    # If human fact-check exists, trust it first.
    if fc in TRUE_RATINGS:
        return "VERIFIED_TRUE", "Human fact-check indicates it is true."
    if fc in FALSE_RATINGS:
        return "FLAGGED_FALSE", "Human fact-check indicates it is false."
    # No clear human rating: apply domain-aware AI gating
    if g_conf is not None and g_flag is not None:
        try:
            c = int(g_conf)
        except Exception:
            c = 0
        is_trusted = any(dom.endswith(td) for td in TRUSTED_DOMAINS)
        if is_trusted:
            # Do not flag trusted domains as false purely via AI; require human rating.
            if g_flag is False and c >= 60:
                return "VERIFIED_TRUE", "Trusted source and AI suggests credibility."
            return "INCONCLUSIVE", "Trusted source with no corroborating fact-check."
        else:
            if g_flag is True and c >= 85:
                return "FLAGGED_FALSE", "AI strongly suggests misinformation."
            if g_flag is False and c >= 80:
                return "VERIFIED_TRUE", "AI strongly suggests it is credible."
    return "INCONCLUSIVE", "Insufficient agreement to decide."

# --- API Functions ---
def _normalize_rating(text):
    t = (text or '').strip().lower()
    # Map common ratings to simple buckets
    true_words = ['true', 'mostly true', 'correct attribution', 'accurate', 'correct', 'verified']
    false_words = ['false', 'mostly false', 'pants on fire', 'scam', 'fake', 'incorrect', 'not true', 'debunked']
    mixed_words = ['half true', 'mixture', 'partly true', 'needs context', 'misleading', 'unproven', 'unsupported']
    if any(w in t for w in false_words):
        return 'false'
    if any(w in t for w in true_words):
        return 'true'
    if any(w in t for w in mixed_words):
        return 'mixed'
    return 'unknown'

def _tokenize(s):
    tokens = re.findall(r"[a-z0-9]+", (s or '').lower())
    stop = {"the","a","an","is","are","to","of","and","or","in","on","for","with"}
    tokens = [t for t in tokens if len(t) > 2 and t not in stop]
    return set(tokens)

def _similar_enough(a, b, threshold=0.65):
    A = _tokenize(a); B = _tokenize(b)
    if not A or not B:
        return False
    inter = len(A & B); union = len(A | B)
    if inter < 2:
        return False
    ratio = inter / union if union else 0.0
    return ratio >= threshold

# --- URL helpers ---
_URL_REGEX = re.compile(r"^(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?::\d+)?(?:/[\S]*)?$", re.IGNORECASE)

def looks_like_url(s: str) -> bool:
    s = (s or '').strip()
    if not s or len(s) > 2048:
        return False
    return bool(_URL_REGEX.match(s))

def normalize_url(u: str) -> str:
    u = (u or '').strip()
    if not u:
        return u
    parsed = urlparse(u)
    if not parsed.scheme:
        u = 'https://' + u
    return u

def call_fact_check_api(query_text, is_url_content=False):
    """Calls Google Fact Check API and aggregates ratings across top similar claims."""
    API_KEY = config.GOOGLE_API_KEY; url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    
    # For URL content, extract key claims/title for better API matching
    search_query = query_text
    if is_url_content and '|' in query_text:
        # Use just the title (first part before |) for fact check API
        search_query = query_text.split('|')[0].strip()
        print(f"[FCAPI] Using title for search: {search_query[:80]}...")
    
    params = {'query': search_query, 'key': API_KEY, 'languageCode': 'en-US', 'pageSize': 10}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json(); claims = data.get('claims') or []
            if not claims:
                return {"status": "success", "found": False, "publisher": "N/A", "rating": "Not Found"}
            # Filter to claims similar to our query/title to reduce mismatches
            selected_reviews = []
            for c in claims:
                claim_text = c.get('text') or ''
                # For similarity check, use the search_query (which is the title for URL content)
                sim_ok = _similar_enough(search_query, claim_text, threshold=0.75) if is_url_content else _similar_enough(search_query, claim_text, threshold=0.65)
                if not sim_ok:
                    continue
                for cr in (c.get('claimReview') or []):
                    r = (cr.get('textualRating') or '').strip()
                    p = cr.get('publisher', {}).get('name', 'N/A')
                    if r:
                        selected_reviews.append((r, p))
            if not selected_reviews:
                return {"status": "success", "found": False, "publisher": "N/A", "rating": "Not Found"}
            # Tally normalized buckets
            true_c = 0; false_c = 0; mixed_c = 0; first_pub = 'N/A'; first_rating = None
            for r, p in selected_reviews:
                cat = _normalize_rating(r)
                if first_rating is None:
                    first_rating = r; first_pub = p
                if cat == 'true': true_c += 1
                elif cat == 'false': false_c += 1
                elif cat == 'mixed': mixed_c += 1
            if false_c > true_c and false_c >= 1:
                return {"status": "success", "found": True, "publisher": first_pub, "rating": first_rating if _normalize_rating(first_rating)=='false' else 'False'}
            if true_c > false_c and true_c >= 1:
                return {"status": "success", "found": True, "publisher": first_pub, "rating": first_rating if _normalize_rating(first_rating)=='true' else 'True'}
            # Otherwise, inconclusive
            return {"status": "success", "found": False, "publisher": first_pub, "rating": "Not Found"}
        elif response.status_code == 429:
            print(f"[FCAPI Err 429]: Rate limit hit. {response.text}")
            return {"status": "error", "message": "Fact Check API quota exceeded."}
        else:
            print(f"[FCAPI Err {response.status_code}]: {response.text}")
            return {"status": "error", "message": "Fact Check API failed."}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Fact Check API timed out."}
    except Exception as e:
        print(f"[FCAPI Exc] {e}")
        return {"status": "error", "message": "Fact Check API connection failed."}

def extract_article_content(article_url):
    """Extracts article content (title + description/body) from a news URL.
    Returns a comprehensive text for better fact-checking.
    """
    try:
        r = requests.get(article_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        if r.status_code == 200:
            html = r.text or ''
            
            # Extract title
            title = None
            # Try OpenGraph title first
            m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if m:
                title = m.group(1).strip()
            else:
                # Fallback: <title> tag
                m2 = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                if m2:
                    title = m2.group(1).strip()
            
            # Extract description/summary
            description = None
            # Try OpenGraph description
            m_desc = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if m_desc:
                description = m_desc.group(1).strip()
            else:
                # Try meta description
                m_desc2 = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if m_desc2:
                    description = m_desc2.group(1).strip()
            
            # Extract article body (common patterns)
            article_body = None
            # Try <article> tag
            article_match = re.search(r'<article[^>]*>(.*?)</article>', html, re.IGNORECASE | re.DOTALL)
            if article_match:
                article_html = article_match.group(1)
                # Remove script and style tags
                article_html = re.sub(r'<script[^>]*>.*?</script>', '', article_html, flags=re.IGNORECASE | re.DOTALL)
                article_html = re.sub(r'<style[^>]*>.*?</style>', '', article_html, flags=re.IGNORECASE | re.DOTALL)
                # Extract text from paragraphs
                paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', article_html, re.IGNORECASE | re.DOTALL)
                if paragraphs:
                    # Clean HTML tags and get first few paragraphs
                    clean_paras = []
                    for p in paragraphs[:5]:  # Limit to first 5 paragraphs
                        clean_p = re.sub(r'<[^>]+>', '', p).strip()
                        if len(clean_p) > 30:  # Only include substantial paragraphs
                            clean_paras.append(clean_p)
                    if clean_paras:
                        article_body = ' '.join(clean_paras)
            
            # Combine title, description, and body
            combined_text = []
            if title:
                combined_text.append(title)
            if description and description not in (title or ''):
                combined_text.append(description)
            if article_body:
                # Limit body to reasonable length (around 1000 chars)
                if len(article_body) > 1000:
                    article_body = article_body[:1000] + '...'
                combined_text.append(article_body)
            
            if combined_text:
                full_text = ' | '.join(combined_text)
                return {"status": "success", "content": full_text, "title": title}
    except Exception as e:
        print(f"[Article Extract] Direct fetch failed: {e}")
    
    # Fallback: Try GNews API
    try:
        GNEWS_KEY = getattr(config, 'GNEWS_API_KEY', None)
        if GNEWS_KEY:
            url = "https://gnews.io/api/v4/search"
            params = {'q': article_url, 'lang': 'en', 'max': 1, 'token': GNEWS_KEY}
            gr = requests.get(url, params=params, timeout=8)
            if gr.status_code == 200:
                gd = gr.json(); arts = gd.get('articles') or []
                if arts:
                    art = arts[0]
                    title = art.get('title', '')
                    desc = art.get('description', '')
                    content = art.get('content', '')
                    combined = ' | '.join([x for x in [title, desc, content] if x])
                    return {"status": "success", "content": combined, "title": title}
    except Exception as e:
        print(f"[GNews Fallback] Failed: {e}")
    
    # Fallback: Try NewsAPI
    try:
        API_KEY = getattr(config, 'NEWS_API_KEY', None)
        if API_KEY:
            url = "https://newsapi.org/v2/everything"
            params = {'q': article_url, 'apiKey': API_KEY, 'searchIn': 'title,description,content', 'pageSize': 1}
            response = requests.get(url, params=params, timeout=8)
            if response.status_code == 200:
                data = response.json(); articles = data.get('articles')
                if articles:
                    art = articles[0]
                    title = art.get('title', '')
                    desc = art.get('description', '')
                    content = art.get('content', '')
                    combined = ' | '.join([x for x in [title, desc, content] if x])
                    return {"status": "success", "content": combined, "title": title}
            elif response.status_code == 429:
                print(f"[NewsAPI Err 429]: Rate limit hit. {response.text}")
                return {"status": "error", "message": "News API rate limit exceeded."}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "News API timed out."}
    except Exception as e:
        print(f"[NewsAPI Fallback] Failed: {e}")
    
    return {"status": "not_found", "message": "Could not extract content from the URL."}

def check_credibility_with_gemini(text_to_analyze):
    """Uses Gemini to analyze text and provide a structured JSON response."""
    if GEMINI_CLIENT is None or types is None:
        return {"status": "error", "message": "Gemini client not initialized."}
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

            print(f"\n--- [Worker] ---"); print(f"Got job (Hash: {text_hash[:8]}...): '{text_to_analyze[:100]}...'")
            
            # Determine if this is URL content (contains the | separator)
            is_url_content = '|' in text_to_analyze and original_url is not None

            # 1. Fact Check API Call
            api_result_fc = call_fact_check_api(text_to_analyze, is_url_content=is_url_content)
            fc_rating = api_result_fc.get('rating', 'API Error')
            if api_result_fc.get('status') != 'success': api_result_fc = {"found": False, "publisher": "N/A", "rating": "API Error"}

            # 2. Gemini API Call
            api_result_gemini = check_credibility_with_gemini(text_to_analyze)
            gemini_data = api_result_gemini.get('data', {})
            g_flag = gemini_data.get('misinformation_flag'); g_conf = gemini_data.get('simulated_confidence_score'); g_reason = gemini_data.get('reasoning_snippet')
            print(f"Gemini Result: Flag={g_flag}, Conf={g_conf}")
            
# 3. DETERMINE FINAL VERDICT
            final_verdict, final_reasoning = determine_final_verdict(fc_rating, g_flag, g_conf, domain)
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
                print(f"[DB] Existing hash {text_hash[:8]}..., updating row instead.")
                try:
                    if conn is None:
                        conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    timestamp = datetime.datetime.now().isoformat()
                    cursor.execute('''UPDATE analysis_results SET
                        timestamp=?, api_result_found=?, rating=?, publisher=?, merkle_root_hash=?,
                        original_url=?, domain=?, gemini_flag=?, gemini_confidence=?, gemini_reasoning=?, final_verdict=?
                        WHERE text_hash=?''',
                        (timestamp, api_result_fc['found'], fc_rating, api_result_fc['publisher'], merkle_hash,
                         original_url, domain, g_flag, g_conf, g_reason, final_verdict, text_hash))
                    conn.commit()
                    print(f"[DB] Updated existing record. Final Verdict: {final_verdict}.")
                except Exception as e2:
                    if conn: conn.rollback()
                    print(f"[DB Error] Update failed: {e2}")
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
    data = request.json or {}
    raw_text = (data.get('article_text') or '').strip()
    raw_url = (data.get('article_url') or '').strip()

    text_to_analyze = None
    original_url = None

    # Prefer explicit URL field, else detect URLs pasted into the text field
    if raw_url:
        original_url = normalize_url(raw_url)
        print(f"\nReceived URL: {original_url}")
        content_result = extract_article_content(original_url)
        if content_result.get('status') == 'success':
            text_to_analyze = content_result['content']
            print(f"Extracted content ({len(text_to_analyze)} chars): {text_to_analyze[:100]}...")
        else:
            return jsonify({"status": "error", "message": content_result.get('message', 'Failed to extract URL content')}), 400
    elif raw_text:
        # If user pasted a URL into the text box, handle it as a URL automatically
        if looks_like_url(raw_text):
            original_url = normalize_url(raw_text)
            print(f"\nDetected URL in text field: {original_url}")
            content_result = extract_article_content(original_url)
            if content_result.get('status') == 'success':
                text_to_analyze = content_result['content']
                print(f"Extracted content ({len(text_to_analyze)} chars): {text_to_analyze[:100]}...")
            else:
                return jsonify({"status": "error", "message": content_result.get('message', 'Failed to extract URL content')}), 400
        else:
            text_to_analyze = raw_text
            print(f"\nReceived Text: {text_to_analyze[:60]}...")
    else:
        return jsonify({"status": "error", "message": "No text or URL"}), 400

    if not text_to_analyze: return jsonify({"status": "error", "message": "Analysis text missing"}), 500

    text_hash = hashlib.sha256(text_to_analyze.encode('utf-8')).hexdigest()

    if text_hash in seen_hashes:
        print(f"Duplicate (Hash: {text_hash[:8]}...). Re-analyzing.")
        # queue anyway to refresh the verdict with latest logic
        job_payload = {'text': text_to_analyze, 'hash': text_hash}
        if original_url:
            job_payload['original_url'] = original_url
        job_queue.append(job_payload)
        return jsonify({"status": "queued", "message": "Re-analysis queued.", "analyzed_text": text_to_analyze})

    print(f"New job (Hash: {text_hash[:8]}...). Queuing.")
    seen_hashes.add(text_hash)
    job_payload = {'text': text_to_analyze, 'hash': text_hash}
    if original_url:
        job_payload['original_url'] = original_url
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

@app.route('/api/delete_history/<int:item_id>', methods=['DELETE'])
def delete_history_item(item_id):
    """Deletes a specific analysis result by ID."""
    print(f"[Delete Request] Item ID: {item_id}")
    try:
        conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
        # Get the text_hash before deleting so we can remove it from seen_hashes
        result = cursor.execute("SELECT text_hash FROM analysis_results WHERE id = ?", (item_id,)).fetchone()
        if result:
            text_hash = result[0]
            print(f"[Delete] Found item with hash: {text_hash[:8]}...")
            cursor.execute("DELETE FROM analysis_results WHERE id = ?", (item_id,))
            conn.commit()
            # Remove from seen_hashes to allow re-analysis if needed
            try:
                seen_hashes.discard(text_hash)
                print(f"[Delete] Removed hash from seen_hashes")
            except Exception as e:
                print(f"[Delete] Warning: Could not remove from seen_hashes: {e}")
            conn.close()
            print(f"[Delete] Successfully deleted item {item_id}")
            return jsonify({"status": "success", "message": "Item deleted."})
        else:
            conn.close()
            print(f"[Delete] Item {item_id} not found in database")
            return jsonify({"status": "error", "message": "Item not found."}), 404
    except Exception as e:
        print(f"[Delete History Error] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    """Clears all saved analysis results and resets duplicate tracking."""
    try:
        conn = sqlite3.connect(DB_FILE); cursor = conn.cursor()
        cursor.execute("DELETE FROM analysis_results")
        conn.commit(); conn.close()
        # Reset in-memory hashes so re-analysis will enqueue
        try:
            seen_hashes.clear()
        except Exception:
            pass
        return jsonify({"status": "success", "message": "History cleared."})
    except Exception as e:
        print(f"[Clear History Error] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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