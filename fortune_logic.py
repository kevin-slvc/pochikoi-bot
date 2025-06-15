from datetime import datetime
import re

class FortuneCalculator:
    """算命学・動物占いの計算ロジック"""
    
    # 十干（じっかん）
    JIKKAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    
    # 十二支（じゅうにし）
    JUNISHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    
    # 動物占いキャラクター（60種類から主要12種類）
    ANIMAL_CHARACTERS = {
        0: {"name": "こじか", "traits": "純粋で人懐っこい", "love": "一途で素直な愛情表現"},
        1: {"name": "黒ひょう", "traits": "情熱的でスマート", "love": "駆け引き上手で魅力的"},
        2: {"name": "ひつじ", "traits": "優しくて平和主義", "love": "相手を包み込む愛情"},
        3: {"name": "チータ", "traits": "行動力抜群", "love": "積極的なアプローチ"},
        4: {"name": "たぬき", "traits": "人当たりが良い", "love": "相手に合わせる柔軟性"},
        5: {"name": "ゾウ", "traits": "真面目で努力家", "love": "誠実で長続きする愛"},
        6: {"name": "ライオン", "traits": "リーダーシップ", "love": "堂々とした愛情表現"},
        7: {"name": "コアラ", "traits": "マイペース", "love": "ゆったりとした愛情"},
        8: {"name": "ペガサス", "traits": "自由奔放", "love": "束縛されない関係を好む"},
        9: {"name": "狼", "traits": "独立心が強い", "love": "一人の時間も大切にする"},
        10: {"name": "猿", "traits": "器用で社交的", "love": "楽しい恋愛を求める"},
        11: {"name": "虎", "traits": "正義感が強い", "love": "真っ直ぐな愛情"}
    }
    
    @staticmethod
    def parse_birthday(birthday_str):
        """生年月日文字列をdatetimeオブジェクトに変換"""
        patterns = [
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', '%Y-%m-%d'),
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', '%Y-%m-%d'),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
        ]
        
        for pattern, _ in patterns:
            match = re.search(pattern, birthday_str)
            if match:
                year, month, day = map(int, match.groups())
                return datetime(year, month, day)
        
        # 和暦の処理
        if "平成" in birthday_str:
            match = re.search(r'平成(\d{1,2})年(\d{1,2})月(\d{1,2})日', birthday_str)
            if match:
                h_year, month, day = map(int, match.groups())
                year = 1988 + h_year
                return datetime(year, month, day)
        elif "昭和" in birthday_str:
            match = re.search(r'昭和(\d{1,2})年(\d{1,2})月(\d{1,2})日', birthday_str)
            if match:
                s_year, month, day = map(int, match.groups())
                year = 1925 + s_year
                return datetime(year, month, day)
        
        return None
    
    @classmethod
    def calculate_sanmeigaku(cls, birthday_str):
        """生年月日から十干十二支を算出"""
        birth_date = cls.parse_birthday(birthday_str)
        if not birth_date:
            return None
        
        # 簡易計算（実際の算命学はもっと複雑）
        year = birth_date.year
        
        # 十干の計算（年の下一桁から算出）
        jikkan_index = (year - 4) % 10
        jikkan = cls.JIKKAN[jikkan_index]
        
        # 十二支の計算
        junishi_index = (year - 4) % 12
        junishi = cls.JUNISHI[junishi_index]
        
        # 性格特性を定義
        jikkan_traits = {
            "甲": "リーダーシップがあり積極的",
            "乙": "柔軟で協調性がある",
            "丙": "明るく情熱的",
            "丁": "繊細で気配り上手",
            "戊": "安定感があり信頼される",
            "己": "面倒見が良く包容力がある",
            "庚": "正義感が強く行動的",
            "辛": "美的センスが高く繊細",
            "壬": "知的で柔軟な思考",
            "癸": "直感力が鋭く感受性豊か"
        }
        
        return {
            "jikkan": jikkan,
            "junishi": junishi,
            "element": f"{jikkan}{junishi}",
            "traits": jikkan_traits.get(jikkan, ""),
            "love_tendency": cls._get_love_tendency(jikkan, junishi)
        }
    
    @classmethod
    def calculate_animal_character(cls, birthday_str):
        """生年月日から動物占いキャラクターを判定"""
        birth_date = cls.parse_birthday(birthday_str)
        if not birth_date:
            return None
        
        # 簡易計算（実際はもっと複雑な計算）
        total = birth_date.year + birth_date.month + birth_date.day
        animal_index = total % 12
        
        return cls.ANIMAL_CHARACTERS[animal_index]
    
    @staticmethod
    def _get_love_tendency(jikkan, junishi):
        """十干十二支から恋愛傾向を導出"""
        tendencies = {
            "甲": "積極的にアプローチし、相手をリードする",
            "乙": "相手に合わせながら、じっくり関係を築く",
            "丙": "情熱的で、感情表現が豊か",
            "丁": "細やかな気遣いで相手を包む",
            "戊": "安定した関係を築き、相手を守る",
            "己": "相手を受け入れ、支える",
            "庚": "真っ直ぐな愛情表現",
            "辛": "上品で洗練された愛し方",
            "壬": "変化を楽しむ恋愛",
            "癸": "深い精神的つながりを求める"
        }
        return tendencies.get(jikkan, "")
    
    @staticmethod
    def get_daily_element_fortune(jikkan, current_date=None):
        """その日の五行相性から運勢を算出"""
        if current_date is None:
            current_date = datetime.now()
        
        # 日の十干を簡易計算
        day_number = current_date.toordinal()
        day_jikkan_index = day_number % 10
        day_jikkan = FortuneCalculator.JIKKAN[day_jikkan_index]
        
        # 相性マトリックス（簡易版）
        compatibility = {
            ("甲", "丙"): 5, ("甲", "丁"): 5, ("甲", "戊"): 3, ("甲", "己"): 3,
            ("乙", "丙"): 5, ("乙", "丁"): 5, ("乙", "庚"): 2, ("乙", "辛"): 2,
            ("丙", "戊"): 5, ("丙", "己"): 5, ("丙", "庚"): 3, ("丙", "辛"): 3,
            ("丁", "戊"): 5, ("丁", "己"): 5, ("丁", "壬"): 2, ("丁", "癸"): 2,
            # ... 実際はもっと詳細な相性表
        }
        
        # デフォルトは3（普通）
        score = compatibility.get((jikkan, day_jikkan), 3)
        
        return {
            "score": score,
            "day_element": day_jikkan,
            "compatibility": "★" * score,
            "advice": FortuneCalculator._get_fortune_advice(score)
        }
    
    @staticmethod
    def _get_fortune_advice(score):
        """運勢スコアに基づくアドバイス"""
        advices = {
            5: "最高の運気！積極的な行動が成功を呼びます",
            4: "良い運気。チャンスを逃さないで",
            3: "安定した運気。いつも通りで大丈夫",
            2: "慎重に行動を。タイミングを見極めて",
            1: "充電期間。無理せず休息を"
        }
        return advices.get(score, "")
