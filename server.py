from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import random
import json

load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

API_URL = os.getenv("API_URL", "https://api.nexadev.my.id/ai/chatgptpro?q=auto%20bahasa%20Malaysia")

# ============================================================
# CUSTOM GREETING — DETECT "hai" / "hello" / "hi"
# ============================================================
GREETING_KEYWORDS = ['hai', 'hello', 'hi', 'helo', 'hye', 'hey', 'halo', 'assalamualaikum', 'salam']

def is_greeting(text: str) -> bool:
    """Check if message is a greeting"""
    if not text or not isinstance(text, str):
        return False
    text_lower = text.lower().strip()
    # Check if text is exactly or starts with greeting
    for word in GREETING_KEYWORDS:
        if text_lower == word or text_lower.startswith(word + ' ') or text_lower.startswith(word + '!'):
            return True
    return False

def get_greeting_response(text: str) -> str:
    """Return custom greeting response"""
    # Check if it's a simple greeting
    text_lower = text.lower().strip()
    
    # List of custom responses
    responses = [
        "Saya dibuat oleh Fiqqzr7. Ada apa yang boleh saya bantu?",
        "Dibuat oleh Fiqqzr7! Ada soalan?",
        "Fiqqzr7 yang bina saya. Apa yang awak nak tahu?",
        "Saya ciptaan Fiqqzr7. Nak tanya apa-apa?",
        "Dibuat oleh Fiqqzr7. Saya sedia membantu!"
    ]
    
    # If it's just a simple greeting
    if text_lower in ['hai', 'hello', 'hi', 'helo', 'hye', 'hey', 'halo']:
        return random.choice(responses)
    
    # If it's "assalamualaikum" or "salam"
    if text_lower in ['assalamualaikum', 'salam']:
        return f"Waalaikumsalam! Saya dibuat oleh Fiqqzr7. Ada apa yang boleh saya bantu?"
    
    return None

# ============================================================
# SERVE INDEX
# ============================================================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# ============================================================
# LINK PREVIEW — FETCH OG DATA
# ============================================================
def fetch_og_data(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        og_title = soup.find('meta', property='og:title')
        og_description = soup.find('meta', property='og:description')
        og_image = soup.find('meta', property='og:image')
        og_site = soup.find('meta', property='og:site_name')
        
        title = og_title.get('content') if og_title else soup.title.string if soup.title else url
        
        return {
            'title': title.strip() if title else url,
            'description': og_description.get('content', '').strip() if og_description else '',
            'image': og_image.get('content', '') if og_image else '',
            'site': og_site.get('content', '') if og_site else urlparse(url).netloc
        }
    except Exception as e:
        print(f'OG fetch error: {e}')
        return None

# ============================================================
# ANTI-SLOP
# ============================================================
def is_slop_response(text):
    if not text or not isinstance(text, str):
        return True
    if len(text.strip()) < 3:
        return True
    if text.strip().lower() in ["ok", "yes", "no", "ya", "tidak", "hi", "hello", "hai"]:
        return True
    if re.search(r'(.)\1{10,}', text):
        return True
    return False

def clean_response(text):
    # Ensure text is string
    if not isinstance(text, str):
        text = str(text)
    
    # Remove extra brackets [ ] from API response
    text = re.sub(r'^\[|\]$', '', text)
    
    # Remove extra quotes
    text = re.sub(r'^"|"$', '', text)
    
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove emoji
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F700-\U0001F77F"
        u"\U0001F780-\U0001F7FF"
        u"\U0001F800-\U0001F8FF"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA00-\U0001FA6F"
        u"\U0001FA70-\U0001FAFF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)
    
    return text

# ============================================================
# EXTRACT REPLY FROM API — HANDLE ALL FORMATS
# ============================================================
def extract_reply(result):
    """Extract reply from API response (handles dict, list, string)"""
    
    # If result is a list
    if isinstance(result, list):
        if len(result) == 0:
            return None
        # Try to get first item if it's a string
        if isinstance(result[0], str):
            return result[0]
        # If first item is dict with message
        if isinstance(result[0], dict):
            return extract_reply(result[0])
        return str(result[0])
    
    # If result is a string
    if isinstance(result, str):
        return result
    
    # If result is a dict
    if isinstance(result, dict):
        # Check for error
        if result.get('status') == False:
            return None
        
        # Try common keys
        keys = ['result', 'response', 'data', 'message', 'reply', 'text', 'content', 'output', 'answer']
        for key in keys:
            if key in result:
                value = result[key]
                if isinstance(value, list):
                    if value and isinstance(value[0], str):
                        return value[0]
                    return str(value) if value else None
                if isinstance(value, str):
                    return value
                if isinstance(value, dict):
                    return extract_reply(value)
        
        # If no known key, try to find any string value
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 10:
                return value
            if isinstance(value, list) and value and isinstance(value[0], str):
                return value[0]
    
    # Fallback: convert to string
    return str(result) if result else None

# ============================================================
# API ROUTES
# ============================================================
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        messages = data.get('messages', [])
        
        if not messages:
            return jsonify({'error': 'No messages'}), 400
        
        user_message = messages[-1].get('content', '') if messages else ''
        
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
        
        # ─── CHECK FOR GREETING FIRST ─────────────────────────
        greeting_response = get_greeting_response(user_message)
        if greeting_response:
            return jsonify({'reply': greeting_response})
        
        # ─── CALL API ──────────────────────────────────────────
        response = requests.get(
            API_URL + user_message,
            timeout=30,
            headers={'User-Agent': 'FzAI/2.0'}
        )
        
        if response.status_code != 200:
            return jsonify({'error': f'API error: {response.status_code}'}), 500
        
        # ─── PARSE RESPONSE ────────────────────────────────────
        try:
            result = response.json()
        except json.JSONDecodeError:
            # If response is not JSON, use raw text
            reply = response.text
            reply = clean_response(reply)
            
            if is_slop_response(reply):
                fallbacks = [
                    "Maaf, saya kurang faham dengan soalan tu. Boleh ulang dengan lebih jelas?",
                    "Saya rasa soalan tu terlalu ringkas. Boleh bagi lebih detail?",
                    "Maaf, saya tak dapat proses permintaan tu. Cuba tanya dengan cara lain.",
                    "Saya tak pasti apa maksud awak. Boleh jelaskan?"
                ]
                reply = random.choice(fallbacks)
            
            return jsonify({'reply': reply})
        
        # ─── EXTRACT REPLY ─────────────────────────────────────
        reply = extract_reply(result)
        
        # If reply is None or empty
        if not reply or reply == 'None' or reply == 'null':
            return jsonify({'error': 'Empty response from API'}), 500
        
        # ─── CLEAN RESPONSE ────────────────────────────────────
        reply = clean_response(reply)
        
        # ─── ANTI-SLOP ─────────────────────────────────────────
        if is_slop_response(reply):
            fallbacks = [
                "Maaf, saya kurang faham dengan soalan tu. Boleh ulang dengan lebih jelas?",
                "Saya rasa soalan tu terlalu ringkas. Boleh bagi lebih detail?",
                "Maaf, saya tak dapat proses permintaan tu. Cuba tanya dengan cara lain.",
                "Saya tak pasti apa maksud awak. Boleh jelaskan?"
            ]
            reply = random.choice(fallbacks)
        
        return jsonify({'reply': reply})
        
    except requests.exceptions.Timeout:
        return jsonify({'error': 'API timeout'}), 500
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Connection error'}), 500
    except Exception as e:
        print(f'Error: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview', methods=['POST'])
def preview():
    try:
        data = request.get_json()
        url = data.get('url', '')
        
        if not url:
            return jsonify({'error': 'No URL'}), 400
        
        og_data = fetch_og_data(url)
        
        if og_data:
            return jsonify(og_data)
        
        return jsonify({
            'title': url,
            'description': '',
            'image': '',
            'site': urlparse(url).netloc
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
