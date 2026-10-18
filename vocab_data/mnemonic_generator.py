# -*- coding: utf-8 -*-
r"""
Sinh mẹo nhớ chữ Hán tự động.

NÂNG CẤP (2026-10-03):
  - Mở rộng RADICAL_STORIES lên ĐẦY ĐỦ 214 bộ thủ Khang Hy
  - Câu chuyện dễ nhớ, có hình ảnh liên tưởng
  - Hỗ trợ TỪ GHÉP (2+ chữ) — phân tích từng chữ rồi ghép nghĩa
  - Ưu tiên cjkradlib cho bộ thủ chính xác
  - Mở rộng SOUND_HINTS lên 300+ âm
"""

import unicodedata
import re

from .radical_analyzer import analyze_word, _split_components
import json
import os

# ═══════════════════════════════════════════════════════════════
#  ⭐ LOAD SIMILAR CHARS (2 files)
# ═══════════════════════════════════════════════════════════════
SIMILAR_CHARS = {}

def _load_similar_chars():
    global SIMILAR_CHARS
    SIMILAR_CHARS = {}
    
    base_dir = os.path.dirname(__file__)
    
    # File 1: HSK 1-4
    p1 = os.path.join(base_dir, "similar_chars.json")
    if os.path.exists(p1):
        try:
            with open(p1, "r", encoding="utf-8") as f:
                data = json.load(f)
                SIMILAR_CHARS.update(data)
            print("[MNEMONIC] Loaded part1: " + str(len(data)) + " chars")
        except Exception as e:
            print("[MNEMONIC] Load part1 error: " + str(e))
    
    # File 2: HSK 5-6
    p2 = os.path.join(base_dir, "similar_chars_part2.json")
    if os.path.exists(p2):
        try:
            with open(p2, "r", encoding="utf-8") as f:
                data = json.load(f)
                SIMILAR_CHARS.update(data)
            print("[MNEMONIC] Loaded part2: " + str(len(data)) + " chars")
        except Exception as e:
            print("[MNEMONIC] Load part2 error: " + str(e))
    
    print("[MNEMONIC] Total similar chars: " + str(len(SIMILAR_CHARS)))

_load_similar_chars()


def find_similar_chars(char):
    """Tìm chữ gần giống từ cache."""
    if not char:
        return None
    return SIMILAR_CHARS.get(char)


# ═══════════════════════════════════════════════════════════════
#  NGÂN HÀNG CÂU CHUYỆN CHO 214 BỘ THỦ KHANG HY
#  Đầy đủ + câu chuyện dễ nhớ cho người Việt
# ═══════════════════════════════════════════════════════════════
RADICAL_STORIES = {
    # ═══════════════ 1 NÉT ═══════════════
    "一": "một nét ngang — khởi đầu của mọi thứ",
    "丨": "một nét sổ — cây cột thẳng đứng",
    "丶": "một chấm nhỏ — giọt nước rơi",
    "丿": "một nét phẩy — cánh chim nghiêng",
    "乙": "hình chữ chi — con chim én lượn",
    "亅": "một nét móc — cái móc treo",

    # ═══════════════ 2 NÉT ═══════════════
    "二": "hai nét ngang — số hai, đôi",
    "亠": "nét chấm trên đầu — cái nắp, mái che",
    "人": "hai chân người — con người đứng",
    "亻": "người đứng nghiêng — người làm việc",
    "儿": "hai chân trẻ con — em bé đang chạy",
    "入": "người bước vào — vào trong nhà",
    "八": "hai cánh tay dang ra — số tám",
    "冂": "khung rỗng — biên giới, vùng đất",
    "冖": "mái che — cái nắp đậy lên",
    "冫": "hai giọt nước đóng băng — băng giá",
    "几": "cái ghế nhỏ — chỗ dựa",
    "凵": "hộp mở miệng — cái hộp đựng",
    "刀": "con dao sắc bén — vũ khí cắt",
    "刂": "dao đứng bên phải — lưỡi dao cắt",
    "力": "cánh tay gồng — sức mạnh cơ bắp",
    "勹": "tay ôm trọn — bao bọc che chở",
    "匕": "cái thìa múc — dụng cụ ăn",
    "匚": "hộp ngang — cái hộp đựng đồ",
    "匸": "hộp che giấu — nơi cất giấu",
    "十": "chữ thập — mười, đầy đủ",
    "卜": "vết nứt trên mai rùa — bói toán",
    "卩": "dấu ấn — con dấu xác nhận",
    "厂": "sườn núi dốc — vách đá che",
    "厶": "vòng tròn riêng — sở hữu cá nhân",
    "又": "bàn tay phải — lại, thêm một lần nữa",

    # ═══════════════ 3 NÉT ═══════════════
    "口": "cái miệng mở — nơi nói ra lời",
    "囗": "vòng vây quanh — thành trì bao quanh",
    "土": "đất đai màu mỡ — nền tảng vững chắc",
    "士": "kẻ có học — người trí thức",
    "夂": "chân bước chậm — đi chậm rãi",
    "夊": "chân bước khoan thai — đi thư thả",
    "夕": "ánh chiều tà — buổi hoàng hôn",
    "大": "người dang hai tay — to lớn, vĩ đại",
    "女": "người phụ nữ ngồi — nữ giới",
    "子": "đứa trẻ sơ sinh — con cái",
    "宀": "mái nhà che — ngôi nhà ấm áp",
    "寸": "đốt tay đo — tấc, đơn vị nhỏ",
    "小": "ba chấm nhỏ — nhỏ bé, tí hon",
    "尢": "người yếu chân — tàn tật, yếu ớt",
    "尸": "xác người nằm — thể xác, thân xác",
    "屮": "mầm cây nhú — sự sống sinh sôi",
    "山": "ba đỉnh núi — núi non hùng vĩ",
    "巛": "dòng nước uốn lượn — sông ngòi",
    "工": "cây cột chống — công việc lao động",
    "己": "con rắn cuộn tròn — bản thân mình",
    "巾": "tấm vải treo — khăn vải, y phục",
    "干": "cây gậy thẳng — khô ráo, can thiệp",
    "幺": "sợi tơ nhỏ — nhỏ bé, út",
    "广": "mái nhà rộng — ngôi nhà lớn, quảng trường",
    "廴": "bước dài — đi xa, bước rộng",
    "廾": "hai tay chắp lên — nâng đỡ kính trọng",
    "弋": "cây gậy có móc — bắn, bắt được",
    "弓": "cây cung uốn — bắn tên, uốn cong",
    "彐": "đầu con heo — hình đầu thú",
    "彡": "sợi lông bay — lông dài, vệt sáng",
    "彳": "bước chân trái — bước đi, con đường",

    # ═══════════════ 4 NÉT ═══════════════
    "心": "trái tim đập — tình cảm, cảm xúc",
    "忄": "tim đứng cạnh — cảm xúc trào dâng",
    "戈": "cây giáo dài — vũ khí chiến tranh",
    "戶": "cánh cửa nhà — cửa ra vào",
    "手": "bàn tay xòe — lao động, làm việc",
    "扌": "tay bên trái — chạm, nắm, giữ",
    "支": "cành cây chống — chống đỡ, nhánh",
    "攴": "tay cầm gậy — đánh nhẹ, sửa chữa",
    "文": "hoa văn chữ — văn chương, văn hóa",
    "斗": "cái đấu đo — đơn vị đo lường",
    "斤": "cái rìu cắt — đơn vị cân, búa",
    "方": "bốn cánh hướng — phương hướng, vuông vắn",
    "无": "không có gì — trống rỗng, vô hình",
    "日": "mặt trời tròn — ngày, ánh sáng",
    "曰": "miệng nói — nói rằng, cho biết",
    "月": "mặt trăng khuyết — tháng, trăng sáng",
    "木": "cây cổ thụ — cây cối, gỗ",
    "欠": "người ngáp — thiếu thốn, nợ nần",
    "止": "chân dừng lại — dừng, ngừng nghỉ",
    "歹": "xương tàn — xấu xa, chết chóc",
    "殳": "tay cầm gậy — binh khí, đánh",
    "毋": "chớ làm — cấm đoán, đừng",
    "比": "hai người cạnh nhau — so sánh",
    "毛": "sợi lông mảnh — lông tóc, mao",
    "氏": "dòng họ — gia tộc, thị tộc",
    "气": "hơi nước bốc — không khí, hơi thở",
    "水": "dòng nước chảy — nước, sông suối",
    "氵": "ba giọt nước — nước, chất lỏng",
    "火": "ngọn lửa cháy — lửa, sức nóng",
    "灬": "bốn đốm lửa — lửa bùng lên",
    "爪": "móng vuốt — bàn tay, nắm bắt",
    "爫": "tay chụp xuống — nắm bắt, che chở",
    "父": "người cha — cha, gia trưởng",
    "爻": "giao thoa — quẻ hào, biến đổi",
    "爿": "mảnh gỗ bổ — mảnh gỗ, giường",
    "片": "miếng mỏng — miếng, mảnh",
    "牙": "răng nanh — răng, hàm răng",
    "牛": "con bò cày — trâu bò, sức kéo",
    "犬": "con chó canh — chó, thú nuôi",
    "犭": "chó đứng cạnh — loài thú, chó",

    # ═══════════════ 5 NÉT ═══════════════
    "玄": "sợi tơ huyền bí — huyền bí, sâu xa",
    "玉": "viên ngọc quý — ngọc, đá quý",
    "王": "vua cầm ngọc — vua chúa, vương giả",
    "瓜": "quả dưa leo — dưa, bầu bí",
    "瓦": "viên ngói nung — ngói, gốm",
    "甘": "vị ngọt đầu lưỡi — ngọt, cam",
    "生": "mầm cây mọc — sinh ra, sự sống",
    "用": "cái chuông dùng — dùng, sử dụng",
    "田": "thửa ruộng vuông — ruộng đất, đồng",
    "疋": "chân người bước — chân, đơn vị đo",
    "疒": "người nằm bệnh — bệnh tật",
    "癶": "hai chân gạt ra — gạt, đẩy ra",
    "白": "ánh sáng trắng — trắng, sáng tỏ",
    "皮": "da thú — da, vỏ ngoài",
    "皿": "đồ đựng — bát đĩa, đồ đựng",
    "目": "con mắt ngang — mắt, nhìn",
    "矛": "cây giáo nhọn — giáo, vũ khí",
    "矢": "mũi tên — tên, đơn vị đo",
    "石": "hòn đá cứng — đá, cứng rắn",
    "示": "bàn thờ tổ tiên — chỉ bảo, hiển thị",
    "礻": "bàn thờ cạnh — thờ cúng, tín ngưỡng",
    "禸": "dấu chân thú — vết chân, dấu vết",
    "禾": "cây lúa chín — lúa, ngũ cốc",
    "穴": "hang động — hang, lỗ hổng",
    "立": "người đứng thẳng — đứng, lập nên",

    # ═══════════════ 6 NÉT ═══════════════
    "竹": "cây tre thẳng — tre, trúc",
    "⺮": "tre trên đầu — tre trúc, đồ tre",
    "米": "hạt gạo rơi — gạo, gạo thóc",
    "糸": "sợi tơ se — tơ lụa, sợi chỉ",
    "纟": "tơ bên trái — dệt may, chỉ",
    "缶": "đồ gốm nung — gốm, bình gốm",
    "网": "tấm lưới đan — lưới, bắt cá",
    "罒": "lưới trên đầu — lưới, bao phủ",
    "羊": "con cừu trắng — cừu, dê",
    "羽": "lông vũ bay — lông chim, cánh",
    "老": "người già chống gậy — già, lâu năm",
    "而": "chòm râu — mà, và",
    "耒": "cái cày gỗ — cày, nông cụ",
    "耳": "đôi tai nghe — tai, nghe",
    "聿": "cây bút viết — bút, viết",
    "肉": "miếng thịt — thịt, thân thể",
    "⺼": "thịt bên trái — bộ phận cơ thể",
    "臣": "bề tôi cúi đầu — bề tôi, thần tử",
    "自": "cái mũi chỉ mình — tự, bản thân",
    "至": "mũi tên cắm đất — đến, tới nơi",
    "臼": "cái cối giã — cối, giã gạo",
    "舌": "cái lưỡi thè — lưỡi, nếm",
    "舛": "hai chân ngược nhau — sai, trái ngược",
    "舟": "con thuyền nhỏ — thuyền, ghe",
    "艮": "quẻ Cấn — dừng lại, bền vững",
    "色": "khuôn mặt đỏ — màu sắc, vẻ mặt",
    "艸": "cỏ mọc — cỏ, thảo mộc",
    "艹": "cỏ trên đầu — cỏ cây, thực vật",
    "虍": "vằn hổ — hổ, dữ tợn",
    "虫": "con sâu bò — sâu bọ, côn trùng",
    "血": "dòng máu đỏ — máu, huyết",
    "行": "ngã tư đường — đi, hành động",
    "衣": "bộ quần áo — áo, y phục",
    "衤": "áo bên trái — áo quần, trang phục",
    "西": "phương tây — hướng tây, chim đậu",

    # ═══════════════ 7 NÉT ═══════════════
    "見": "con mắt nhìn — thấy, gặp",
    "见": "mắt nhìn thấy — thấy, gặp",
    "角": "sừng trâu nhọn — sừng, góc",
    "言": "lời nói ra — nói, ngôn ngữ",
    "讠": "lời nói bên trái — nói, ngôn từ",
    "谷": "thung lũng sâu — thung lũng, hạt lúa",
    "豆": "hạt đậu tròn — đậu, hạt",
    "豕": "con heo lông — heo, lợn",
    "豸": "loài sâu có xương — bọ, trùng",
    "貝": "vỏ sò quý — tiền, của cải",
    "贝": "vỏ sò tiền — tiền, tài sản",
    "赤": "màu đỏ lửa — đỏ, trần trụi",
    "走": "chân bước đi — đi, chạy",
    "足": "bàn chân đứng — chân, đầy đủ",
    "⻊": "chân bên trái — chân, bước đi",
    "身": "thân thể người — thân, cơ thể",
    "車": "chiếc xe lăn — xe, phương tiện",
    "车": "xe chạy — xe, di chuyển",
    "辛": "cay đắng — cay, vất vả",
    "辰": "giờ Thìn — giờ Thìn, buổi sớm",
    "辵": "bước đi xa — đi, di chuyển",
    "辶": "bước đi — đi, hành trình",
    "邑": "thành phố — thành, ấp",
    "⻏": "thành phố bên phải — thành trì, huyện",
    "⻖": "gò đất bên trái — đồi, gò",
    "酉": "bình rượu — rượu, giờ Dậu",
    "釆": "phân biệt hạt — phân biệt, chọn lọc",
    "里": "làng xóm — làng, dặm",

    # ═══════════════ 8 NÉT ═══════════════
    "金": "kim loại vàng — vàng, kim loại",
    "钅": "kim loại bên trái — sắt thép, kim khí",
    "長": "tóc dài — dài, trưởng thành",
    "长": "dài — dài, lớn lên",
    "門": "cửa hai cánh — cửa, cổng",
    "门": "cửa — cửa, cổng",
    "阜": "gò đất cao — đồi, gò đất",
    "隶": "nô lệ cúi — nô lệ, phục tùng",
    "隹": "chim đuôi ngắn — chim, loài chim",
    "雨": "cơn mưa rơi — mưa, nước trời",
    "⻗": "mưa trên đầu — mưa, thời tiết",
    "青": "màu xanh — xanh, trẻ trung",
    "非": "hai cánh ngược — không phải, sai",

    # ═══════════════ 9 NÉT ═══════════════
    "面": "khuôn mặt — mặt, diện mạo",
    "革": "da thuộc — da, cải cách",
    "韋": "da mềm — da mềm, bao quanh",
    "韭": "cây hẹ — hẹ, rau hẹ",
    "音": "âm thanh vang — âm thanh, tiếng",
    "頁": "trang giấy — trang, đầu",
    "页": "trang — trang, đầu",
    "風": "cơn gió thổi — gió, phong",
    "风": "gió — gió, phong cách",
    "飛": "chim bay — bay, phi",
    "飞": "bay — bay, phi",
    "食": "ăn uống — ăn, thức ăn",
    "饣": "thức ăn bên trái — ăn, món ăn",
    "首": "cái đầu — đầu, thủ lĩnh",
    "香": "mùi thơm — thơm, hương",

    # ═══════════════ 10+ NÉT ═══════════════
    "馬": "con ngựa phi — ngựa, mã",
    "马": "ngựa — ngựa, mã",
    "骨": "bộ xương — xương, cốt",
    "高": "cái tháp cao — cao, cao thượng",
    "髟": "tóc dài bay — tóc, lông",
    "鬥": "hai người đánh nhau — đánh nhau, đấu",
    "鬯": "rượu tế — rượu cúng tế",
    "鬲": "nồi đất ba chân — nồi, chảo",
    "鬼": "ma quỷ — ma, quỷ",
    "魚": "con cá bơi — cá, ngư",
    "鱼": "cá — cá, ngư",
    "鳥": "con chim bay — chim, điểu",
    "鸟": "chim — chim, điểu",
    "鹵": "đất mặn — muối, đất mặn",
    "鹿": "con hươu — hươu, nai",
    "麥": "cây lúa mạch — lúa mạch, mạch",
    "麦": "lúa mạch — lúa mạch, mạch",
    "麻": "cây gai — gai, tê liệt",
    "黃": "màu vàng — vàng, hoàng",
    "黄": "vàng — vàng, hoàng",
    "黍": "lúa nếp — lúa nếp, nếp",
    "黑": "màu đen — đen, hắc",
    "黹": "thêu thùa — thêu, chỉ",
    "黽": "con ếch — ếch, cóc",
    "鼎": "cái đỉnh đồng — đỉnh, vạc",
    "鼓": "cái trống — trống, cổ vũ",
    "鼠": "con chuột — chuột, thử",
    "鼻": "cái mũi — mũi, khứu giác",
    "齊": "bằng phẳng — đều, ngang",
    "齿": "răng — răng, xỉ",
    "龍": "con rồng — rồng, long",
    "龙": "rồng — rồng, long",
    "龜": "con rùa — rùa, quy",
    "龟": "rùa — rùa, quy",
    "龠": "ống sáo — sáo, nhạc cụ",
}


# ═══════════════════════════════════════════════════════════════
#  NGÂN HÀNG ÂM THANH GẦN GIỐNG TIẾNG VIỆT
# ═══════════════════════════════════════════════════════════════
SOUND_HINTS = {
    # A
    "āi": "ai (than thở)", "ài": "ái (ái tình)",
    "ān": "an (yên ổn)", "ào": "áo (áo quần)",
    # B
    "bā": "ba (số ba)", "bà": "bà (người bà)",
    "bái": "bái (bái biệt)", "bān": "ban (ban phát)",
    "bàn": "bàn (cái bàn)", "bāo": "bao (bao bọc)",
    "bǎo": "bảo (bảo bối)", "běi": "bắc (hướng bắc)",
    "běn": "bản (bản thân)", "bǐ": "bỉ (so bì)",
    "bì": "bì (bì ẩn)", "biàn": "biến (biến đổi)",
    "biǎo": "biểu (biểu diễn)", "bié": "biệt (biệt ly)",
    "bīng": "binh (binh lính)", "bù": "bộ (bộ phận)",
    # C
    "cài": "cải (rau cải)", "chá": "trà (uống trà)",
    "cháng": "tràng (ruột)", "chàng": "chàng (chàng trai)",
    "chē": "xe (chiếc xe)", "chī": "chi (chi tiêu)",
    "chū": "xuất (xuất hiện)", "cì": "thứ (thứ tự)",
    "cóng": "tùng (cây tùng)",
    # D
    "dà": "đại (to lớn)", "dài": "đại (đại khái)",
    "dào": "đạo (đạo lý)", "dì": "địa (đất đai)",
    "diǎn": "điểm (điểm số)", "dōng": "đông (mùa đông)",
    "dòng": "động (động vật)", "duì": "đối (đối diện)",
    "duō": "đa (đa số)",
    # E
    "ér": "nhi (nhi đồng)", "èr": "nhị (số 2)",
    # F
    "fàn": "phạn (cơm)", "fēi": "phi (bay)",
    "fēng": "phong (gió)", "fú": "phúc (phúc lợi)",
    "fù": "phụ (cha)",
    # G
    "gāo": "cao (cao thấp)", "gē": "ca (anh trai)",
    "gè": "cá (cá nhân)", "gěi": "cấp (cấp cho)",
    "gēn": "căn (căn nhà)", "gōng": "công (công việc)",
    "gǒu": "cẩu (con chó)", "guā": "qua (quả dưa)",
    "guò": "quá (quá khứ)",
    # H
    "hǎo": "hảo (tốt)", "hào": "hào (hào phóng)",
    "hé": "hà (con sông)", "hē": "ha (cười ha)",
    "hēi": "hắc (màu đen)", "hěn": "hận (thù hận)",
    "hóng": "hồng (màu đỏ)", "hòu": "hậu (sau)",
    "huā": "hoa (bông hoa)", "huà": "họa (bức họa)",
    "huǒ": "hỏa (lửa)",
    # J
    "jī": "cơ (cơ hội)", "jǐ": "kỷ (kỷ luật)",
    "jiā": "gia (gia đình)", "jiàn": "kiến (kiến thức)",
    "jiào": "giáo (giáo dục)", "jīn": "kim (kim loại)",
    "jìn": "tiến (tiến bộ)", "jiǔ": "cửu (số 9)",
    # K
    "kāi": "khai (khai mở)", "kàn": "khán (xem)",
    "kǎo": "khảo (khảo sát)", "kǒu": "khẩu (miệng)",
    "kū": "khốc (khóc)",
    # L
    "lái": "lai (đến)", "lǎo": "lão (già)",
    "lè": "lạc (vui vẻ)", "lěng": "lãnh (lạnh)",
    "lì": "lực (sức lực)", "liǎng": "lưỡng (hai)",
    # M
    "mā": "ma (mẹ)", "mǎ": "mã (con ngựa)",
    "mǎi": "mãi (mua)", "mài": "mại (bán)",
    "máng": "mang (mang vác)", "máo": "mao (lông)",
    "mào": "mạo (mạo hiểm)", "méi": "mai (hoa mai)",
    "mèi": "muội (em gái)", "mén": "môn (cửa)",
    "mǐ": "mễ (gạo)", "miàn": "miến (mặt)",
    "míng": "minh (sáng)", "mù": "mộc (gỗ)",
    # N
    "nǎ": "na (nào)", "nán": "nam (phía nam)",
    "nǎo": "não (bộ não)", "ne": "nê (đâu)",
    "néng": "năng (khả năng)", "nǐ": "nhĩ (tai)",
    "nián": "niên (năm)", "niǎo": "điểu (chim)",
    "niú": "ngưu (bò)", "nǚ": "nữ (phụ nữ)",
    "nuǎn": "noãn (ấm áp)",
    # P
    "pàng": "bàng (bên cạnh)", "pǎo": "bào (chạy)",
    "péng": "bằng (bạn)", "piào": "phiếu (vé)",
    # Q
    "qī": "thê (vợ)", "qí": "kỳ (kỳ lạ)",
    "qián": "tiền (tiền bạc)", "qiáng": "cường (mạnh)",
    "qīng": "thanh (xanh)", "qíng": "tình (tình cảm)",
    "qǐng": "thỉnh (mời)", "qù": "khứ (đi)",
    "quán": "quyền (quyền lực)",
    # R
    "rán": "nhiên (tự nhiên)", "rén": "nhân (người)",
    "rèn": "nhận (nhận biết)", "rì": "nhật (ngày)",
    "róng": "dung (dung mạo)",
    # S
    "sān": "tam (số 3)", "sè": "sắc (màu sắc)",
    "shān": "sơn (núi)", "shàng": "thượng (trên)",
    "shǎo": "thiểu (ít)", "shé": "xà (con rắn)",
    "shēng": "sinh (sống)", "shí": "thập (mười)",
    "shì": "thị (chợ)", "shǒu": "thủ (tay)",
    "shū": "thư (sách)", "shuǐ": "thủy (nước)",
    "shuō": "thuyết (nói)", "sī": "tư (tư duy)",
    "sì": "tứ (số 4)", "sòng": "tống (đưa tiễn)",
    "suì": "tuế (năm)",
    # T
    "tā": "tha (anh ấy)", "tài": "thái (thái độ)",
    "tán": "đàm (đàm thoại)", "tāng": "canh (canh súp)",
    "táo": "đào (quả đào)", "tīng": "thính (nghe)",
    "tǔ": "thổ (đất)", "tóu": "đầu (đầu tiên)",
    "tú": "đồ (bản đồ)",
    # W
    "wán": "hoàn (hoàn thành)", "wǎn": "vãn (buổi tối)",
    "wàn": "vạn (vạn vật)", "wáng": "vương (vua)",
    "wàng": "vọng (hy vọng)", "wén": "văn (văn chương)",
    "wèn": "vấn (vấn đề)", "wǒ": "ngã (tôi)",
    "wǔ": "ngũ (số 5)",
    # X
    "xī": "tây (hướng tây)", "xǐ": "tẩy (rửa)",
    "xì": "hệ (hệ thống)", "xià": "hạ (mùa hè)",
    "xiān": "tiên (trước)", "xiàn": "hiện (hiện tại)",
    "xiǎng": "tưởng (tưởng tượng)", "xiàng": "tượng (hình tượng)",
    "xiǎo": "tiểu (nhỏ)", "xiào": "tiếu (cười)",
    "xiě": "tả (viết)", "xīn": "tâm (tim)",
    "xìn": "tín (tin tưởng)", "xīng": "tinh (ngôi sao)",
    "xíng": "hành (hành động)", "xué": "học (học tập)",
    "xuě": "tuyết (tuyết rơi)",
    # Y
    "yáng": "dương (mặt trời)", "yào": "dược (thuốc)",
    "yé": "da (ông)", "yě": "dã (hoang dã)",
    "yī": "y (áo)", "yí": "di (di chuyển)",
    "yǐ": "dĩ (đã)", "yì": "ý (ý nghĩa)",
    "yīn": "âm (âm thanh)", "yín": "ngân (bạc)",
    "yīng": "anh (nước Anh)", "yóu": "du (du lịch)",
    "yǒu": "hữu (có)", "yòu": "hữu (bên phải)",
    "yú": "ngư (cá)", "yǔ": "vũ (mưa)",
    "yuán": "nguyên (nguồn)", "yuè": "nguyệt (trăng)",
    # Z
    "zài": "tái (lần nữa)", "zǎo": "tảo (sớm)",
    "zěn": "chẩm (gối)", "zhàn": "trạm (trạm dừng)",
    "zhǎng": "trưởng (lớn lên)", "zhè": "giá (đây)",
    "zhēn": "trân (quý)", "zhèng": "chính (đúng)",
    "zhī": "chi (cành)", "zhí": "trực (thẳng)",
    "zhǐ": "chỉ (dừng lại)", "zhì": "trí (trí tuệ)",
    "zhōng": "trung (giữa)", "zhòng": "trọng (nặng)",
    "zhōu": "châu (châu lục)", "zhù": "trú (ở)",
    "zhuā": "trảo (nắm)", "zhuǎn": "chuyển (chuyển đổi)",
    "zì": "tự (chữ)", "zǒu": "tẩu (đi)",
    "zuì": "tội (tội lỗi)", "zuó": "tạc (hôm qua)",
    "zuǒ": "tả (bên trái)", "zuò": "tọa (ngồi)",
}


# ═══════════════════════════════════════════════════════════════
#  HELPER
# ═══════════════════════════════════════════════════════════════
def _remove_tone(text):
    if not text:
        return ""
    nfd = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def _get_sound_hint(pinyin):
    if not pinyin:
        return None
    clean = re.sub(r'[/\s]', '', pinyin.lower().strip())
    if not clean:
        return None
    if clean in SOUND_HINTS:
        return SOUND_HINTS[clean]
    no_tone = _remove_tone(clean)
    for key, val in SOUND_HINTS.items():
        if _remove_tone(key) == no_tone:
            return val
    return None


def _get_radical_story(radical_info):
    if not radical_info:
        return None
    zh = radical_info.get("zh", "")
    meaning = radical_info.get("meaning", "")
    return RADICAL_STORIES.get(zh) or meaning


# ═══════════════════════════════════════════════════════════════
#  SINH MẸO NHỚ CHO 1 CHỮ
# ═══════════════════════════════════════════════════════════════
def _generate_single_char_mnemonic(char, pinyin="", vi=""):
    """Sinh mẹo cho 1 chữ Hán."""
    hints = []

    # Phân tích thành phần
    comps = _split_components(char)

    # 1. Chiết tự
    if len(comps) >= 2:
        parts_str = []
        for c in comps[:4]:
            ch = c.get("zh", "")
            meaning = c.get("meaning", "")
            if ch and meaning:
                parts_str.append(ch + " (" + meaning + ")")
            elif ch:
                parts_str.append(ch)
        if len(parts_str) >= 2:
            breakdown = " + ".join(parts_str)
            hints.append('"' + char + '" = ' + breakdown)

    # 2. Âm thanh
    sound_hint = _get_sound_hint(pinyin)
    if sound_hint:
        hints.append('Âm "' + pinyin + '" ≈ "' + sound_hint + '"')

    # 3. Câu chuyện bộ thủ chính
    if comps:
        # Chọn bộ chính (ưu tiên left)
        left_comps = [c for c in comps if c.get("position") == "left"]
        main_c = left_comps[0] if left_comps else comps[0]
        story = _get_radical_story(main_c)
        if story:
            hints.append("Chữ có bộ " + main_c.get("zh", "") + " — " + story)

    if not hints:
        return ""
    return "\n".join(hints[:3])


# ═══════════════════════════════════════════════════════════════
#  API CHÍNH — SINH MẸO CHO TỪ (1+ chữ)
# ═══════════════════════════════════════════════════════════════
def generate_mnemonic(zh, pinyin="", vi=""):
    """
    Sinh mẹo nhớ tự động.
    - Từ 1 chữ: chiết tự + âm thanh + câu chuyện
    - Từ 2+ chữ: phân tích từng chữ + ghép nghĩa
    """
    if not zh:
        return ""

    chars = [c for c in zh if '\u4e00' <= c <= '\u9fff']
    if not chars:
        return ""

    # ═══ TỪ 1 CHỮ ═══
    # ═══ TỪ 1 CHỮ ═══
    if len(chars) == 1:
        base = _generate_single_char_mnemonic(chars[0], pinyin, vi)
        
        # ⭐ Thêm gợi ý chữ dễ nhầm
        similar_info = find_similar_chars(chars[0])
        if similar_info:
            similar_list = similar_info.get("similar", [])
            diff_text = similar_info.get("diff", "")
            if similar_list and diff_text:
                similar_str = "🔍 Dễ nhầm: " + ", ".join(similar_list)
                similar_str += "\n📌 " + diff_text
                if base:
                    base += "\n\n" + similar_str
                else:
                    base = similar_str
        
        return base
    # ═══ TỪ 2+ CHỮ — TỪ GHÉP ═══
    hints = []

    # 1. Phân tích từng chữ
    parts_meaning = []
    for c in chars[:4]:  # Tối đa 4 chữ
        comps = _split_components(c)
        if comps:
            # Chọn bộ chính
            left = [x for x in comps if x.get("position") == "left"]
            main_c = left[0] if left else comps[0]
            meaning = main_c.get("meaning", "")
            if meaning:
                parts_meaning.append(c + " (" + meaning + ")")
            else:
                parts_meaning.append(c)
        else:
            parts_meaning.append(c)

    if len(parts_meaning) >= 2:
        hints.append("Phân tích: " + " + ".join(parts_meaning))

    # 2. Ghép nghĩa — mẹo hay hơn
    if vi and len(chars) >= 2:
        hints.append("→ Nghĩa: " + vi)

    # 3. Âm thanh (chỉ khi từ ngắn)
    if len(chars) <= 2:
        # Tách pinyin
        pinyin_parts = pinyin.split()
        if len(pinyin_parts) == len(chars):
            sound_hints = []
            for i, c in enumerate(chars):
                sh = _get_sound_hint(pinyin_parts[i])
                if sh:
                    sound_hints.append(c + ' (' + pinyin_parts[i] + ' ≈ ' + sh + ')')
            if sound_hints:
                hints.append("Âm: " + " · ".join(sound_hints))

    if not hints:
        return ""
    return "\n".join(hints[:3])
