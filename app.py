# -*- coding: utf-8 -*-
"""
ALL-IN-ONE API (Python)
Bao gồm: Chấm điểm, Từ vựng (Vocab), Firebase Delete, và OTP (chuyển từ Node.js).
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pypinyin import pinyin, Style

import os
import sys
import json
import re
import random
import base64
import threading
import traceback
from datetime import datetime, timedelta

# Thư viện OTP & Firebase
from pymongo import MongoClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import firebase_admin
from firebase_admin import credentials, auth, firestore

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

# ==========================================================
# PHẦN 1: KHỞI TẠO FIREBASE
# ==========================================================
FIREBASE_READY = False
try:
    firebase_json_str = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if firebase_json_str:
        cred = credentials.Certificate(json.loads(firebase_json_str))
        firebase_admin.initialize_app(cred)
        FIREBASE_READY = True
        print("[API] Firebase init OK (env)")
    elif os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        FIREBASE_READY = True
        print("[API] Firebase init OK (file)")
    else:
        print("[API] [WARN] Không có Firebase credential — /api/delete-user sẽ lỗi")
except Exception as e:
    print("[API] Firebase init failed: " + str(e))

# ==========================================================
# PHẦN 2: KHỞI TẠO MONGODB (Cho OTP)
# ==========================================================
MONGO_URI = os.environ.get("MONGODB_URI")
mongo_client = None
db_mongo = None
otp_collection = None
last_sent_map = {}

if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        db_mongo = mongo_client["test"]
        otp_collection = db_mongo["otpcodes"]
        # Tạo TTL index để tự động xóa OTP sau 10 phút (600 giây)
        otp_collection.create_index("createdAt", expireAfterSeconds=600)
        print("[API] MongoDB init OK (OTP ready)")
    except Exception as e:
        print("[API] MongoDB init failed: " + str(e))

# ==========================================================
# PHẦN 3: SETUP VOCAB (Từ vocab_api.py)
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

_AI_MNEMONICS = {}
_AI_MNEMONICS_INDEX = {}
_VOCAB_MEANINGS = {}
_SIMILAR_CHARS = {}

def _find_ai_mnemonics_file():
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    candidates = [
        os.path.join(here, "data", "ai_mnemonics.json"),
        os.path.join(parent, "data", "ai_mnemonics.json"),
        os.path.join(os.getcwd(), "data", "ai_mnemonics.json"),
        "data/ai_mnemonics.json", "ai_mnemonics.json",
    ]
    for p in candidates:
        if os.path.exists(p): return p
    return None

def _build_ai_index(data):
    idx = {}
    for k, v in data.items():
        parts = k.split("|")
        if len(parts) == 3 and parts[2].strip():
            idx[parts[2].strip()] = v
    return idx

def _do_load_ai_mnemonics():
    global _AI_MNEMONICS, _AI_MNEMONICS_INDEX
    path = _find_ai_mnemonics_file()
    if not path: return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            _AI_MNEMONICS = json.load(f)
        _AI_MNEMONICS_INDEX = _build_ai_index(_AI_MNEMONICS)
        return True
    except: return False

def get_ai_mnemonic(char):
    if not _AI_MNEMONICS_INDEX: _do_load_ai_mnemonics()
    return _AI_MNEMONICS_INDEX.get(str(char or "").strip(), "")

def _find_vocab_meanings_file():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in [os.path.join(here, "data", "vocab_meanings.json"), "data/vocab_meanings.json"]:
        if os.path.exists(p): return p
    return None

def _do_load_vocab_meanings():
    global _VOCAB_MEANINGS
    path = _find_vocab_meanings_file()
    if not path: return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            _VOCAB_MEANINGS = json.load(f)
        return True
    except: return False

def get_meaning(char):
    return _VOCAB_MEANINGS.get(char, "")

def _do_load_similar_chars():
    global _SIMILAR_CHARS
    here = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(here, "vocab_data")
    if os.path.isdir(folder):
        for fname in os.listdir(folder):
            if fname.startswith("similar_chars") and fname.endswith(".json"):
                try:
                    with open(os.path.join(folder, fname), "r", encoding="utf-8") as f:
                        _SIMILAR_CHARS.update(json.load(f))
                except: pass

def get_similar_chars(char):
    if not char: return [], ""
    entry = _SIMILAR_CHARS.get(char)
    if not entry: return [], ""
    if isinstance(entry, list): return [str(c).strip() for c in entry if c], ""
    if isinstance(entry, dict):
        return [str(c).strip() for c in entry.get('similar', []) if c], entry.get('diff', '')
    return [], ""

_do_load_ai_mnemonics()
_do_load_vocab_meanings()
_do_load_similar_chars()

def get_pinyin_vocab(char):
    if not char: return ''
    try:
        result = pinyin(char, style=Style.TONE)
        if result and result[0]: return result[0][0]
    except: pass
    return ''

def analyze_char(char):
    if not char or len(char) != 1 or not ('\u4e00' <= char <= '\u9fff') or not HAS_VOCAB:
        return None
    try:
        result = {'char': char, 'pinyin': get_pinyin_vocab(char)}
        vi = get_meaning(char)
        if vi: result['vi'] = vi
        
        main_rad = get_radical_for_word(char)
        if main_rad:
            result['radical'] = {
                'zh': main_rad.get('zh', ''), 'pinyin': main_rad.get('pinyin', ''),
                'meaning': main_rad.get('meaning', ''), 'strokes': main_rad.get('strokes', 0),
                'position': main_rad.get('position', '')
            }
        
        comps = _split_components(char)
        if comps:
            result['components'] = [{
                'zh': c.get('zh', ''), 'pinyin': c.get('pinyin', ''),
                'meaning': c.get('meaning', ''), 'position': c.get('position', '')
            } for c in comps[:8]]

        mnemonic = get_ai_mnemonic(char) or generate_mnemonic(char)
        if mnemonic: result['mnemonic'] = mnemonic
        
        sim_chars, diff_text = get_similar_chars(char)
        if sim_chars:
            result['similar'] = {
                'list': [{'char': c, 'pinyin': get_pinyin_vocab(c), 'meaning': get_meaning(c)} for c in sim_chars if len(c)==1],
                'diff': diff_text
            }
        return result
    except Exception as e:
        print("[VocabAPI] analyze error:", e)
        return None

# ==========================================================
# PHẦN 4: CHẤM ĐIỂM (Từ app.py)
# ==========================================================
_corrector = None
_corrector_lock = threading.Lock()
_corrector_failed = False

def get_corrector():
    global _corrector, _corrector_failed
    if _corrector is not None: return _corrector
    if _corrector_failed: return None
    with _corrector_lock:
        if _corrector is not None: return _corrector
        if _corrector_failed: return None
        try:
            from pycorrector import MacBertCorrector
            _corrector = MacBertCorrector("shibing624/macbert4csc-base-chinese")
            return _corrector
        except Exception as e:
            print("[API] Load failed:", e)
            _corrector_failed = True
            return None

def clean(text):
    if not text: return ''
    return re.sub(r'[。，！？、；：""''「」『』（）《》〈〉【】〔〕\s]+', '', str(text))

def get_pinyin(char):
    if not char: return ''
    try:
        result = pinyin(char, style=Style.TONE)
        if result and result[0]: return result[0][0]
    except: pass
    return ''

def add_pinyin_to_errors(errors):
    for e in errors:
        if e.get('user'): e['user_pinyin'] = get_pinyin(e['user'])
        if e.get('correct'): e['correct_pinyin'] = get_pinyin(e['correct'])
    return errors

def find_diff(user, correct):
    u, c = list(clean(user)), list(clean(correct))
    errors = []
    m, n = len(u), len(c)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1): dp[i][0] = i
    for j in range(n + 1): dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if u[i-1] == c[j-1]: dp[i][j] = dp[i-1][j-1]
            else: dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and u[i-1] == c[j-1]:
            i -= 1; j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
            errors.append({'type': 'wrong', 'position': j, 'input_position': i - 1, 'user': u[i-1], 'correct': c[j-1]})
            i -= 1; j -= 1
        elif j > 0 and dp[i][j] == dp[i][j-1] + 1:
            errors.append({'type': 'missing', 'position': j, 'input_position': i, 'correct': c[j-1]})
            j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + 1:
            errors.append({'type': 'extra', 'position': j, 'input_position': i - 1, 'user': u[i-1]})
            i -= 1
        else: break
    errors.reverse()
    return errors, dp[m][n]

def grade(user_answer, correct_answer):
    u, c = clean(user_answer), clean(correct_answer)
    if not u: return {'score': 0, 'status': 'empty', 'message': 'Bạn chưa gõ gì cả', 'errors': [], 'suggestion': correct_answer, 'used_ai': False}
    if u == c: return {'score': 100, 'status': 'correct', 'message': 'Đúng hoàn toàn', 'errors': [], 'suggestion': None, 'used_ai': False}
    
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
                    errors.append({'type': 'wrong', 'position': pos, 'input_position': pos, 'user': e.get('orig', ''), 'correct': e.get('correct', '')})
        except Exception as e: print("[API] Correct error:", e)
        
    if not errors: errors, _ = find_diff(u, c)
    
    max_len = max(len(u), len(c))
    distance = len(errors)
    ratio = 1 - (distance / max_len) if max_len > 0 else 0
    ratio = max(0, min(1, ratio))
    
    if ratio >= 0.9: status, message = 'correct', 'Đúng (sai nhỏ)'
    elif ratio >= 0.6: status, message = 'partial', 'Gần đúng'
    else: status, message = 'wrong', 'Sai'
    
    add_pinyin_to_errors(errors)
    
    return {
        'score': round(ratio * 100), 'status': status, 'message': message,
        'errors': errors, 'suggestion': correct_answer if u != c else None, 'used_ai': used_ai
    }

# ==========================================================
# PHẦN 5: OTP GMAIL (Chuyển từ server.js sang Python)
# ==========================================================
def send_gmail_html(to_email, subject, html_content):
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    sender_email = os.environ.get("GOOGLE_SENDER_EMAIL")

    if not all([client_id, client_secret, refresh_token, sender_email]):
        raise Exception("Thiếu cấu hình Google OAuth2 (Env Vars)")

    creds = Credentials(
        None, refresh_token=refresh_token, client_id=client_id,
        client_secret=client_secret, token_uri="https://oauth2.googleapis.com/token"
    )
    service = build('gmail', 'v1', credentials=creds)
    
    # Mã hóa tiêu đề
    subject_encoded = "=?UTF-8?B?" + base64.b64encode(subject.encode('utf-8')).decode('utf-8') + "?="
    
    # Xây dựng message
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

@app.route('/api/device/send-otp', methods=['POST'])
def send_otp():
    if otp_collection is None:
        return jsonify({'ok': False, 'error': 'OTP service chưa sẵn sàng (Thiếu MongoDB)'}), 503
        
    try:
        data = request.get_json(force=True, silent=True) or {}
        email = data.get('email', '')
        device_id = data.get('deviceId', 'unknown')
        device_name = data.get('deviceName', 'Thiết bị')
        
        if not email or '@' not in email:
            return jsonify({'ok': False, 'error': 'Email không hợp lệ'}), 400
            
        email_lower = email.lower().strip()
        
        # Rate limit 60s
        now = datetime.utcnow()
        last_sent = last_sent_map.get(email_lower)
        if last_sent and (now - last_sent).total_seconds() < 60:
            wait_sec = int(60 - (now - last_sent).total_seconds())
            return jsonify({'ok': False, 'error': f'Vui lòng đợi {wait_sec} giây trước khi gửi lại', 'waitSec': wait_sec}), 429
            
        # Xóa OTP cũ & tạo mới
        otp_collection.delete_many({'email': email_lower})
        otp = str(random.randint(100000, 999999))
        otp_collection.insert_one({
            'email': email_lower,
            'otp': otp,
            'deviceId': device_id,
            'deviceName': device_name,
            'attempts': 0,
            'createdAt': now
        })
        
        # Gửi mail
        html = build_otp_email_html(otp, device_name, email_lower)
        send_gmail_html(email_lower, 'Your OTP Verification Code', html)
        
        last_sent_map[email_lower] = now
        print(f"📧 Gửi OTP {otp} đến {email_lower}")
        return jsonify({'ok': True, 'message': 'Đã gửi mã OTP'})
        
    except Exception as e:
        print("❌ Send OTP error:", e)
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/device/verify-otp', methods=['POST'])
def verify_otp():
    if otp_collection is None:
        return jsonify({'ok': False, 'error': 'OTP service chưa sẵn sàng'}), 503

    try:
        data = request.get_json(force=True, silent=True) or {}
        email = data.get('email', '')
        otp = data.get('otp', '')
        
        if not email or not otp:
            return jsonify({'ok': False, 'error': 'Thiếu email hoặc OTP'}), 400
            
        email_lower = email.lower().strip()
        record = otp_collection.find_one({'email': email_lower}, sort=[('createdAt', -1)])
        
        if not record:
            return jsonify({'ok': False, 'error': 'OTP không tồn tại hoặc đã hết hạn'}), 400
            
        # Kiểm tra hết hạn (10 phút) - Đề phòng TTL index chưa chạy kịp
        if datetime.utcnow() - record['createdAt'] > timedelta(minutes=10):
            otp_collection.delete_many({'email': email_lower})
            return jsonify({'ok': False, 'error': 'OTP đã hết hạn'}), 400
            
        # Kiểm tra số lần nhập sai
        if record.get('attempts', 0) >= 5:
            otp_collection.delete_many({'email': email_lower})
            return jsonify({'ok': False, 'error': 'Quá nhiều lần thử'}), 429
            
        # Kiểm tra OTP
        if str(record['otp']) != str(otp).strip():
            otp_collection.update_one({'_id': record['_id']}, {'$inc': {'attempts': 1}})
            return jsonify({
                'ok': False, 
                'error': 'Mã OTP không đúng',
                'attemptsLeft': 5 - (record.get('attempts', 0) + 1)
            }), 400
            
        # Đúng -> Xóa OTP
        otp_collection.delete_many({'email': email_lower})
        print(f"✅ OTP đúng cho {email_lower}")
        return jsonify({'ok': True, 'message': 'Xác thực thành công'})
        
    except Exception as e:
        print("❌ Verify OTP error:", e)
        return jsonify({'ok': False, 'error': str(e)}), 500


# ==========================================================
# PHẦN 6: ĐỊNH NGHĨA CÁC ROUTES KHÁC
# ==========================================================

@app.route('/')
def index():
    return jsonify({'name': 'All-in-one API', 'version': '6.0-python-all'})

@app.route('/health')
def health():
    return jsonify({
        'ok': True, 
        'model_loaded': _corrector is not None, 
        'firebase_ready': FIREBASE_READY, 
        'mongo_ready': otp_collection is not None
    })

@app.route('/warmup')
def warmup():
    get_corrector()
    return jsonify({'ok': True, 'loaded': _corrector is not None})

@app.route('/check', methods=['POST'])
def check():
    try:
        data = request.get_json(force=True, silent=True) or {}
        u, c = data.get('user_answer', ''), data.get('correct_answer', '')
        if not c: return jsonify({'error': 'Missing correct_answer'}), 400
        return jsonify(grade(u, c))
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/test')
def test_get():
    u, c = request.args.get('u', ''), request.args.get('c', '')
    if not c:
        return jsonify({'error': 'Thieu tham so c', 'usage': 'Them ?u=cau_user&c=cau_dung'})
    return jsonify(grade(u, c))

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json(force=True, silent=True) or {}
        char = data.get('char', '').strip()
        if not char or len(char) != 1: return jsonify({'ok': False, 'error': 'Invalid char'}), 400
        res = analyze_char(char)
        return jsonify({'ok': True, 'data': res}) if res else jsonify({'ok': False, 'error': 'Not found'}), 500
    except Exception as e: return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/vocab_test')
def vocab_test():
    ch = request.args.get('char', '').strip()
    res = analyze_char(ch)
    return jsonify({'ok': True, 'data': res}) if res else jsonify({'ok': False, 'error': 'Not found'}), 500

@app.route('/reload', methods=['POST', 'GET'])
def reload_ai():
    _do_load_ai_mnemonics()
    _do_load_vocab_meanings()
    return jsonify({'ok': True, 'ai_count': len(_AI_MNEMONICS), 'meanings_count': len(_VOCAB_MEANINGS)})

@app.route('/api/delete-user', methods=['POST'])
def delete_user():
    if not FIREBASE_READY:
        return jsonify({"success": False, "error": "Firebase chưa được cấu hình"}), 503

    data = request.json or {}
    email = data.get('email')
    if not email: return jsonify({"success": False, "error": "Thiếu email"}), 400

    email_clean = email.strip().lower()
    try:
        db = firestore.client()
        deleted_auth = False
        deleted_firestore = False
        
        try:
            user_record = auth.get_user_by_email(email_clean)
            auth.delete_user(user_record.uid)
            deleted_auth = True
        except firebase_admin.auth.UserNotFoundError: pass
            
        doc_ref = db.collection('allowed_users').document(email_clean)
        if doc_ref.get().exists:
            doc_ref.delete()
            deleted_firestore = True
            
        if not deleted_auth and not deleted_firestore:
            return jsonify({"success": False, "error": f"Không tìm thấy user {email_clean}"}), 404
            
        return jsonify({"success": True, "message": f"Đã xóa user {email_clean}"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
