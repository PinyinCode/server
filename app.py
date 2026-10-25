# -*- coding: utf-8 -*-
"""
MEGA API 5-IN-1 (BẢN HOÀN CHỈNH - PHÂN QUYỀN TOKEN, LỊCH SỬ 100 CÂU CUỐN CHIẾU & GIỚI HẠN NGÀY)
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
import requests
from datetime import datetime, timedelta

# Thư viện OTP & Firebase & Excel
from pymongo import MongoClient
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import firebase_admin
from firebase_admin import credentials, auth, firestore
from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

# ==========================================================
# CẤU HÌNH CORS TỐI ĐA (DÀNH RIÊNG CHO SAFARI/IOS)
# ==========================================================
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With", "X-CSRF-Token"]
    }
})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept,Origin,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS,PUT,DELETE')
    return response

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
    elif os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        FIREBASE_READY = True
except Exception as e:
    print("[API] Firebase init failed:", e)

# ==========================================================
# PHẦN 2: KHỞI TẠO MONGODB (OTP)
# ==========================================================
MONGO_URI = os.environ.get("MONGODB_URI")
mongo_client = None
otp_collection = None
last_sent_map = {}

if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        otp_collection = mongo_client["test"]["otpcodes"]
        otp_collection.create_index("createdAt", expireAfterSeconds=600)
        print("[API] MongoDB init OK")
    except Exception as e:
        print("[API] MongoDB init failed:", e)

# ==========================================================
# PHẦN 3: VOCAB SETUP
# ==========================================================
HAS_VOCAB = False
try:
    from vocab_data.radical_analyzer import _split_components, get_radical_for_word
    from vocab_data.mnemonic_generator import generate_mnemonic
    HAS_VOCAB = True
except Exception as e:
    print("[VocabAPI] vocab_data load failed:", e)

_AI_MNEMONICS = {}
_AI_MNEMONICS_INDEX = {}
_VOCAB_MEANINGS = {}
_SIMILAR_CHARS = {}

def _find_ai_mnemonics_file():
    here = os.path.dirname(os.path.abspath(__file__))
    for p in [os.path.join(here, "data", "ai_mnemonics.json"), "data/ai_mnemonics.json"]:
        if os.path.exists(p): return p
    return None

def _build_ai_index(data):
    idx = {}
    for k, v in data.items():
        parts = k.split("|")
        if len(parts) == 3 and parts[2].strip(): idx[parts[2].strip()] = v
    return idx

def _do_load_ai_mnemonics():
    global _AI_MNEMONICS, _AI_MNEMONICS_INDEX
    path = _find_ai_mnemonics_file()
    if not path: return False
    try:
        with open(path, "r", encoding="utf-8") as f: _AI_MNEMONICS = json.load(f)
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
        with open(path, "r", encoding="utf-8") as f: _VOCAB_MEANINGS = json.load(f)
        return True
    except: return False

def get_meaning(char): return _VOCAB_MEANINGS.get(char, "")

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
    if isinstance(entry, dict): return [str(c).strip() for c in entry.get('similar', []) if c], entry.get('diff', '')
    return [], ""

_do_load_ai_mnemonics()
_do_load_vocab_meanings()
_do_load_similar_chars()

def get_pinyin_vocab(char):
    if not char: return ''
    try:
        res = pinyin(char, style=Style.TONE)
        if res and res[0]: return res[0][0]
    except: pass
    return ''

def analyze_char(char):
    if not char or len(char) != 1 or not ('\u4e00' <= char <= '\u9fff') or not HAS_VOCAB:
        return None
    try:
        result = {'char': char, 'pinyin': get_pinyin_vocab(char)}
        try:
            vi = get_meaning(char)
            if vi: result['vi'] = vi
        except: pass
        try:
            main_rad = get_radical_for_word(char)
            if main_rad: 
                result['radical'] = {k: main_rad.get(k, '') for k in ['zh', 'pinyin', 'meaning', 'strokes', 'position']}
        except: pass
        try:
            comps = _split_components(char)
            if comps: 
                result['components'] = [{k: c.get(k, '') for k in ['zh', 'pinyin', 'meaning', 'position']} for c in comps[:8]]
        except: pass
        try:
            mnemonic = get_ai_mnemonic(char) or generate_mnemonic(char)
            if mnemonic: result['mnemonic'] = mnemonic
        except: pass
        try:
            sim_chars, diff_text = get_similar_chars(char)
            if sim_chars:
                result['similar'] = {
                    'list': [{'char': c, 'pinyin': get_pinyin_vocab(c), 'meaning': get_meaning(c)} for c in sim_chars if len(c)==1],
                    'diff': diff_text
                }
        except: pass
        return result
    except:
        return {'char': char, 'pinyin': get_pinyin_vocab(char)}

# ==========================================================
# PHẦN 4: CHẤM ĐIỂM
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
        except:
            _corrector_failed = True
            return None

def clean(text):
    if not text: return ''
    return re.sub(r'[。，！？、；：""''「」『』（）《》〈〉【】〔〕\s]+', '', str(text))

def get_pinyin(char):
    if not char: return ''
    try:
        res = pinyin(char, style=Style.TONE)
        if res and res[0]: return res[0][0]
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
        if i > 0 and j > 0 and u[i-1] == c[j-1]: i -= 1; j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
            errors.append({'type': 'wrong', 'position': j, 'input_position': i-1, 'user': u[i-1], 'correct': c[j-1]})
            i -= 1; j -= 1
        elif j > 0 and dp[i][j] == dp[i][j-1] + 1:
            errors.append({'type': 'missing', 'position': j, 'input_position': i, 'correct': c[j-1]})
            j -= 1
        elif i > 0 and dp[i][j] == dp[i-1][j] + 1:
            errors.append({'type': 'extra', 'position': j, 'input_position': i-1, 'user': u[i-1]})
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
        except: pass
        
    if not errors: errors, _ = find_diff(u, c)
    max_len = max(len(u), len(c))
    ratio = max(0, min(1, 1 - (len(errors) / max_len))) if max_len > 0 else 0
    
    if ratio >= 0.9: status, message = 'correct', 'Đúng (sai nhỏ)'
    elif ratio >= 0.6: status, message = 'partial', 'Gần đúng'
    else: status, message = 'wrong', 'Sai'
    
    add_pinyin_to_errors(errors)
    return {'score': round(ratio * 100), 'status': status, 'message': message, 'errors': errors, 'suggestion': correct_answer if u != c else None, 'used_ai': used_ai}

# ==========================================================
# PHẦN 5: OTP GMAIL & ROUTES KHÁC
# ==========================================================
def send_gmail_html(to, subject, html):
    cid, csecret = os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")
    rtoken, sender = os.environ.get("GOOGLE_REFRESH_TOKEN"), os.environ.get("GOOGLE_SENDER_EMAIL")
    if not all([cid, csecret, rtoken, sender]): raise Exception("Thiếu biến môi trường Google OAuth2")
    
    creds = Credentials(None, refresh_token=rtoken, client_id=cid, client_secret=csecret, token_uri="https://oauth2.googleapis.com/token")
    service = build('gmail', 'v1', credentials=creds)
    
    sub_enc = "=?UTF-8?B?" + base64.b64encode(subject.encode('utf-8')).decode('utf-8') + "?="
    msg = f'From: "Account Verification" <{sender}>\nTo: {to}\nSubject: {sub_enc}\nMIME-Version: 1.0\nContent-Type: text/html; charset=UTF-8\nContent-Transfer-Encoding: base64\n\n{base64.b64encode(html.encode("utf-8")).decode("utf-8")}'
    encoded = base64.urlsafe_b64encode(msg.encode("utf-8")).decode("utf-8")
    service.users().messages().send(userId='me', body={'raw': encoded}).execute()

def build_otp_email_html(otp, device_name, email):
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;background:#f8fafc;padding:20px;border-radius:12px">
        <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:24px;border-radius:12px 12px 0 0;text-align:center">
            <h1 style="color:#fff;margin:0;font-size:22px">🔐 Xác thực đăng nhập</h1>
        </div>
        <div style="background:#fff;padding:28px 24px;border-radius:0 0 12px 12px">
            <p style="color:#475569;font-size:14px;margin:0 0 16px">Thiết bị đang đăng nhập vào tài khoản <b>{email}</b>:</p>
            <div style="background:#f1f5f9;border-radius:10px;padding:14px 18px;margin-bottom:20px"><b>{device_name}</b></div>
            <div style="text-align:center;margin:24px 0">
                <div style="display:inline-block;background:linear-gradient(135deg,#4f46e5,#7c3aed);padding:18px 36px;border-radius:12px">
                    <div style="color:#fff;font-size:36px;font-weight:900;letter-spacing:8px;">{otp}</div>
                </div>
            </div>
        </div>
    </div>
    """

@app.route('/api/delete-user', methods=['POST', 'OPTIONS'])
def delete_user():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not FIREBASE_READY: return jsonify({"success": False, "error": "Firebase chưa cấu hình"}), 503
    data = request.json or {}
    email = data.get('email')
    if not email: return jsonify({"success": False, "error": "Thiếu email"}), 400
    email_clean = email.strip().lower()
    try:
        db = firestore.client()
        deleted_auth, deleted_fs = False, False
        try:
            user_record = auth.get_user_by_email(email_clean)
            auth.delete_user(user_record.uid)
            deleted_auth = True
        except: pass
        doc_ref = db.collection('allowed_users').document(email_clean)
        if doc_ref.get().exists:
            doc_ref.delete()
            deleted_fs = True
        if not deleted_auth and not deleted_fs: return jsonify({"success": False, "error": f"Không tìm thấy user {email_clean}"}), 404
        return jsonify({"success": True, "message": f"Đã xóa user {email_clean}"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/device/send-otp', methods=['POST', 'OPTIONS'])
def send_otp():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if otp_collection is None: return jsonify({'ok': False, 'error': 'OTP service chưa sẵn sàng'}), 503
    try:
        data = request.get_json(force=True, silent=True) or {}
        email, did, dname = data.get('email', ''), data.get('deviceId', 'unknown'), data.get('deviceName', 'Thiết bị')
        if not email or '@' not in email: return jsonify({'ok': False, 'error': 'Email không hợp lệ'}), 400
        el = email.lower().strip()
        now = datetime.utcnow()
        if el in last_sent_map and (now - last_sent_map[el]).total_seconds() < 60:
            wait = int(60 - (now - last_sent_map[el]).total_seconds())
            return jsonify({'ok': False, 'error': f'Vui lòng đợi {wait} giây', 'waitSec': wait}), 429
        otp_collection.delete_many({'email': el})
        otp = str(random.randint(100000, 999999))
        otp_collection.insert_one({'email': el, 'otp': otp, 'deviceId': did, 'deviceName': dname, 'attempts': 0, 'createdAt': now})
        send_gmail_html(el, 'Your OTP Verification Code', build_otp_email_html(otp, dname, el))
        last_sent_map[el] = now
        return jsonify({'ok': True, 'message': 'Đã gửi mã OTP'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/device/verify-otp', methods=['POST'])
def verify_otp():
    if otp_collection is None: return jsonify({'ok': False, 'error': 'OTP service chưa sẵn sàng'}), 503
    try:
        data = request.get_json(force=True, silent=True) or {}
        email, otp = data.get('email', ''), data.get('otp', '')
        if not email or not otp: return jsonify({'ok': False, 'error': 'Thiếu email hoặc OTP'}), 400
        el = email.lower().strip()
        record = otp_collection.find_one({'email': el}, sort=[('createdAt', -1)])
        if not record: return jsonify({'ok': False, 'error': 'OTP không tồn tại hoặc đã hết hạn'}), 400
        if datetime.utcnow() - record['createdAt'] > timedelta(minutes=10):
            otp_collection.delete_many({'email': el})
            return jsonify({'ok': False, 'error': 'OTP đã hết hạn'}), 400
        if record.get('attempts', 0) >= 5:
            otp_collection.delete_many({'email': el})
            return jsonify({'ok': False, 'error': 'Quá nhiều lần thử'}), 429
        if str(record['otp']) != str(otp).strip():
            otp_collection.update_one({'_id': record['_id']}, {'$inc': {'attempts': 1}})
            return jsonify({'ok': False, 'error': 'Mã OTP không đúng', 'attemptsLeft': 5 - (record.get('attempts', 0) + 1)}), 400
        otp_collection.delete_many({'email': el})
        return jsonify({'ok': True, 'message': 'Xác thực thành công'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/check', methods=['POST', 'OPTIONS'])
def check():
    if request.method == 'OPTIONS': return jsonify({}), 200
    try:
        data = request.get_json(force=True, silent=True) or {}
        u, c = data.get('user_answer', ''), data.get('correct_answer', '')
        if not c: return jsonify({'error': 'Missing correct_answer'}), 400
        return jsonify(grade(u, c))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test')
def test_get():
    u, c = request.args.get('u', ''), request.args.get('c', '')
    if not c: return jsonify({'error': 'Thieu tham so c', 'usage': 'Them ?u=...&c=...'})
    return jsonify(grade(u, c))

@app.route('/analyze', methods=['POST', 'OPTIONS'])
def analyze():
    if request.method == 'OPTIONS': return jsonify({}), 200
    try:
        data = request.get_json(force=True, silent=True) or {}
        char = data.get('char', '').strip()
        if not char or len(char) != 1: return jsonify({'ok': False, 'error': 'Invalid char'}), 400
        res = analyze_char(char)
        if res: return jsonify({'ok': True, 'data': res})
        else: return jsonify({'ok': False, 'error': 'Not found', 'char': char}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'char': char}), 200

@app.route('/vocab_test')
def vocab_test():
    ch = request.args.get('char', '').strip()
    res = analyze_char(ch)
    return jsonify({'ok': True, 'data': res}) if res else jsonify({'ok': False, 'error': 'Not found'}), 500

@app.route('/api/admin/export-excel', methods=['GET', 'POST'])
def export_excel():
    EXCEL_PATH = "data/tu_vung_hsk.xlsx"
    OUTPUT_PATH = "data/vocab_meanings.json"
    if not os.path.exists(EXCEL_PATH): return jsonify({"success": False, "error": f"Không tìm thấy {EXCEL_PATH}"}), 404
    try:
        wb = load_workbook(EXCEL_PATH, data_only=True, read_only=True)
        result = {}
        for sheet_name in wb.sheetnames:
            if not sheet_name.upper().startswith("HSK"): continue
            ws = wb[sheet_name]
            is_hsk79 = any(x in sheet_name for x in ['7', '8', '9'])
            col_zh, col_vi = 1, (4 if is_hsk79 else 5)
            for row in ws.iter_rows(min_row=3, values_only=True):
                if not row or len(row) <= col_vi: continue
                zh = str(row[col_zh]).strip() if row[col_zh] else ""
                vi = str(row[col_vi]).strip() if len(row) > col_vi and row[col_vi] else ""
                if zh and vi and zh not in result: result[zh] = vi
        wb.close()
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f: json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
        _do_load_vocab_meanings()
        return jsonify({"success": True, "message": f"Đã xuất {len(result)} từ vựng"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
# PHẦN 7: TRANSLATE API (PHÂN QUYỀN TOKEN & BẢO LƯU BONUS)
# ==========================================================
QWEN_API_KEY = os.environ.get("DASHCOPE_API_KEY") 
QWEN_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"

VIETNAMESE_ABBREVIATIONS = {
    r'\bTTXVN\b': 'Thông tấn xã Việt Nam',
    r'\bVTV\b': 'Đài Truyền hình Việt Nam',
    r'\bVOV\b': 'Đài Tiếng nói Việt Nam',
    r'\bTP\.?HCM\b': 'Thành phố Hồ Chí Minh',
    r'\bUBND\b': 'Ủy ban nhân dân',
    r'\bHĐND\b': 'Hội đồng nhân dân',
    r'\bBCT\b': 'Bộ Công Thương',
    r'\bBTC\b': 'Bộ Tài chính',
    r'\bBYT\b': 'Bộ Y tế',
    r'\bBGDĐT\b': 'Bộ Giáo dục và Đào tạo',
    r'\bBCA\b': 'Bộ Công an',
    r'\bBQP\b': 'Bộ Quốc phòng',
    r'\bTCT\b': 'Tổng cục Thuế',
    r'\bXNK\b': 'Xuất nhập khẩu',
    r'\bOCOP\b': 'Mỗi xã một sản phẩm',
}

@app.route('/api/translate', methods=['POST', 'OPTIONS'])
def translate():
    if request.method == 'OPTIONS': 
        return jsonify({}), 200
    if not FIREBASE_READY: 
        return jsonify({"error": "Firebase chưa cấu hình"}), 503
    
    data = request.json or {}
    text = data.get('text')
    source = data.get('source', 'vi')
    target = data.get('target', 'zh-CN')
    email = data.get('email')

    if not text or not email:
        return jsonify({"error": "Thiếu dữ liệu (text hoặc email)"}), 400

    try:
        db = firestore.client()
        user_ref = db.collection('allowed_users').document(email)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            return jsonify({"error": "Tài khoản không tồn tại"}), 404
            
        user_data = user_doc.to_dict()
        email_clean = email.strip().lower()
        
        raw_role = user_data.get('role')
        tier = user_data.get('tier')
        
        if email_clean == 'esp32.hotro@gmail.com' or tier == 'active':
            role = 'active'
        else:
            role = str(raw_role or tier or 'trial').strip().lower()
        
        expires_at = user_data.get('expiresAt')
        is_expired = False
        if expires_at:
            try:
                # ⭐ Sử dụng giờ VN để kiểm tra hết hạn
                now_vn = datetime.utcnow() + timedelta(hours=7)
                exp_date = expires_at if hasattr(expires_at, 'strftime') else datetime.strptime(str(expires_at)[:10], '%Y-%m-%d')
                if now_vn > exp_date:
                    is_expired = True
            except: 
                pass

        # ═══════════════════════════════════════════════════════
        # 1. TÍNH QUOTA VÀ RESET ĐỊNH KỲ
        # ═══════════════════════════════════════════════════════
        # ⭐ Tạo biến thời gian chuẩn VN dùng chung
        now_vn = datetime.utcnow() + timedelta(hours=7)

        if role == 'super_admin':
            quota = 999999999
            used = 0
        elif role == 'admin':
            quota = 20000
            today_str = now_vn.strftime('%Y-%m-%d') # Sửa thành giờ VN
            last_reset = user_data.get('lastTokenResetDate', '')
            used = user_data.get('tokensUsed', 0)
            if last_reset != today_str:
                used = 0
                user_ref.update({
                    'tokensUsed': 0,
                    'lastTokenResetDate': today_str,
                    'tokenQuota': 20000
                })
        elif role in ['trial', 'demo', 'user'] and is_expired:
            quota = 0
            used = user_data.get('tokensUsed', 0)
        else:
            quota = user_data.get('tokenQuota', 10000)
            current_month = now_vn.strftime('%Y-%m') # Sửa thành giờ VN
            last_reset_month = user_data.get('lastTokenResetMonth', '')
            used = user_data.get('tokensUsed', 0)
            
            if last_reset_month != current_month:
                used = 0
                user_ref.update({
                    'tokensUsed': 0,
                    'lastTokenResetMonth': current_month,
                    'tokenQuota': 10000
                })
                
        # ═══════════════════════════════════════════════════════
        # 2. TÍNH TOKEN KHẢ DỤNG (Bonus + Quota tháng còn lại)
        # ═══════════════════════════════════════════════════════
        bonus = user_data.get('bonusTokens', 0)
        monthly_remain = max(0, quota - used)
        total_available = monthly_remain + bonus
        
        if role != 'super_admin' and total_available <= 0:
            return jsonify({"error": "Tài khoản của bạn đã hết quota token, vui lòng nạp thêm để tiếp tục sử dụng!"}), 403

        # ═══════════════════════════════════════════════════════
        # 3. CHUẨN BỊ VĂN BẢN DỊCH
        # ═══════════════════════════════════════════════════════
        source_lang = 'Chinese' if source == 'zh-CN' else 'Vietnamese'
        target_lang = 'Vietnamese' if target == 'vi' else 'Chinese'
        
        processed_text = text
        if source == 'vi':
            for pattern, replacement in VIETNAMESE_ABBREVIATIONS.items():
                processed_text = re.sub(pattern, replacement, processed_text, flags=re.IGNORECASE)

        placeholders = {}
        def protect_english_words(match):
            word = match.group(0)
            ph = f"__ENG_{len(placeholders)}__"
            placeholders[ph] = word
            return ph

        protected_text = re.sub(r'\b[A-Z][a-z]+(?:\s*-\s*[A-Z][a-z]+)*\b|\b[A-Z]{2,4}\b', protect_english_words, processed_text)

        payload = {
            "model": "qwen-mt-flash",
            "messages": [{"role": "user", "content": protected_text}],
            "translation_options": {"source_lang": source_lang, "target_lang": target_lang}
        }
        headers = {"Authorization": f"Bearer {QWEN_API_KEY}", "Content-Type": "application/json"}
        
        res = requests.post(QWEN_URL, json=payload, headers=headers, timeout=25)
        res_data = res.json()
        if 'error' in res_data:
            return jsonify({"error": res_data['error']['message']}), 500
            
        translated_text = res_data['choices'][0]['message']['content']
        for ph, original in placeholders.items():
            translated_text = translated_text.replace(ph, original)

        # ═══════════════════════════════════════════════════════
        # 4. TRỪ TOKEN (ƯU TIÊN BONUS TRƯỚC, SAU ĐÓ MỚI QUOTA THÁNG)
        # ═══════════════════════════════════════════════════════
        tokens_used = res_data.get('usage', {}).get('total_tokens', 0)
        
        if role != 'super_admin' and tokens_used > 0:
            bonus_to_deduct = min(bonus, tokens_used)
            remaining_to_deduct = tokens_used - bonus_to_deduct
            
            update_data = {'lastTokenUsedAt': firestore.SERVER_TIMESTAMP}
            
            if bonus_to_deduct > 0:
                update_data['bonusTokens'] = firestore.Increment(-bonus_to_deduct)
            
            if remaining_to_deduct > 0:
                update_data['tokensUsed'] = firestore.Increment(remaining_to_deduct)
            
            user_ref.update(update_data)
            
            print(f"[Translate] Token dùng: {tokens_used} | "
                  f"Trừ bonus: {bonus_to_deduct} | "
                  f"Trừ quota: {remaining_to_deduct}")
            
        return jsonify({
            "translated": translated_text,
            "tokensUsed": tokens_used
        })

    except Exception as e:
        print(f"[Translate API] Lỗi: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ==========================================================
# PHẦN 8: LỊCH SỬ DỊCH (KIỂM TRA QUYỀN & GIỚI HẠN ĐỌC 250 / GHI 150)
# ==========================================================
@app.route('/api/history', methods=['POST', 'GET', 'OPTIONS'])
def history_api():
    if request.method == 'OPTIONS': 
        return jsonify({}), 200
        
    if not FIREBASE_READY: 
        return jsonify({"ok": False, "error": "Firebase chưa cấu hình"}), 503
    
    data = request.get_json(silent=True) or request.form or request.args or {}
    email = data.get('email') or request.args.get('email')
    
    if not email:
        return jsonify({"ok": False, "error": "Thiếu email"}), 400
        
    email_clean = email.strip().lower()
    db = firestore.client()
    history_ref = db.collection('translation_history')
    user_ref = db.collection('allowed_users').document(email_clean)
    
    # ⭐ KIỂM TRA QUYỀN CHÍNH XÁC TỪ FIRESTORE
    user_doc = user_ref.get()
    user_role = 'user'
    
    if user_doc.exists:
        ud = user_doc.to_dict()
        user_role = str(ud.get('role', 'user')).strip().lower()
    
    is_admin = (user_role in ['admin', 'super_admin', 'super-admin'])
    is_get_request = (request.method == 'GET') or (str(data.get('_method', '')).upper() == 'GET')
    
    # ⭐ XỬ LÝ LẤY LỊCH SỬ (GET)
    if is_get_request:
        try:
            # ⭐ Sử dụng giờ VN (GMT+7)
            now_vn = datetime.utcnow() + timedelta(hours=7)
            today_str = now_vn.strftime('%Y-%m-%d')
            
            user_data = user_doc.to_dict() if user_doc.exists else {}
            last_read_date = user_data.get('lastReadDate', '')
            read_count = user_data.get('historyReadToday', 0)
            
            if last_read_date != today_str:
                read_count = 0
                
            # ⭐ Chặn nếu user đã hết 250 lượt đọc trong ngày
            if not is_admin and read_count >= 250:
                return jsonify({
                    "ok": False, 
                    "error": "Bạn đã hết 250 lượt đọc lịch sử trong ngày hôm nay!",
                    "readRemain": 0
                }), 429

            docs = history_ref.where('email', '==', email_clean).stream()
            history_list = []
            today_start = now_vn.replace(hour=0, minute=0, second=0, microsecond=0)
            today_saved_count = 0
            
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                created_at = d.get('createdAt')
                
                if hasattr(created_at, 'strftime'):
                    d['createdAtStr'] = created_at.strftime('%Y-%m-%d %H:%M:%S')
                    d['sortTime'] = created_at.timestamp()
                    if created_at.replace(tzinfo=None) >= today_start:
                        today_saved_count += 1
                else:
                    d['createdAtStr'] = str(created_at or '')
                    d['sortTime'] = 0
                    
                d['createdAt'] = d['createdAtStr']
                history_list.append(d)
            
            # ⭐ SẮP XẾP THÔNG MINH (Đã sửa lỗi thụt lề)
            # 1. Tìm thời gian mới nhất của từng nhóm (groupId)
            group_latest_times = {}
            for d in history_list:
                gid = str(d.get('groupId', 'unknown'))
                t = d.get('sortTime', 0)
                if gid not in group_latest_times or t > group_latest_times[gid]:
                    group_latest_times[gid] = t
            
            # 2. Hàm sắp xếp: Ưu tiên nhóm mới nhất, sau đó đến STT tăng dần
            def smart_sort_key(d):
                gid = str(d.get('groupId', 'unknown'))
                group_time = group_latest_times.get(gid, 0)
                
                stt_str = str(d.get('stt', ''))
                stt_num = int(stt_str) if stt_str.isdigit() else 9999
                
                # Dấu âm (-) ở group_time để sắp xếp nhóm mới nhất lên đầu
                return (-group_time, stt_num)
                
            history_list.sort(key=smart_sort_key)
            
            if not is_admin:
                read_count += 1
                user_ref.set({
                    'historyReadToday': read_count,
                    'lastReadDate': today_str
                }, merge=True)
            
            # ⭐ Tính số lượt đọc còn lại dựa trên mốc 250
            read_remain = 999999 if is_admin else (250 - read_count)
            
            return jsonify({
                "ok": True, 
                "history": history_list[:150], # ⭐ Trả về tối đa 150 câu để khớp với giới hạn lưu
                "todayCount": today_saved_count,
                "readToday": read_count,
                "readRemain": read_remain,
                "isAdmin": is_admin
            })
            
        except Exception as e:
            traceback.print_exc()
            return jsonify({"ok": False, "error": str(e)}), 500

    # ⭐ XỬ LÝ LƯU LỊCH SỬ (POST)
    try:
        items = data.get('items')
        if not items:
            vi = data.get('text_vi', '')
            zh = data.get('text_zh', '')
            pinyin_str = data.get('pinyin', '')
            if vi or zh:
                items = [{'vi': vi, 'zh': zh, 'pinyin': pinyin_str}]
            else:
                return jsonify({"ok": False, "error": "Thiếu dữ liệu items"}), 400
                
        if isinstance(items, dict):
            items = [items]
            
        all_docs = list(history_ref.where('email', '==', email_clean).stream())
        
        # ⭐ Sử dụng giờ VN (GMT+7) để xác định "hôm nay"
        now_vn = datetime.utcnow() + timedelta(hours=7)
        today_start = now_vn.replace(hour=0, minute=0, second=0, microsecond=0)
        today_saved_count = 0
        
        for doc in all_docs:
            d = doc.to_dict()
            ca = d.get('createdAt')
            if ca and hasattr(ca, 'replace'):
                if ca.replace(tzinfo=None) >= today_start:
                    today_saved_count += 1

        # ⭐ Kiểm tra giới hạn lưu 150 câu/ngày
        if not is_admin:
            remaining_quota_today = 150 - today_saved_count
            if remaining_quota_today <= 0:
                return jsonify({"ok": False, "error": "Đã đạt giới hạn lưu 150 câu trong ngày!"}), 429
            items_to_save = items[:remaining_quota_today]
        else:
            items_to_save = items
        
        for item in items_to_save:
            history_ref.add({
                'email': email_clean,
                'stt': item.get('stt', ''),         # ⭐ Lưu STT
                'groupId': item.get('groupId', ''), # ⭐ Lưu Group ID
                'text_vi': item.get('vi') or item.get('text_vi', ''),
                'text_zh': item.get('zh') or item.get('text_zh', ''),
                'pinyin': item.get('pinyin', ''),
                'createdAt': firestore.SERVER_TIMESTAMP
            })
            
        # Giới hạn số câu lưu trữ tối đa trong Firestore
        if len(all_docs) >= 150:
            def get_doc_time(doc):
                ca = doc.to_dict().get('createdAt')
                return ca.timestamp() if hasattr(ca, 'timestamp') else 0
                
            all_docs.sort(key=get_doc_time, reverse=True)
            for old_doc in all_docs[149:]:
                old_doc.reference.delete()
                
        return jsonify({"ok": True, "saved": len(items_to_save)})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
@app.route('/api/user/check-token', methods=['POST', 'OPTIONS'])
def check_token():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not FIREBASE_READY: return jsonify({"error": "Firebase chưa cấu hình"}), 503
    
    data = request.json or {}
    email = data.get('email')
    if not email: return jsonify({"error": "Thiếu email"}), 400

    try:
        db = firestore.client()
        email_clean = email.strip().lower()
        user_ref = db.collection('allowed_users').document(email_clean)
        user_doc = user_ref.get()
        
        if not user_doc.exists: return jsonify({"error": "Tài khoản không tồn tại"}), 404
            
        user_data = user_doc.to_dict()
        raw_role = user_data.get('role')
        tier = user_data.get('tier')
        
        if email_clean == 'esp32.hotro@gmail.com' or tier == 'active':
            role = 'active'
        else:
            role = str(raw_role or tier or 'trial').strip().lower()
            
        expires_at = user_data.get('expiresAt')
        is_expired = False
        if expires_at:
            try:
                now_vn = datetime.utcnow() + timedelta(hours=7)
                exp_date = expires_at if hasattr(expires_at, 'strftime') else datetime.strptime(str(expires_at)[:10], '%Y-%m-%d')
                if now_vn > exp_date: is_expired = True
            except: pass

        now_vn = datetime.utcnow() + timedelta(hours=7)
        
        if role == 'super_admin':
            quota = 999999999
            used = 0
        elif role == 'admin':
            quota = 20000
            today_str = now_vn.strftime('%Y-%m-%d')
            last_reset = user_data.get('lastTokenResetDate', '')
            used = user_data.get('tokensUsed', 0)
            if last_reset != today_str:
                used = 0
                user_ref.update({'tokensUsed': 0, 'lastTokenResetDate': today_str, 'tokenQuota': 20000})
        elif role in ['trial', 'demo', 'user'] and is_expired:
            quota = 0
            used = user_data.get('tokensUsed', 0)
        else:
            quota = user_data.get('tokenQuota', 10000)
            current_month = now_vn.strftime('%Y-%m')
            last_reset_month = user_data.get('lastTokenResetMonth', '')
            used = user_data.get('tokensUsed', 0)
            if last_reset_month != current_month:
                used = 0
                user_ref.update({'tokensUsed': 0, 'lastTokenResetMonth': current_month, 'tokenQuota': 10000})
                
        bonus = user_data.get('bonusTokens', 0)
        
        return jsonify({
            "ok": True,
            "role": role,
            "quota": quota,
            "bonus": bonus,
            "used": used,
            "lastTokenResetDate": user_data.get('lastTokenResetDate', ''),
            "lastTokenResetMonth": user_data.get('lastTokenResetMonth', '')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/admin/approve-token', methods=['POST', 'OPTIONS'])
def approve_token():
    if request.method == 'OPTIONS': return jsonify({}), 200
    if not FIREBASE_READY: return jsonify({"error": "Firebase chưa cấu hình"}), 503
    
    data = request.json or {}
    admin_email = data.get('admin_email')
    target_email = data.get('target_email')
    amount = int(data.get('amount', 0))
    password = data.get('password') # Pass do Admin nhập từ giao diện

    # ⭐ Lấy Pass bí mật từ Server
    SERVER_PASS = os.environ.get("APPROVE_PASSWORD", "admin123")

    # ⭐ Kiểm tra Pass
    if password != SERVER_PASS:
        return jsonify({"error": "Mật khẩu duyệt không đúng! Thao tác bị từ chối."}), 403

    # Tiến hành cộng token
    db = firestore.client()
    user_ref = db.collection('allowed_users').document(target_email)
    if not user_ref.get().exists:
        return jsonify({"error": "Tài khoản cần nạp không tồn tại"}), 404
        
    user_ref.update({
        'bonusTokens': firestore.Increment(amount)
    })
    
    # (Tùy chọn) Bạn có thể lưu lại lịch sử ai đã duyệt
    print(f"[Approve] Admin {admin_email} đã duyệt {amount} token cho {target_email}")
    
    return jsonify({"ok": True, "message": f"Đã duyệt thành công {amount} token!"})

@app.route('/health')
def health():
    return jsonify({
        'ok': True,
        'model_loaded': _corrector is not None,
        'firebase': FIREBASE_READY,
        'mongo': otp_collection is not None,
        'has_vocab': HAS_VOCAB
    })

@app.route('/warmup')
def warmup():
    get_corrector()
    return jsonify({'ok': True, 'loaded': _corrector is not None})

@app.route('/')
def index():
    return jsonify({'name': 'Mega API 5-in-1', 'version': '7.9-Batch-History', 'status': 'Running'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
