# Simple API diagnostics without exposing secrets.
import os, json, requests

# Load config or env
try:
    import config
except Exception:
    class _Cfg:
        GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
        GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
        NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
        GNEWS_API_KEY = os.environ.get('GNEWS_API_KEY')
    config = _Cfg()


def test_fact_check():
    key = getattr(config, 'GOOGLE_API_KEY', None)
    if not key:
        return {"configured": False, "ok": False, "reason": "Missing GOOGLE_API_KEY"}
    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    try:
        r = requests.get(url, params={"query": "earth is round", "key": key, "languageCode": "en-US", "pageSize": 1}, timeout=8)
        ok = (r.status_code == 200)
        payload = {}
        try:
            payload = r.json()
        except Exception:
            payload = {"text": r.text[:200]}
        return {"configured": True, "ok": ok, "status_code": r.status_code, "sample": payload}
    except Exception as e:
        return {"configured": True, "ok": False, "error": str(e)}


def test_newsapi():
    key = getattr(config, 'NEWS_API_KEY', None)
    if not key:
        return {"configured": False, "ok": False, "reason": "Missing NEWS_API_KEY"}
    url = "https://newsapi.org/v2/everything"
    try:
        r = requests.get(url, params={"q": "OpenAI", "apiKey": key, "pageSize": 1}, timeout=8)
        ok = (r.status_code == 200)
        payload = {}
        try:
            payload = r.json()
        except Exception:
            payload = {"text": r.text[:200]}
        return {"configured": True, "ok": ok, "status_code": r.status_code, "sample": payload}
    except Exception as e:
        return {"configured": True, "ok": False, "error": str(e)}


def test_gnews():
    key = getattr(config, 'GNEWS_API_KEY', None)
    if not key:
        return {"configured": False, "ok": False, "reason": "Missing GNEWS_API_KEY"}
    url = "https://gnews.io/api/v4/search"
    try:
        r = requests.get(url, params={"q": "OpenAI", "lang": "en", "max": 1, "token": key}, timeout=8)
        ok = (r.status_code == 200)
        payload = {}
        try:
            payload = r.json()
        except Exception:
            payload = {"text": r.text[:200]}
        return {"configured": True, "ok": ok, "status_code": r.status_code, "sample": payload}
    except Exception as e:
        return {"configured": True, "ok": False, "error": str(e)}


def test_gemini():
    try:
        from google import genai
        from google.genai import types
    except Exception as e:
        return {"configured": False, "ok": False, "reason": f"Gemini SDK not installed: {e}"}
    key = getattr(config, 'GEMINI_API_KEY', None)
    if not key:
        return {"configured": False, "ok": False, "reason": "Missing GEMINI_API_KEY"}
    try:
        client = genai.Client(api_key=key)
        # Minimal JSON response
        schema = types.Schema(
            type=types.Type.OBJECT,
            properties={"ok": types.Schema(type=types.Type.BOOLEAN)},
            required=["ok"],
        )
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents='Respond ONLY with {"ok": true}',
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=0.0)
        )
        sample = {}
        try:
            sample = resp.text
        except Exception:
            sample = str(resp)
        return {"configured": True, "ok": True, "sample": sample}
    except Exception as e:
        return {"configured": True, "ok": False, "error": str(e)}


if __name__ == "__main__":
    results = {
        "google_fact_check": test_fact_check(),
        "newsapi": test_newsapi(),
        "gnews": test_gnews(),
        "gemini": test_gemini(),
    }
    print(json.dumps(results, indent=2))
