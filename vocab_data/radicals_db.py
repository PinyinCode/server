# -*- coding: utf-8 -*-
"""
Database 214 bộ thủ Khang Hy (Kangxi Radicals) + biến thể giản thể.
Format: { char: (pinyin, strokes, meaning_vi) }

Nguồn: Kangxi Dictionary (康熙字典)
"""

RADICALS = {
    # ═══════════ 1 NÉT ═══════════
    "一": ("yī", 1, "Một, số một"),
    "丨": ("gǔn", 1, "Sổ thẳng"),
    "丶": ("zhǔ", 1, "Chấm"),
    "丿": ("piě", 1, "Phẩy"),
    "乙": ("yǐ", 1, "Vị trí thứ 2 thiên can"),
    "亅": ("jué", 1, "Móc"),

    # ═══════════ 2 NÉT ═══════════
    "二": ("èr", 2, "Hai"),
    "亠": ("tóu", 2, "Đầu, nắp"),
    "人": ("rén", 2, "Người"),
    "儿": ("ér", 2, "Trẻ con, chân người"),
    "入": ("rù", 2, "Vào"),
    "八": ("bā", 2, "Tám"),
    "冂": ("jiōng", 2, "Biên giới"),
    "冖": ("mì", 2, "Che, trùm"),
    "冫": ("bīng", 2, "Băng đá"),
    "几": ("jī", 2, "Ghế dựa"),
    "凵": ("kǎn", 2, "Há miệng"),
    "刀": ("dāo", 2, "Dao"),
    "力": ("lì", 2, "Sức mạnh"),
    "勹": ("bāo", 2, "Bọc"),
    "匕": ("bǐ", 2, "Thìa"),
    "匚": ("fāng", 2, "Hộp"),
    "匸": ("xì", 2, "Che giấu"),
    "十": ("shí", 2, "Mười"),
    "卜": ("bǔ", 2, "Bói toán"),
    "卩": ("jié", 2, "Đốt tre"),
    "厂": ("chǎng", 2, "Sườn núi"),
    "厶": ("sī", 2, "Riêng tư"),
    "又": ("yòu", 2, "Lại, một lần nữa"),

    # ═══════════ 3 NÉT ═══════════
    "口": ("kǒu", 3, "Miệng"),
    "囗": ("wéi", 3, "Vây quanh"),
    "土": ("tǔ", 3, "Đất"),
    "士": ("shì", 3, "Sĩ, kẻ có học"),
    "夂": ("zhǐ", 3, "Đi chậm"),
    "夊": ("suī", 3, "Đi chậm"),
    "夕": ("xī", 3, "Chiều tối"),
    "大": ("dà", 3, "To, lớn"),
    "女": ("nǚ", 3, "Phụ nữ"),
    "子": ("zǐ", 3, "Con"),
    "宀": ("mián", 3, "Mái nhà"),
    "寸": ("cùn", 3, "Tấc (đơn vị đo)"),
    "小": ("xiǎo", 3, "Nhỏ"),
    "尢": ("wāng", 3, "Yếu ớt"),
    "尸": ("shī", 3, "Xác chết"),
    "屮": ("chè", 3, "Mầm cây"),
    "山": ("shān", 3, "Núi"),
    "巛": ("chuān", 3, "Sông"),
    "工": ("gōng", 3, "Công việc"),
    "己": ("jǐ", 3, "Bản thân"),
    "巾": ("jīn", 3, "Khăn"),
    "干": ("gān", 3, "Khô"),
    "幺": ("yāo", 3, "Nhỏ, út"),
    "广": ("guǎng", 3, "Rộng"),
    "廴": ("yǐn", 3, "Bước dài"),
    "廾": ("gǒng", 3, "Chắp tay"),
    "弋": ("yì", 3, "Bắn"),
    "弓": ("gōng", 3, "Cung"),
    "彐": ("jì", 3, "Đầu heo"),
    "彡": ("shān", 3, "Lông"),
    "彳": ("chì", 3, "Bước chân"),

    # ═══════════ 4 NÉT ═══════════
    "心": ("xīn", 4, "Tim, tình cảm"),
    "戈": ("gē", 4, "Giáo mác"),
    "戶": ("hù", 4, "Cửa"),
    "手": ("shǒu", 4, "Tay"),
    "支": ("zhī", 4, "Chống đỡ"),
    "攴": ("pū", 4, "Đánh nhẹ"),
    "文": ("wén", 4, "Văn, chữ"),
    "斗": ("dǒu", 4, "Đấu (đơn vị)"),
    "斤": ("jīn", 4, "Cái búa, cân"),
    "方": ("fāng", 4, "Vuông, phương hướng"),
    "无": ("wú", 4, "Không"),
    "日": ("rì", 4, "Mặt trời, ngày"),
    "曰": ("yuē", 4, "Nói"),
    "月": ("yuè", 4, "Mặt trăng, tháng"),
    "木": ("mù", 4, "Cây"),
    "欠": ("qiàn", 4, "Thiếu"),
    "止": ("zhǐ", 4, "Dừng lại"),
    "歹": ("dǎi", 4, "Xấu, chết"),
    "殳": ("shū", 4, "Binh khí"),
    "毋": ("wú", 4, "Chớ, đừng"),
    "比": ("bǐ", 4, "So sánh"),
    "毛": ("máo", 4, "Lông"),
    "氏": ("shì", 4, "Họ"),
    "气": ("qì", 4, "Không khí"),
    "水": ("shuǐ", 4, "Nước"),
    "火": ("huǒ", 4, "Lửa"),
    "爪": ("zhǎo", 4, "Móng vuốt, bàn tay"),
    "父": ("fù", 4, "Cha"),
    "爻": ("yáo", 4, "Hào (quẻ)"),
    "爿": ("pán", 4, "Mảnh gỗ"),
    "片": ("piàn", 4, "Miếng"),
    "牙": ("yá", 4, "Răng"),
    "牛": ("niú", 4, "Bò"),
    "犬": ("quǎn", 4, "Chó"),

    # ═══════════ 5 NÉT ═══════════
    "玄": ("xuán", 5, "Huyền bí"),
    "玉": ("yù", 5, "Ngọc"),
    "瓜": ("guā", 5, "Dưa"),
    "瓦": ("wǎ", 5, "Ngói"),
    "甘": ("gān", 5, "Ngọt"),
    "生": ("shēng", 5, "Sinh, sống"),
    "用": ("yòng", 5, "Dùng"),
    "田": ("tián", 5, "Ruộng"),
    "疋": ("pǐ", 5, "Chân"),
    "疒": ("nè", 5, "Bệnh"),
    "癶": ("bō", 5, "Gạt ra"),
    "白": ("bái", 5, "Trắng"),
    "皮": ("pí", 5, "Da"),
    "皿": ("mǐn", 5, "Đồ đựng"),
    "目": ("mù", 5, "Mắt"),
    "矛": ("máo", 5, "Giáo"),
    "矢": ("shǐ", 5, "Mũi tên"),
    "石": ("shí", 5, "Đá"),
    "示": ("shì", 5, "Chỉ bảo"),
    "禸": ("róu", 5, "Dấu chân"),
    "禾": ("hé", 5, "Lúa"),
    "穴": ("xué", 5, "Hang"),
    "立": ("lì", 5, "Đứng"),

    # ═══════════ 6 NÉT ═══════════
    "竹": ("zhú", 6, "Tre"),
    "米": ("mǐ", 6, "Gạo"),
    "糸": ("mì", 6, "Tơ"),
    "缶": ("fǒu", 6, "Đồ gốm"),
    "网": ("wǎng", 6, "Lưới"),
    "羊": ("yáng", 6, "Cừu"),
    "羽": ("yǔ", 6, "Lông vũ"),
    "老": ("lǎo", 6, "Già"),
    "而": ("ér", 6, "Mà"),
    "耒": ("lěi", 6, "Cày"),
    "耳": ("ěr", 6, "Tai"),
    "聿": ("yù", 6, "Bút"),
    "肉": ("ròu", 6, "Thịt"),
    "臣": ("chén", 6, "Bề tôi"),
    "自": ("zì", 6, "Tự, mình"),
    "至": ("zhì", 6, "Đến"),
    "臼": ("jiù", 6, "Cối"),
    "舌": ("shé", 6, "Lưỡi"),
    "舛": ("chuǎn", 6, "Sai"),
    "舟": ("zhōu", 6, "Thuyền"),
    "艮": ("gèn", 6, "Quẻ Cấn"),
    "色": ("sè", 6, "Màu"),
    "艸": ("cǎo", 6, "Cỏ"),
    "虍": ("hū", 6, "Vằn hổ"),
    "虫": ("chóng", 6, "Sâu bọ"),
    "血": ("xuè", 6, "Máu"),
    "行": ("xíng", 6, "Đi"),
    "衣": ("yī", 6, "Áo"),
    "西": ("xī", 6, "Tây"),

    # ═══════════ 7 NÉT ═══════════
    "見": ("jiàn", 7, "Thấy"),
    "角": ("jiǎo", 7, "Sừng"),
    "言": ("yán", 7, "Lời nói"),
    "谷": ("gǔ", 7, "Thung lũng"),
    "豆": ("dòu", 7, "Đậu"),
    "豕": ("shǐ", 7, "Heo"),
    "豸": ("zhì", 7, "Loài sâu"),
    "貝": ("bèi", 7, "Vỏ sò, tiền"),
    "赤": ("chì", 7, "Đỏ"),
    "走": ("zǒu", 7, "Đi, chạy"),
    "足": ("zú", 7, "Chân"),
    "身": ("shēn", 7, "Thân thể"),
    "車": ("chē", 7, "Xe"),
    "辛": ("xīn", 7, "Cay, vất vả"),
    "辰": ("chén", 7, "Giờ Thìn"),
    "辵": ("chuò", 7, "Bước đi"),
    "邑": ("yì", 7, "Thành phố"),
    "酉": ("yǒu", 7, "Giờ Dậu"),
    "釆": ("biàn", 7, "Phân biệt"),
    "里": ("lǐ", 7, "Dặm, làng"),

    # ═══════════ 8 NÉT ═══════════
    "金": ("jīn", 8, "Vàng, kim loại"),
    "長": ("cháng", 8, "Dài"),
    "門": ("mén", 8, "Cửa"),
    "阜": ("fù", 8, "Gò đất"),
    "隶": ("lì", 8, "Nô lệ"),
    "隹": ("zhuī", 8, "Chim đuôi ngắn"),
    "雨": ("yǔ", 8, "Mưa"),
    "青": ("qīng", 8, "Xanh"),
    "非": ("fēi", 8, "Không phải"),

    # ═══════════ 9 NÉT ═══════════
    "面": ("miàn", 9, "Mặt"),
    "革": ("gé", 9, "Da thuộc"),
    "韋": ("wéi", 9, "Da mềm"),
    "韭": ("jiǔ", 9, "Hẹ"),
    "音": ("yīn", 9, "Âm thanh"),
    "頁": ("yè", 9, "Trang giấy, đầu"),
    "風": ("fēng", 9, "Gió"),
    "飛": ("fēi", 9, "Bay"),
    "食": ("shí", 9, "Ăn"),
    "首": ("shǒu", 9, "Đầu"),
    "香": ("xiāng", 9, "Thơm"),

    # ═══════════ 10+ NÉT ═══════════
    "馬": ("mǎ", 10, "Ngựa"),
    "骨": ("gǔ", 10, "Xương"),
    "高": ("gāo", 10, "Cao"),
    "髟": ("biāo", 10, "Tóc dài"),
    "鬥": ("dòu", 10, "Đánh nhau"),
    "鬯": ("chàng", 10, "Rượu tế"),
    "鬲": ("lì", 10, "Nồi đất"),
    "鬼": ("guǐ", 10, "Ma"),
    "魚": ("yú", 11, "Cá"),
    "鳥": ("niǎo", 11, "Chim"),
    "鹵": ("lǔ", 11, "Đất mặn"),
    "鹿": ("lù", 11, "Hươu"),
    "麥": ("mài", 11, "Lúa mạch"),
    "麻": ("má", 11, "Cây gai"),
    "黃": ("huáng", 12, "Vàng"),
    "黍": ("shǔ", 12, "Lúa nếp"),
    "黑": ("hēi", 12, "Đen"),
    "黹": ("zhǐ", 12, "Thêu"),
    "黽": ("mǐn", 13, "Con ếch"),
    "鼎": ("dǐng", 13, "Cái đỉnh"),
    "鼓": ("gǔ", 13, "Cái trống"),
    "鼠": ("shǔ", 13, "Chuột"),
    "鼻": ("bí", 14, "Mũi"),
    "齊": ("qí", 14, "Đều, ngang"),
    "齒": ("chǐ", 15, "Răng"),
    "龍": ("lóng", 16, "Rồng"),
    "龜": ("guī", 16, "Rùa"),
    "龠": ("yuè", 17, "Ống sáo"),
}

# ═══════════════════════════════════════════════════════════════
#  BIẾN THỂ GIẢN THỂ CỦA BỘ THỦ PHỒN THỂ
# ═══════════════════════════════════════════════════════════════
SIMPLIFIED_VARIANTS = {
    # Bộ thủ thật
    "见": "見", "车": "車", "门": "門", "马": "馬", "鸟": "鳥",
    "鱼": "魚", "贝": "貝", "长": "長", "韦": "韋", "页": "頁",
    "风": "風", "飞": "飛", "齿": "齒", "龙": "龍", "龟": "龜",
    "卤": "鹵", "麦": "麥", "黄": "黃", "齐": "齊",

    # ═══ Biến thể 形声 (hình thanh) phổ biến ═══
    "氵": "水",   # Nước — 江 河 湖 海
    "忄": "心",   # Tim — 快 忙 怕 情
    "扌": "手",   # Tay — 打 拉 推 拿
    "讠": "言",   # Lời — 说 话 请 谢
    "钅": "金",   # Kim loại — 银 铁 钱 钢
    "饣": "食",   # Ăn — 饭 饿 饱 饺
    "纟": "糸",   # Tơ — 红 绿 纸 练
    "辶": "辵",   # Bước đi — 进 出 过 送
    "犭": "犬",   # Chó — 猫 狗 猪 狼
    "艹": "艸",   # Cỏ — 花 草 茶 药
    "灬": "火",   # Lửa — 热 照 煮 煎
    "爫": "爪",   # Tay/móng — 爱 受 采 乳
    "罒": "网",   # Lưới — 罗 罚 罪 置
    "⺮": "竹",   # Tre — 笔 笑 第 答
    "⻊": "足",   # Chân — 跑 跳 踢 跟
    "⺼": "肉",   # Thịt — 肚 肝 胖 脑
    "⻖": "阜",   # Gò đất — 阴 阳 阳 陈
    "⻏": "邑",   # Thành phố — 都 部 邮 邻
    "⻗": "雨",   # Mưa — 雪 雷 需 雾
    "刂": "刀",   # Dao — 别 到 划 刻
    "亻": "人",   # Người — 你 他 休 位
    "冫": "冫",   # Băng đá (biến thể của 冰)

    # ═══ Biến thể mới bổ sung ═══
    "攵": "攴",   # Đánh nhẹ — 收 故 教 数 整 敬 救 散 敷
    "乛": "乙",   # Nét sổ cong — 买
    "礻": "示",   # Chỉ bảo — 礼 祝 神 福
    "衤": "衣",   # Áo — 裸 补 衬 袖
}

# ═══════════════════════════════════════════════════════════════
#  Ý NGHĨA BỔ SUNG CHO BIẾN THỂ
# ═══════════════════════════════════════════════════════════════
VARIANT_MEANINGS = {
    "氵": "Nước (biến thể của 水)",
    "忄": "Tim, cảm xúc (biến thể của 心)",
    "扌": "Tay (biến thể của 手)",
    "讠": "Lời nói (biến thể của 言)",
    "钅": "Kim loại (biến thể của 金)",
    "饣": "Ăn (biến thể của 食)",
    "纟": "Tơ, chỉ (biến thể của 糸)",
    "辶": "Bước đi (biến thể của 辵)",
    "犭": "Chó (biến thể của 犬)",
    "艹": "Cỏ (biến thể của 艸)",
    "灬": "Lửa (biến thể của 火)",
    "爫": "Tay, móng (biến thể của 爪)",
    "罒": "Lưới (biến thể của 网)",
    "⺮": "Tre (biến thể của 竹)",
    "⻊": "Chân (biến thể của 足)",
    "⺼": "Thịt (biến thể của 肉)",
    "⻖": "Gò đất (biến thể của 阜)",
    "⻏": "Thành phố (biến thể của 邑)",
    "⻗": "Mưa (biến thể của 雨)",
    "刂": "Dao (biến thể của 刀)",
    "亻": "Người (biến thể của 人)",
    "冫": "Băng đá (biến thể của 冰)",

    # ═══ Biến thể mới bổ sung ═══
    "攵": "Đánh nhẹ (biến thể của 攴)",
    "乛": "Nét sổ cong (biến thể của 乙)",
    "礻": "Chỉ bảo (biến thể của 示)",
    "衤": "Áo (biến thể của 衣)",
}


def get_radical_info(char):
    """
    Tra cứu bộ thủ. Trả về dict hoặc None.
    Format: {"zh", "pinyin", "strokes", "meaning"}
    """
    if not char:
        return None

    original = char

    # Chuẩn hoá về dạng gốc nếu là biến thể
    if char in SIMPLIFIED_VARIANTS:
        base = SIMPLIFIED_VARIANTS[char]
        # Nếu có trong RADICALS → dùng info của base
        if base in RADICALS:
            pinyin, strokes, meaning = RADICALS[base]
            # Nếu là biến thể (VD: 氵), trả về info biến thể + ý nghĩa gốc
            if char != base:
                variant_meaning = VARIANT_MEANINGS.get(char, meaning)
                return {
                    "zh": char,           # Hiển thị biến thể (氵)
                    "base_zh": base,      # Bộ gốc (水)
                    "pinyin": pinyin,
                    "strokes": strokes,
                    "meaning": variant_meaning,
                }
            # Trùng với base → trả về bình thường
            return {
                "zh": base,
                "pinyin": pinyin,
                "strokes": strokes,
                "meaning": meaning,
            }

    # Trực tiếp có trong RADICALS
    if char in RADICALS:
        pinyin, strokes, meaning = RADICALS[char]
        return {
            "zh": char,
            "pinyin": pinyin,
            "strokes": strokes,
            "meaning": meaning,
        }

    # Chỉ có trong VARIANT_MEANINGS (biến thể không map được)
    if original in VARIANT_MEANINGS:
        return {
            "zh": original,
            "pinyin": "",
            "strokes": "",
            "meaning": VARIANT_MEANINGS[original],
        }

    return None
