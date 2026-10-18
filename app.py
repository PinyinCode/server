# -*- coding: utf-8 -*-
"""
API cham diem cau tieng Trung + Vocab Analysis + OTP + Delete User.
Gop tu:
  - app.py v3.2  (cham diem)
  - vocab_api.py v1.6  (phan tich tu vung / flashcard)
  - app.py mo rong  (OTP qua Gmail OAuth2 + xoa user Firebase)

Render Free toi uu. Chay: python app.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pypinyin import pinyin, Style

import re
import os
import sys
import json
import random
import base64
import threading
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)


# ==========================================================
# PHAN 1: FIREBASE + MONGODB + GOOGLE OAUTH2 SETUP
# ==========================================================

# --- GOOGLE GMAIL OAUTH2 ---
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- FIREBASE ---
import firebase_admin
from firebase_admin import credentials, auth, firestore

firebase_json_str = os.environ.get("FIREBASE_CREDENTIALS_JSON")
if firebase_json_str:
    try:
        cred_dict = json.loads(firebase_json_str)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        print("[API] Firebase init OK (env)")
    except Exception as e:
        print("[API] Firebase init failed (env): " + str(e))
else:
    if os.path.exists("serviceAccountKey.json"):
        try:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            print("[API] Firebase init OK (file)")
        except Exception as e:
            print("[API] Firebase init failed (file): " + str(e))

# --- MONGODB (OTP) ---
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGODB_URI")
mongo_client = None
db_mongo = None
otp_collection = None
if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db_mongo = mongo_client["test"]
        otp_collection = db_mongo["otpcodes"]
        print("[API] MongoDB init OK")
    except Exception as e:
        print("[API] MongoDB init failed: " + str(e))

# Rate-limit OTP
last_sent_map = {}
OTP_COOLDOWN_SECONDS = 60


# ==========================================================
# PHAN 2: VOCAB ANALYSIS SETUP (tu vocab_api.py v1.6)
# ==========================================================

HAS_VOCAB = False
try:
    from vocab_data.radical_analyzer import (
        _split_components, get_radical_for_word
    )
    from vocab_data.mnemonic_generator import generate_mnemonic
    HAS_VOCAB = True
    print("[VocabAPI] vocab_data loaded OK")
except Exception as e:
    print("[VocabAPI] vocab_data load failed: " + str(e))


# ---- AI MNEMONICS ----
_AI_MNEMONICS = {}
_AI_MNEMONICS_INDEX = {}
_AI_MNEMONICS_PATH = None
_AI_MNEMONICS_MTIME = 0
_AI_MNEMONICS_LOADED = False


def _find_ai_mnemonics_file():
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    candidates = [
        os.path.join(here, "data", "ai_mnemonics.json"),
        os.path.join(parent, "data", "ai_mnemonics.json"),
        os.path.join(os.getcwd(), "data", "ai_mnemonics.json"),
        "data/ai_mnemonics.json",
        os.path.join(here, "ai_mnemonics.json"),
        "ai_mnemonics.json",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _build_ai_index(data):
    idx = {}
    for k, v in data.items():
        parts = k.split("|")
        if len(parts) != 3:
            continue
        zh = parts[2].strip()
        if not zh:
            continue
        if zh not in idx:
            idx[zh] = v
    return idx


def _do_load_ai_mnemonics():
    global _AI_MNEMONICS, _AI_MNEMONICS_INDEX
    global _AI_MNEMONICS_PATH, _AI_MNEMONICS_MTIME, _AI_MNEMONICS_LOADED

    path = _find_ai_mnemonics_file()
    if not path:
        _AI_MNEMONICS = {}
        _AI_MNEMONICS_INDEX = {}
        _AI_MNEMONICS_PATH = None
        _AI_MNEMONICS_MTIME = 0
        _AI_MNEMONICS_LOADED = True
        print("[VocabAPI] [INFO] Khong co ai_mnemonics.json")
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False

        _AI_MNEMONICS = data
        _AI_MNEMONICS_INDEX = _build_ai_index(data)
        _AI_MNEMONICS_PATH = path
        _AI_MNEMONICS_MTIME = os.path.getmtime(path)
        _AI_MNEMONICS_LOADED = True

        print("[VocabAPI] [OK] Load " + str(len(data)) + " meo nho AI")
        print("[VocabAPI] [OK] Index: " + str(len(_AI_MNEMONICS_INDEX)) + " chu")
        return True
    except Exception as e:
        print("[VocabAPI] [WARN] Loi doc ai_mnemonics.json: " + str(e))
        return False


def _check_ai_mnemonics_fresh():
    if not _AI_MNEMONICS_LOADED:
        _do_load_ai_mnemonics()
        return
    path = _AI_MNEMONICS_PATH
    if not path:
        new_path = _find_ai_mnemonics_file()
        if new_path:
            _do_load_ai_mnemonics()
        return
    if not os.path.exists(path):
        _do_load_ai_mnemonics()
        return
    try:
        current_mtime = os.path.getmtime(path)
        if current_mtime > _AI_MNEMONICS_MTIME:
            _do_load_ai_mnemonics()
    except Exception:
        pass


def get_ai_mnemonic(char):
    _check_ai_mnemonics_fresh()
    if not _AI_MNEMONICS_INDEX:
        return ""
    char = str(char or "").strip()
    if not char:
        return ""
    return _AI_MNEMONICS_INDEX.get(char, "")


# ---- VOCAB MEANINGS ----
_VOCAB_MEANINGS = {}
_VOCAB_MEANINGS_PATH = None
_VOCAB_MEANINGS_MTIME = 0


def _find_vocab_meanings_file():
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    candidates = [
        os.path.join(here, "data", "vocab_meanings.json"),
        os.path.join(here, "vocab_data", "vocab_meanings.json"),
        os.path.join(parent, "data", "vocab_meanings.json"),
        "data/vocab_meanings.json",
        "vocab_data/vocab_meanings.json",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _do_load_vocab_meanings():
    global _VOCAB_MEANINGS, _VOCAB_MEANINGS_PATH, _VOCAB_MEANINGS_MTIME
    path = _find_vocab_meanings_file()
    if not path:
        _VOCAB_MEANINGS = {}
        _VOCAB_MEANINGS_PATH = None
        _VOCAB_MEANINGS_MTIME = 0
        print("[VocabAPI] [INFO] Khong co vocab_meanings.json")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _VOCAB_MEANINGS = data
            _VOCAB_MEANINGS_PATH = path
            _VOCAB_MEANINGS_MTIME = os.path.getmtime(path)
            print("[VocabAPI] [OK] Load " + str(len(data)) + " nghia tu")
            return True
    except Exception as e:
        print("[VocabAPI] [WARN] Loi doc vocab_meanings.json: " + str(e))
    return False


def get_meaning(char):
    if not char:
        return ""
    return _VOCAB_MEANINGS.get(char, "")


def _check_vocab_meanings_fresh():
    path = _VOCAB_MEANINGS_PATH
    if not path:
        new_path = _find_vocab_meanings_file()
        if new_path:
            _do_load_vocab_meanings()
        return
    if not os.path.exists(path):
        _do_load_vocab_meanings()
        return
    try:
        if os.path.getmtime(path) > _VOCAB_MEANINGS_MTIME:
            _do_load_vocab_meanings()
    except Exception:
        pass


# ---- SIMILAR CHARS ----
_SIMILAR_CHARS = {}
_SIMILAR_CHARS_LOADED = False


def _do_load_similar_chars():
    global _SIMILAR_CHARS, _SIMILAR_CHARS_LOADED
    if _SIMILAR_CHARS_LOADED:
        return

    here = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(here, "vocab_data")
    if not os.path.isdir(folder):
        _SIMILAR_CHARS_LOADED = True
        return

    total = 0
    for fname in sorted(os.listdir(folder)):
        if fname.startswith("similar_chars") and fname.endswith(".json"):
            path = os.path.join(folder, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    _SIMILAR_CHARS.update(data)
                    total += len(data)
                    print("[VocabAPI] [OK] Load " + str(len(data))
                          + " similar chars tu " + fname)
            except Exception as e:
                print("[VocabAPI] [WARN] Loi doc " + fname + ": " + str(e))

    _SIMILAR_CHARS_LOADED = True
    print("[VocabAPI] [OK] Tong similar chars: " + str(total))


def get_similar_chars(char):
    if not char:
        return [], ""
    entry = _SIMILAR_CHARS.get(char)
    if not entry:
        return [], ""
    if isinstance(entry, list):
        return [str(c).strip() for c in entry if c], ""
    if isinstance(entry, dict):
        chars = entry.get('similar', []) or []
        diff = entry.get('diff', '') or ''
        return [str(c).strip() for c in chars if c], diff
    return [], ""


# ---- LOAD LAN DAU ----
_do_load_ai_mnemonics()
_do_load_vocab_meanings()
_do_load_similar_chars()


# ==========================================================
# PHAN 3: CHAM DIEM CAU (tu app.py v3.2 - giu nguyen 100%)
# ==========================================================

_corrector = None
_corrector_lock = threading.Lock()
_corrector_failed = False


def get_corrector():
    global _corrector, _corrector_failed

    if _corrector is not None:
        return _corrector
    if _corrector_failed:
        return None

    with _corrector_lock:
        if _corrector is not None:
            return _corrector
        if _corrector_failed:
            return None

        try:
            print("[API] Loading pycorrector...")
            from pycorrector import MacBertCorrector
            _corrector = MacBertCorrector("shibing624/macbert4csc-base-chinese")
            print("[API] Loaded OK")
            return _corrector
        except Exception as e:
            print("[API] Load failed: " + str(e))
            _corrector_failed = True
            return None


def clean(text):
    if not text:
        return ''
    return re.sub(r'[。，！？、；：""''「」『』（）《》〈〉【】〔〕\s]+', '', str(text))


def get_pinyin(char):
    if not char:
        return ''
    try:
        result = pinyin(char, style=Style.TONE)
        if result and result[0]:
            return result[0][0]
    except Exception:
        pass
    return ''


def add_pinyin_to_errors(errors):
    for e in errors:
        if e.get('user'):
            e['user_pinyin'] = get_pinyin(e['user'])
        if e.get('correct'):
            e['correct_pinyin'] = get_pinyin(e['correct'])
    return errors


def find_diff(user, correct):
    """Tim loi bang Levenshtein. Tra ve ca input_position."""
    u = list(clean(user))
    c = list(clean(correct))
    errors = []
    m, n = len(u), len(c)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if u[i-1] == c[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and u[i-1] == c[j-1]:
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
            errors.append({
                'type': 'wrong',
                'position': j,
                'input_position': i - 1,
                'user': u[i-1],
                'correct': c[j-1]
            })
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j-1] + 1:
            errors.append({
                'type': 'missing',
                'position': j,
                'input_position': i,
                'correct': c[j-1]
            })
            j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + 1:
            errors.append({
                'type': 'extra',
                'position': j,
                'input_position': i - 1,
                'user': u[i-1]
            })
            i -= 1
        else:
            break

    errors.reverse()
    return errors, dp[m][n]


def grade(user_answer, correct_answer):
    u = clean(user_answer)
    c = clean(correct_answer)

    if not u:
        return {
            'score': 0,
            'status': 'empty',
            'message': 'Bạn chưa gõ gì cả',
            'errors': [],
            'suggestion': correct_answer,
            'used_ai': False
        }

    if u == c:
        return {
            'score': 100,
            'status': 'correct',
            'message': 'Đúng hoàn toàn',
            'errors': [],
            'suggestion': None,
            'used_ai': False
        }

    errors = []
    used_ai = False
    corrector = get_corrector()
    if corrector:
        try:
            corrected, err_info = corrector.correct(u)
            if err_info:
                used_ai = True
                for e in err_info:
                    pos = e.get('pos', 0)
                    errors.append({
                        'type': 'wrong',
                        'position': pos,
                        'input_position': pos,
                        'user': e.get('orig', ''),
                        'correct': e.get('correct', '')
                    })
        except Exception as e:
            print("[API] Correct error: " + str(e))

    if not errors:
        errors, _ = find_diff(u, c)

    max_len = max(len(u), len(c))
    distance = len(errors)
    ratio = 1 - (distance / max_len) if max_len > 0 else 0
    ratio = max(0, min(1, ratio))

    if ratio >= 0.9:
        status, message = 'correct', 'Đúng (sai nhỏ)'
    elif ratio >= 0.6:
        status, message = 'partial', 'Gần đúng'
    else:
        status, message = 'wrong', 'Sai'

    add_pinyin_to_errors(errors)

    return {
        'score': round(ratio * 100),
        'status': status,
        'message': message,
        'errors': errors,
        'suggestion': correct_answer if u != c else None,
        'used_ai': used_ai
    }


# ==========================================================
# PHAN 4: ANALYZE CHAR (tu vocab_api.py v1.6 - giu nguyen)
# ==========================================================

def analyze_char(char):
    if not char or len(char) != 1:
        return None
    if not ('\u4e00' <= char <= '\u9fff'):
        return None
    if not HAS_VOCAB:
        return None
    try:
        result = {'char': char, 'pinyin': get_pinyin(char)}

        _check_vocab_meanings_fresh()
        vi = get_meaning(char)
        if vi:
            result['vi'] = vi

        main_rad = get_radical_for_word(char)
        if main_rad:
            result['radical'] = {
                'zh': main_rad.get('zh', ''),
                'pinyin': main_rad.get('pinyin', ''),
                'meaning': main_rad.get('meaning', ''),
                'strokes': main_rad.get('strokes', 0),
                'position': main_rad.get('position', ''),
            }

        comps = _split_components(char)
        if comps:
            result['components'] = []
            for c in comps[:8]:
                result['components'].append({
                    'zh': c.get('zh', ''),
                    'pinyin': c.get('pinyin', ''),
                    'meaning': c.get('meaning', ''),
                    'position': c.get('position', ''),
                })

        mnemonic = get_ai_mnemonic(char)
        if not mnemonic:
            mnemonic = generate_mnemonic(char)
        if mnemonic:
            result['mnemonic'] = mnemonic

        sim_chars, diff_text = get_similar_chars(char)
        if sim_chars:
            similar_full = []
            for c in sim_chars:
                if not c or len(c) != 1:
                    continue
                c_vi = get_meaning(c)
                similar_full.append({
                    'char': c,
                    'pinyin': get_pinyin(c),
                    'meaning': c_vi,
                    'breakdown': '',
                })
            if similar_full:
                result['similar'] = {
                    'list': similar_full,
                    'diff': diff_text,
                }

        return result
    except Exception as e:
        print("[VocabAPI] analyze error '" + str(char) + "': " + str(e))
        return None


# ==========================================================
# PHAN 5: GMAIL OTP
# ==========================================================

def send_gmail_oauth2(to_email, subject, html_content):
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    sender_email = os.environ.get("GOOGLE_SENDER_EMAIL")

    if not all([client_id, client_secret, refresh_token, sender_email]):
        raise Exception("Thiếu thông tin cấu hình Google OAuth2!")

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token"
    )
    service = build('gmail', 'v1', credentials=creds)
    subject_encoded = "=?UTF-8?B?" + base64.b64encode(subject.encode('utf-8')).decode('utf-8') + "?="

    message_parts = [
        f'From: "Account Verification" <{sender_email}>',
        f'To: {to_email}',
        f'Subject: {subject_encoded}',
        'MIME-Version: 1.0',
        'Content-Type: text/html; charset=UTF-8',
        'Content-Transfer-Encoding: base64',
        '',
        base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
    ]
    raw_message = '\n'.join(message_parts)
    encoded_message = base64.urlsafe_b64encode(raw_message.encode('utf-8')).decode('utf-8')
    service.users().messages().send(userId='me', body={'raw': encoded_message}).execute()


# ==========================================================
# PHAN 6: ROUTES
# ==========================================================

@app.route('/')
def index():
    return jsonify({
        'name': 'Chinese Grading + Vocab + OTP API',
        'version': '4.0-merged',
        'model_loaded': _corrector is not None,
        'has_vocab': HAS_VOCAB,
        'ai_mnemonics_loaded': len(_AI_MNEMONICS),
        'ai_index_size': len(_AI_MNEMONICS_INDEX),
        'vocab_meanings_loaded': len(_VOCAB_MEANINGS),
        'similar_chars_loaded': len(_SIMILAR_CHARS),
        'endpoints': {
            'health': 'GET /health',
            'warmup': 'GET /warmup',
            'check': 'POST /check  { user_answer, correct_answer }',
            'test': 'GET /test?u=...&c=...',
            'analyze': 'POST /analyze  { char: "权" }',
            'analyze_batch': 'POST /analyze_batch  { chars: ["权"] }',
            'reload': 'POST /reload',
            'send_otp': 'POST /api/device/send-otp  { email, deviceId, deviceName }',
            'verify_otp': 'POST /api/device/verify-otp  { email, otp }',
            'delete_user': 'POST /api/delete-user  { email }',
        }
    })


# ---- HEALTH / WARMUP ----
@app.route('/health')
def health():
    return jsonify({
        'ok': True,
        'model_loaded': _corrector is not None,
        'model_failed': _corrector_failed,
        'has_vocab': HAS_VOCAB,
        'ai_mnemonics_loaded': len(_AI_MNEMONICS),
        'ai_index_size': len(_AI_MNEMONICS_INDEX),
        'ai_file_path': _AI_MNEMONICS_PATH,
        'ai_file_mtime': _AI_MNEMONICS_MTIME,
        'vocab_meanings_loaded': len(_VOCAB_MEANINGS),
        'vocab_meanings_path': _VOCAB_MEANINGS_PATH,
        'similar_chars_loaded': len(_SIMILAR_CHARS),
        'mongo_ready': otp_collection is not None,
        'version': '4.0-merged',
    })


@app.route('/warmup')
def warmup():
    get_corrector()
    return jsonify({'ok': True, 'loaded': _corrector is not None})


# ---- CHAM DIEM ----
@app.route('/check', methods=['POST'])
def check():
    try:
        data = request.get_json(force=True, silent=True) or {}
        u = data.get('user_answer', '')
        c = data.get('correct_answer', '')
        if not c:
            return jsonify({'error': 'Missing correct_answer'}), 400
        return jsonify(grade(u, c))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/test')
def test_get():
    """Ho tro 2 che do:
       /test?u=...&c=...  -> cham diem (giong app.py goc)
       /test?char=权      -> phan tich chu (giong vocab_api.py)
    """
    # Che do cham diem
    u = request.args.get('u', '')
    c = request.args.get('c', '')
    if c:
        return jsonify(grade(u, c))

    # Che do phan tich chu
    ch = request.args.get('char', '').strip()
    if ch:
        result = analyze_char(ch)
        if not result:
            return jsonify({'ok': False, 'error': 'Analysis failed', 'char': ch}), 500
        return jsonify({'ok': True, 'data': result})

    # Huong dan
    return jsonify({
        'error': 'Thieu tham so',
        'usage_grading': '/test?u=cau_user&c=cau_dung',
        'usage_analyze': '/test?char=权',
        'example': '/test?u=wo xi huan chi ping guo&c=wo xi huan chi ping guo',
    })


# ---- ANALYZE ----
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json(force=True, silent=True) or {}
        char = data.get('char', '').strip()
        if not char:
            return jsonify({'ok': False, 'error': 'Missing char'}), 400
        if len(char) != 1:
            return jsonify({'ok': False, 'error': 'Only 1 char'}), 400
        result = analyze_char(char)
        if not result:
            return jsonify({
                'ok': False, 'error': 'Analysis failed', 'char': char
            }), 500
        return jsonify({'ok': True, 'data': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/analyze_batch', methods=['POST'])
def analyze_batch():
    try:
        data = request.get_json(force=True, silent=True) or {}
        chars = data.get('chars', [])
        if not isinstance(chars, list):
            return jsonify({'ok': False, 'error': 'chars must be array'}), 400
        if len(chars) > 20:
            return jsonify({'ok': False, 'error': 'Max 20 chars'}), 400
        result = {}
        for ch in chars:
            ch = str(ch).strip()
            if not ch or len(ch) != 1:
                continue
            if ch in result:
                continue
            analysis = analyze_char(ch)
            if analysis:
                result[ch] = analysis
        return jsonify({'ok': True, 'data': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/debug')
def debug():
    try:
        ch = request.args.get('char', '').strip()
        if not ch:
            return jsonify({'error': 'Missing ?char=...'})

        _check_vocab_meanings_fresh()

        ai_mnemonic = get_ai_mnemonic(ch) or ''
        static_mnemonic = ''
        if HAS_VOCAB:
            try:
                static_mnemonic = generate_mnemonic(ch) or ''
            except Exception:
                pass
        sim_chars, diff_text = get_similar_chars(ch)
        vi = get_meaning(ch)
        analysis = analyze_char(ch) or {}

        return jsonify({
            'char': ch,
            'has_vocab': HAS_VOCAB,
            'vi': vi,
            'ai_mnemonic': ai_mnemonic,
            'static_mnemonic': static_mnemonic,
            'mnemonic_raw': ai_mnemonic if ai_mnemonic else static_mnemonic,
            'similar_chars': sim_chars,
            'similar_diff': diff_text,
            'full_analysis': analysis,
            'ai_count': len(_AI_MNEMONICS),
            'ai_index_size': len(_AI_MNEMONICS_INDEX),
            'meanings_count': len(_VOCAB_MEANINGS),
            'similar_count': len(_SIMILAR_CHARS),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/reload', methods=['POST', 'GET'])
def reload_ai():
    ok = _do_load_ai_mnemonics()
    _do_load_vocab_meanings()
    return jsonify({
        'ok': ok,
        'count': len(_AI_MNEMONICS),
        'index_size': len(_AI_MNEMONICS_INDEX),
        'path': _AI_MNEMONICS_PATH,
        'mtime': _AI_MNEMONICS_MTIME,
        'meanings_count': len(_VOCAB_MEANINGS),
        'similar_count': len(_SIMILAR_CHARS),
    })


# ---- OTP ----
@app.route('/api/device/send-otp', methods=['POST'])
def send_otp():
    try:
        data = request.get_json(force=True, silent=True) or {}
        email = data.get('email', '')
        device_id = data.get('deviceId', 'unknown')
        device_name = data.get('deviceName', 'Thiết bị')

        if not email or '@' not in email:
            return jsonify({'ok': False, 'error': 'Email không hợp lệ'}), 400

        if otp_collection is None:
            return jsonify({'ok': False, 'error': 'OTP service chưa sẵn sàng'}), 503

        email_lower = email.lower().strip()

        # Rate limit
        now = datetime.utcnow()
        last = last_sent_map.get(email_lower)
        if last and (now - last).total_seconds() < OTP_COOLDOWN_SECONDS:
            remaining = int(OTP_COOLDOWN_SECONDS - (now - last).total_seconds())
            return jsonify({
                'ok': False,
                'error': f'Vui lòng đợi {remaining}s trước khi gửi lại'
            }), 429

        otp = str(random.randint(100000, 999999))
        otp_collection.delete_many({'email': email_lower})
        otp_collection.insert_one({
            'email': email_lower,
            'otp': otp,
            'attempts': 0,
            'createdAt': now
        })

        html = (
            f"<h3>Mã OTP của bạn là:</h3>"
            f"<h1 style='font-size:32px;letter-spacing:4px;color:#4f46e5'>{otp}</h1>"
            f"<p>Thiết bị: {device_name} ({device_id})</p>"
            f"<p>Mã có hiệu lực trong vài phút. Không chia sẻ với ai.</p>"
        )
        send_gmail_oauth2(email_lower, 'OTP Verification', html)

        last_sent_map[email_lower] = now

        return jsonify({'ok': True, 'message': 'Đã gửi mã OTP'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/device/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json(force=True, silent=True) or {}
        email = data.get('email', '')
        otp = data.get('otp', '')

        if not email or not otp:
            return jsonify({'ok': False, 'error': 'Thiếu email hoặc OTP'}), 400

        email_lower = email.lower().strip()

        if otp_collection is None:
            return jsonify({'ok': False, 'error': 'Database chưa sẵn sàng'}), 500

        record = otp_collection.find_one(
            {'email': email_lower},
            sort=[('createdAt', -1)]
        )
        if not record or str(record['otp']) != str(otp).strip():
            return jsonify({'ok': False, 'error': 'Mã OTP không đúng hoặc hết hạn'}), 400

        otp_collection.delete_many({'email': email_lower})
        last_sent_map.pop(email_lower, None)

        return jsonify({'ok': True, 'message': 'Xác thực thành công'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ---- DELETE USER ----
@app.route('/api/delete-user', methods=['POST'])
def delete_user():
    data = request.json or {}
    email = data.get('email')
    if not email:
        return jsonify({"success": False, "error": "Thiếu thông tin email"}), 400

    email_clean = email.strip().lower()
    try:
        db_fs = firestore.client()
        deleted_auth = False
        deleted_firestore = False

        try:
            user_record = auth.get_user_by_email(email_clean)
            auth.delete_user(user_record.uid)
            deleted_auth = True
        except Exception as e:
            print("[DeleteUser] auth skip: " + str(e))

        try:
            doc_ref = db_fs.collection('allowed_users').document(email_clean)
            if doc_ref.get().exists:
                doc_ref.delete()
                deleted_firestore = True
        except Exception as e:
            print("[DeleteUser] firestore skip: " + str(e))

        return jsonify({
            "success": True,
            "message": f"Đã xóa user {email_clean}",
            "deleted_auth": deleted_auth,
            "deleted_firestore": deleted_firestore,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================================
# MAIN
# ==========================================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
