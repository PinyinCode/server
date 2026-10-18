# -*- coding: utf-8 -*-
"""
Unified Flask Server (All-in-One):
1. Chấm điểm tiếng Trung (MacBert + Pinyin + Diff) -> /check, /test, /warmup, /health
2. Gửi & xác thực OTP qua Gmail OAuth2 + MongoDB -> /api/device/send-otp, /api/device/verify-otp
3. Xóa tài khoản Firebase Auth & Firestore -> /api/delete-user
4. Phân tích chi tiết từ vựng / Flashcard -> /analyze, /analyze_batch, /debug
"""

import os
import json
import traceback
import threading
import random
import base64
import sys
from math import ceil
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from fuzzywuzzy import fuzz
from pypinyin import pinyin, Style
import re

# Đảm bảo đường dẫn module hiện tại được ưu tiên
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- GOOGLE GMAIL OAUTH2 SETUP ---
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- FIREBASE SETUP ---
import firebase_admin
from firebase_admin import credentials, auth, firestore

firebase_json_str = os.environ.get("FIREBASE_CREDENTIALS_JSON")
if firebase_json_str:
    try:
        cred_dict = json.loads(firebase_json_str)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"⚠️ Lỗi khởi tạo Firebase từ biến môi trường: {e}")
else:
    if os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    else:
        print("⚠️ Cảnh báo: Chưa cấu hình thông tin xác thực Firebase Admin SDK!")

# --- MONGODB SETUP CHO OTP ---
from pymongo import MongoClient
MONGO_URI = os.environ.get("MONGODB_URI")
mongo_client = MongoClient(MONGO_URI) if MONGO_URI else None
db_mongo = mongo_client["test"] if mongo_client else None
otp_collection = db_mongo["otpcodes"] if db_mongo is not None else None
last_sent_map = {}

# --- VOCAB ANALYSIS SETUP ---
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
        return True
    except Exception as e:
        return False

def get_ai_mnemonic(char):
    if not _AI_MNEMONICS_LOADED:
        _do_load_ai_mnemonics()
    if not _AI_MNEMONICS_INDEX:
        return ""
    char = str(char or "").strip()
    return _AI_MNEMONICS_INDEX.get(char, "")

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
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            _VOCAB_MEANINGS = data
            _VOCAB_MEANINGS_PATH = path
            _VOCAB_MEANINGS_MTIME = os.path.getmtime(path)
            return True
    except Exception:
        pass
    return False

def get_meaning(char):
    if not char:
        return ""
    return _VOCAB_MEANINGS.get(char, "")

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

    for fname in sorted(os.listdir(folder)):
        if fname.startswith("similar_chars") and fname.endswith(".json"):
            path = os.path.join(folder, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    _SIMILAR_CHARS.update(data)
            except Exception:
                pass
    _SIMILAR_CHARS_LOADED = True

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

app = Flask(__name__)
CORS(app)

# Khởi tạo dữ liệu từ vựng lúc khởi động server
_do_load_ai_mnemonics()
_do_load_vocab_meanings()
_do_load_similar_chars()


# ==========================================
# 1. CHỨC NĂNG: CHẤM ĐIỂM TIẾNG TRUNG (MacBert)
# ==========================================
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

def get_pinyin_char(char):
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
            e['user_pinyin'] = get_pinyin_char(e['user'])
        if e.get('correct'):
            e['correct_pinyin'] = get_pinyin_char(e['correct'])
    return errors

def find_diff(user, correct):
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

@app.route('/health')
def health():
    return jsonify({
        'ok': True,
        'model_loaded': _corrector is not None,
        'model_failed': _corrector_failed,
        'has_vocab': HAS_VOCAB,
        'ai_mnemonics_loaded': len(_AI_MNEMONICS),
        'vocab_meanings_loaded': len(_VOCAB_MEANINGS),
    })

@app.route('/warmup')
def warmup():
    get_corrector()
    return jsonify({'ok': True, 'loaded': _corrector is not None})

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
    u = request.args.get('u', '')
    c = request.args.get('c', '')
    if not c:
        return jsonify({
            'error': 'Thieu tham so c',
            'usage': 'Them ?u=cau_user&c=cau_dung'
        })
    return jsonify(grade(u, c))


# ==========================================
# 2. CHỨC NĂNG: GỬI & XÁC THỰC OTP QUA GMAIL OAUTH2 & MONGODB
# ==========================================
def send_gmail_oauth2(to_email, subject, html_content):
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    sender_email = os.environ.get("GOOGLE_SENDER_EMAIL")

    if not all([client_id, client_secret, refresh_token, sender_email]):
        raise Exception("Thiếu thông tin cấu hình Google OAuth2 trong biến môi trường!")

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

def build_otp_email_html(otp, device_name, email):
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;background:#f8fafc;padding:20px;border-radius:12px">
        <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:24px;border-radius:12px 12px 0 0;text-align:center">
            <h1 style="color:#fff;margin:0;font-size:22px">🔐 Xác thực đăng nhập</h1>
        </div>
        <div style="background:#fff;padding:28px 24px;border-radius:0 0 12px 12px">
            <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 16px">
                Có một thiết bị mới đang cố đăng nhập vào tài khoản <b>{email}</b>:
            </p>
            <div style="background:#f1f5f9;border-radius:10px;padding:14px 18px;margin-bottom:20px">
                <div style="font-weight:bold;color:#0f172a;font-size:15px">{device_name or 'Thiết bị'}</div>
            </div>
            <p style="color:#475569;font-size:14px;margin:0 0 12px">Nhập mã OTP sau để xác nhận:</p>
            <div style="text-align:center;margin:24px 0">
                <div style="display:inline-block;background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:18px 36px;border-radius:12px">
                    <div style="color:#fff;font-size:36px;font-weight:900;letter-spacing:8px;font-family:monospace">{otp}</div>
                </div>
            </div>
            <p style="color:#94a3b8;font-size:13px;text-align:center;margin:0">
                Mã có hiệu lực trong <b>10 phút</b>.
            </p>
            <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:12px 16px;border-radius:8px;margin-top:20px">
                <p style="color:#92400e;font-size:13px;margin:0;line-height:1.5">
                    ⚠️ Nếu <b>KHÔNG phải bạn</b>, hãy bỏ qua email này và đổi mật khẩu ngay.
                </p>
            </div>
        </div>
    </div>
    """

def generate_otp():
    return str(random.randint(100000, 999999))

@app.route('/api/device/send-otp', methods=['POST'])
def send_otp():
    try:
        data = request.get_json(force=True, silent=True) or {}
        email = data.get('email', '')
        device_id = data.get('deviceId', 'unknown')
        device_name = data.get('deviceName', 'Thiết bị')

        if not email or '@' not in email:
            return jsonify({'ok': False, 'error': 'Email không hợp lệ'}), 400

        email_lower = email.lower().strip()
        now = datetime.utcnow().timestamp() * 1000
        last_sent = last_sent_map.get(email_lower, 0)
        if now - last_sent < 60000:
            wait_sec = int(ceil((60000 - (now - last_sent)) / 1000))
            return jsonify({'ok': False, 'error': f'Vui lòng đợi {wait_sec} giây trước khi gửi lại'}), 429

        if otp_collection is not None:
            otp_collection.delete_many({'email': email_lower})

        otp = generate_otp()
        try:
            html = build_otp_email_html(otp, device_name, email_lower)
            send_gmail_oauth2(email_lower, 'Your OTP Verification Code', html)
        except Exception as mail_err:
            return jsonify({'ok': False, 'error': f'Không thể gửi email: {str(mail_err)}'}), 500

        record = {
            'email': email_lower,
            'otp': otp,
            'deviceId': device_id,
            'deviceName': device_name,
            'attempts': 0,
            'createdAt': datetime.utcnow()
        }
        if otp_collection is not None:
            otp_collection.insert_one(record)

        last_sent_map[email_lower] = now
        return jsonify({'ok': True, 'message': 'Đã gửi mã OTP'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/device/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json(force=True, silent=True) or {}
        email, otp = data.get('email', ''), data.get('otp', '')

        if not email or not otp:
            return jsonify({'ok': False, 'error': 'Thiếu email hoặc OTP'}), 400

        email_lower = email.lower().strip()
        if otp_collection is None:
            return jsonify({'ok': False, 'error': 'Database chưa sẵn sàng'}), 500

        record = otp_collection.find_one({'email': email_lower}, sort=[('createdAt', -1)])
        if not record:
            return jsonify({'ok': False, 'error': 'OTP không tồn tại hoặc đã hết hạn'}), 400

        if datetime.utcnow() - record['createdAt'] > timedelta(minutes=10):
            otp_collection.delete_many({'email': email_lower})
            return jsonify({'ok': False, 'error': 'OTP đã hết hạn'}), 400

        if record.get('attempts', 0) >= 5:
            otp_collection.delete_many({'email': email_lower})
            return jsonify({'ok': False, 'error': 'Quá nhiều lần thử'}), 429

        if str(record['otp']) != str(otp).strip():
            otp_collection.update_one({'_id': record['_id']}, {'$inc': {'attempts': 1}})
            return jsonify({'ok': False, 'error': 'Mã OTP không đúng', 'attemptsLeft': 5 - (record.get('attempts', 0) + 1)}), 400

        otp_collection.delete_many({'email': email_lower})
        return jsonify({'ok': True, 'message': 'Xác thực thành công'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ==========================================
# 3. CHỨC NĂNG: XÓA TÀI KHOẢN FIREBASE
# ==========================================
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
        except firebase_admin.auth.UserNotFoundError:
            pass
            
        doc_ref = db_fs.collection('allowed_users').document(email_clean)
        doc = doc_ref.get()
        if doc.exists:
            doc_ref.delete()
            deleted_firestore = True
            
        if not deleted_auth and not deleted_firestore:
            return jsonify({"success": False, "error": f"Không tìm thấy user {email_clean} trong hệ thống."}), 404
            
        return jsonify({
            "success": True, 
            "message": f"Đã xóa hoàn toàn user {email_clean} (Auth: {deleted_auth}, Firestore: {deleted_firestore})"
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ==========================================
# 4. CHỨC NĂNG: PHÂN TÍCH TỪ VỰNG & FLASHCARD (/analyze, /debug)
# ==========================================
def analyze_char(char):
    if not char or len(char) != 1:
        return None
    if not ('\u4e00' <= char <= '\u9fff'):
        return None
    if not HAS_VOCAB:
        return None
    try:
        result = {'char': char, 'pinyin': get_pinyin_char(char)}
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
                    'pinyin': get_pinyin_char(c),
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

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json(force=True, silent=True) or {}
        char = data.get('char', '').strip()
        if not char or len(char) != 1:
            return jsonify({'ok': False, 'error': 'Invalid or missing char'}), 400
        result = analyze_char(char)
        if not result:
            return jsonify({'ok': False, 'error': 'Analysis failed', 'char': char}), 500
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
        result = {}
        for ch in chars:
            ch = str(ch).strip()
            if not ch or len(ch) != 1 or ch in result:
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
        analysis = analyze_char(ch) or {}
        return jsonify({
            'char': ch,
            'has_vocab': HAS_VOCAB,
            'full_analysis': analysis,
            'ai_count': len(_AI_MNEMONICS),
            'meanings_count': len(_VOCAB_MEANINGS),
            'similar_count': len(_SIMILAR_CHARS),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==========================================
# HOME ENDPOINT
# ==========================================
@app.route('/')
def index():
    return jsonify({
        'status': 'running',
        'message': 'Unified Python Flask Server (4 trong 1) hoạt động hoàn hảo!',
        'endpoints': {
            'health': 'GET /health',
            'warmup': 'GET /warmup',
            'check_api': 'POST /check',
            'test_api': 'GET /test?u=...&c=...',
            'send_otp': 'POST /api/device/send-otp',
            'verify_otp': 'POST /api/device/verify-otp',
            'delete_user': 'POST /api/delete-user',
            'analyze': 'POST /analyze { "char": "爱" }',
            'analyze_batch': 'POST /analyze_batch { "chars": ["爱", "你"] }',
            'debug': 'GET /debug?char=爱'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
