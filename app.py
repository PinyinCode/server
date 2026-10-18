# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
from pypinyin import pinyin, Style
import re, os, sys, json, random, base64, threading, traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)
CORS(app)

# ==========================================================
# PHẦN 1: SETUP (Firebase, MongoDB, Gmail OAuth2)
# ==========================================================
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import firebase_admin
from firebase_admin import credentials, auth, firestore
from pymongo import MongoClient

firebase_json_str = os.environ.get("FIREBASE_CREDENTIALS_JSON")
if firebase_json_str:
    try:
        cred = credentials.Certificate(json.loads(firebase_json_str))
        firebase_admin.initialize_app(cred)
    except Exception as e: print("Firebase env error:", e)
elif os.path.exists("serviceAccountKey.json"):
    try:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    except Exception as e: print("Firebase file error:", e)

MONGO_URI = os.environ.get("MONGODB_URI")
mongo_client = MongoClient(MONGO_URI) if MONGO_URI else None
otp_collection = mongo_client["test"]["otpcodes"] if mongo_client else None
last_sent_map = {}
OTP_COOLDOWN_SECONDS = 60

# ==========================================================
# PHẦN 2: VOCAB ANALYSIS (Từ vocab_api.py)
# ==========================================================
HAS_VOCAB = False
try:
    from vocab_data.radical_analyzer import _split_components, get_radical_for_word
    from vocab_data.mnemonic_generator import generate_mnemonic
    HAS_VOCAB = True
except Exception as e: print("Vocab load error:", e)

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
        if len(parts) == 3 and parts[2].strip():
            idx[parts[2].strip()] = v
    return idx

def _do_load_ai_mnemonics():
    global _AI_MNEMONICS, _AI_MNEMONICS_INDEX
    path = _find_ai_mnemonics_file()
    if not path: return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _AI_MNEMONICS = data
        _AI_MNEMONICS_INDEX = _build_ai_index(data)
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

_do_load_ai_mnemonics()
_do_load_vocab_meanings()
_do_load_similar_chars()

def get_similar_chars(char):
    if not char: return [], ""
    entry = _SIMILAR_CHARS.get(char)
    if not entry: return [], ""
    if isinstance(entry, list): return [str(c).strip() for c in entry if c], ""
    if isinstance(entry, dict):
        return [str(c).strip() for c in entry.get('similar', []) if c], entry.get('diff', '')
    return [], ""

def get_pinyin(char):
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
        result = {'char': char, 'pinyin': get_pinyin(char)}
        vi = get_meaning(char)
        if vi: result['vi'] = vi
        main_rad = get_radical_for_word(char)
        if main_rad: result['radical'] = main_rad
        comps = _split_components(char)
        if comps: result['components'] = comps[:8]
        mnemonic = get_ai_mnemonic(char) or generate_mnemonic(char)
        if mnemonic: result['mnemonic'] = mnemonic
        sim_chars, diff_text = get_similar_chars(char)
        if sim_chars:
            result['similar'] = {
                'list': [{'char': c, 'pinyin': get_pinyin(c), 'meaning': get_meaning(c)} for c in sim_chars if len(c)==1],
                'diff': diff_text
            }
        return result
    except: return None

# ==========================================================
# PHẦN 3: CHẤM ĐIỂM (Từ app.py gốc - KHÔI PHỤC 100%)
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
            print("Load failed:", e)
            _corrector_failed = True
            return None

def clean(text):
    if not text: return ''
    return re.sub(r'[。，！？、；：""''「」『』（）《》〈〉【】〔〕\s]+', '', str(text))

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
        except Exception as e: print("Correct error:", e)

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
        'score': round(ratio * 100),
        'status': status,
        'message': message,
        'errors': errors,
        'suggestion': correct_answer if u != c else None,
        'used_ai': used_ai
    }

# ==========================================================
# PHẦN 4: GỬI OTP & XÓA USER (Giữ nguyên)
# ==========================================================
def send_gmail_oauth2(to_email, subject, html_content):
    client_id, client_secret = os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token, sender_email = os.environ.get("GOOGLE_REFRESH_TOKEN"), os.environ.get("GOOGLE_SENDER_EMAIL")
    if not all([client_id, client_secret, refresh_token, sender_email]): raise Exception("Thiếu OAuth2 config")
    creds = Credentials(None, refresh_token=refresh_token, client_id=client_id, client_secret=client_secret, token_uri="https://oauth2.googleapis.com/token")
    service = build('gmail', 'v1', credentials=creds)
    subject_encoded = "=?UTF-8?B?" + base64.b64encode(subject.encode('utf-8')).decode('utf-8') + "?="
    message_parts = [f'From: "Account Verification" <{sender_email}>', f'To: {to_email}', f'Subject: {subject_encoded}', 'MIME-Version: 1.0', 'Content-Type: text/html; charset=UTF-8', 'Content-Transfer-Encoding: base64', '', base64.b64encode(html_content.encode('utf-8')).decode('utf-8')]
    raw_message = '\n'.join(message_parts)
    encoded_message = base64.urlsafe_b64encode(raw_message.encode('utf-8')).decode('utf-8')
    service.users().messages().send(userId='me', body={'raw': encoded_message}).execute()

@app.route('/api/device/send-otp', methods=['POST'])
def send_otp():
    try:
        data = request.get_json(force=True, silent=True) or {}
        email, device_id, device_name = data.get('email', ''), data.get('deviceId', 'unknown'), data.get('deviceName', 'Thiết bị')
        if not email or '@' not in email: return jsonify({'ok': False, 'error': 'Email không hợp lệ'}), 400
        if otp_collection is None: return jsonify({'ok': False, 'error': 'OTP service chưa sẵn sàng'}), 503
        email_lower = email.lower().strip()
        now = datetime.utcnow()
        if email_lower in last_sent_map and (now - last_sent_map[email_lower]).total_seconds() < OTP_COOLDOWN_SECONDS:
            return jsonify({'ok': False, 'error': 'Vui lòng đợi trước khi gửi lại'}), 429
        otp = str(random.randint(100000, 999999))
        otp_collection.delete_many({'email': email_lower})
        otp_collection.insert_one({'email': email_lower, 'otp': otp, 'attempts': 0, 'createdAt': now})
        html = f"<h3>Mã OTP của bạn là:</h3><h1>{otp}</h1><p>Thiết bị: {device_name}</p>"
        send_gmail_oauth2(email_lower, 'OTP Verification', html)
        last_sent_map[email_lower] = now
        return jsonify({'ok': True, 'message': 'Đã gửi mã OTP'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/device/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json(force=True, silent=True) or {}
        email, otp = data.get('email', ''), data.get('otp', '')
        if not email or not otp: return jsonify({'ok': False, 'error': 'Thiếu email hoặc OTP'}), 400
        if otp_collection is None: return jsonify({'ok': False, 'error': 'Database chưa sẵn sàng'}), 500
        email_lower = email.lower().strip()
        record = otp_collection.find_one({'email': email_lower}, sort=[('createdAt', -1)])
        if not record or str(record['otp']) != str(otp).strip():
            return jsonify({'ok': False, 'error': 'Mã OTP không đúng hoặc hết hạn'}), 400
        otp_collection.delete_many({'email': email_lower})
        last_sent_map.pop(email_lower, None)
        return jsonify({'ok': True, 'message': 'Xác thực thành công'})
    except Exception as e: return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/delete-user', methods=['POST'])
def delete_user():
    data = request.json or {}
    email = data.get('email')
    if not email: return jsonify({"success": False, "error": "Thiếu email"}), 400
    email_clean = email.strip().lower()
    try:
        db_fs = firestore.client()
        try:
            user_record = auth.get_user_by_email(email_clean)
            auth.delete_user(user_record.uid)
        except: pass
        doc_ref = db_fs.collection('allowed_users').document(email_clean)
        if doc_ref.get().exists: doc_ref.delete()
        return jsonify({"success": True, "message": f"Đã xóa user {email_clean}"})
    except Exception as e: return jsonify({"success": False, "error": str(e)}), 500

# ==========================================================
# PHẦN 5: ROUTES CHÍNH (TÁCH BIỆT HOÀN TOÀN)
# ==========================================================

@app.route('/health')
def health():
    return jsonify({'ok': True, 'model_loaded': _corrector is not None, 'model_failed': _corrector_failed, 'has_vocab': HAS_VOCAB})

@app.route('/warmup')
def warmup():
    get_corrector()
    return jsonify({'ok': True, 'loaded': _corrector is not None})

# Route /check giữ nguyên như file gốc
@app.route('/check', methods=['POST'])
def check():
    try:
        data = request.get_json(force=True, silent=True) or {}
        u, c = data.get('user_answer', ''), data.get('correct_answer', '')
        if not c: return jsonify({'error': 'Missing correct_answer'}), 400
        return jsonify(grade(u, c))
    except Exception as e: return jsonify({'error': str(e)}), 500

# Route /test giữ nguyên như file gốc (chỉ chấm điểm)
@app.route('/test')
def test_get():
    u, c = request.args.get('u', ''), request.args.get('c', '')
    if not c:
        return jsonify({'error': 'Thieu tham so c', 'usage': 'Them ?u=cau_user&c=cau_dung'})
    return jsonify(grade(u, c))

# Route /analyze tách riêng ra, không dùng chung /test nữa
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json(force=True, silent=True) or {}
        char = data.get('char', '').strip()
        if not char or len(char) != 1: return jsonify({'ok': False, 'error': 'Invalid char'}), 400
        res = analyze_char(char)
        return jsonify({'ok': True, 'data': res}) if res else jsonify({'ok': False, 'error': 'Not found'}), 500
    except Exception as e: return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/')
def index():
    return jsonify({
        'name': 'Chinese Grading API',
        'version': '4.1-fixed-merge',
        'endpoints': {
            'health': '/health', 'check': 'POST /check', 'test': '/test?u=...&c=...',
            'analyze': 'POST /analyze', 'send_otp': 'POST /api/device/send-otp'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
