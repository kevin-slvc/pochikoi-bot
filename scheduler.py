import os
import json
from datetime import datetime, time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from linebot import LineBotApi
from linebot.models import TextSendMessage
import google.generativeai as genai

# 追加インポート（main.pyから）
from fortune_logic import FortuneCalculator

# 環境変数
line_bot_api = LineBotApi(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', ''))
genai.configure(api_key=os.environ.get('GEMINI_API_KEY', ''))
model = genai.GenerativeModel('gemini-pro')

# タイムゾーン設定（日本時間）
JST = pytz.timezone('Asia/Tokyo')

class FortuneScheduler:
    """占い配信スケジューラー"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=JST)
        self.setup_jobs()
    
    def setup_jobs(self):
        """定期実行ジョブの設定"""
        # 毎朝7時の配信
        self.scheduler.add_job(
            func=self.send_morning_fortunes,
            trigger=CronTrigger(hour=7, minute=0, timezone=JST),
            id='morning_fortune',
            replace_existing=True
        )
        
        # 毎週月曜日の週間占い
        self.scheduler.add_job(
            func=self.send_weekly_fortunes,
            trigger=CronTrigger(day_of_week='mon', hour=7, minute=30, timezone=JST),
            id='weekly_fortune',
            replace_existing=True
        )
        
        # 新月・満月の特別占い（月2回程度）
        # 実際は天文データAPIと連携して正確な日時を取得
        
    def start(self):
        """スケジューラー開始"""
        self.scheduler.start()
        print("Fortune Scheduler started!")
    
    def shutdown(self):
        """スケジューラー停止"""
        self.scheduler.shutdown()
    
    @staticmethod
    def load_users_data():
        """ユーザーデータ読み込み"""
        try:
            with open('users_data.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def send_morning_fortunes(self):
        """毎朝の占い配信"""
        print(f"Starting morning fortune delivery at {datetime.now(JST)}")
        
        users_data = self.load_users_data()
        success_count = 0
        error_count = 0
        
        for user_id, user_data in users_data.items():
            # オンボーディング完了ユーザーのみ
            if not user_data.get('onboarding_complete', False):
                continue
            
            # 有料プランチェック（今は全員に配信）
            # if not user_data.get('is_premium', True):
            #     continue
            
            try:
                fortune_message = self.generate_personalized_morning_fortune(user_data)
                
                # LINE配信
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(text=fortune_message)
                )
                
                success_count += 1
                
            except Exception as e:
                print(f"Error sending to {user_id}: {e}")
                error_count += 1
        
        print(f"Morning fortune delivery completed: {success_count} success, {error_count} errors")
    
    def generate_personalized_morning_fortune(self, user_data):
        """個人用の朝の占い生成"""
        now = datetime.now(JST)
        name = user_data.get('name', 'あなた')
        animal = user_data.get('animal_character', {})
        sanmeigaku = user_data.get('sanmeigaku', {})
        
        # 今日の運勢を算命学で計算
        daily_fortune = FortuneCalculator.get_daily_element_fortune(
            sanmeigaku.get('jikkan', '甲')
        )
        
        # 曜日別の特別メッセージ
        weekday_messages = {
            0: "月曜日、新しい週の始まり！",
            1: "火曜日、エネルギーが高まる日",
            2: "水曜日、バランスを大切に",
            3: "木曜日、恋愛運のピーク！",
            4: "金曜日、華やかな出会いの予感",
            5: "土曜日、デート日和",
            6: "日曜日、心の充電を"
        }
        
        weekday_msg = weekday_messages.get(now.weekday(), "")
        
        prompt = f"""
{name}さんへの今日の占いを作成してください。

【基本情報】
日付：{now.strftime('%m月%d日')}（{weekday_msg}）
動物占い：{animal.get('name', '')} - {animal.get('traits', '')}
算命学：{sanmeigaku.get('element', '')} - {sanmeigaku.get('traits', '')}
今日の相性：{daily_fortune.get('compatibility', '')}

【ユーザー状況】
恋愛状況：{user_data.get('relationship_status', '')}
悩み：{user_data.get('main_concern', '')}

200-250文字で以下を含めて：
1. 今日の総合運（★5段階）
2. 恋愛運のピークタイム（具体的な時間）
3. 今日のラッキーアクション（ユニークで実践しやすい）
4. 一言アドバイス

明るく前向きで、読んだ人が行動したくなる内容で。
絵文字を適度に使用。
"""

        try:
            response = model.generate_content(prompt)
            
            base_message = f"""おはようございます、{name}さん☀️

【{now.strftime('%m月%d日')}の運勢】
{animal.get('name', '')}×{sanmeigaku.get('element', '')}

{response.text}"""
            
            # 有料プラン誘導（無料ユーザーの場合）
            if not user_data.get('is_premium', False):
                base_message += "\n\n💎 詳細な時間別運勢は有料プランで！"
            
            return base_message
            
        except Exception as e:
            print(f"Gemini API error: {e}")
            # フォールバック
            return f"""おはようございます、{name}さん☀️

【{now.strftime('%m月%d日')}の運勢】
総合運：{daily_fortune.get('compatibility', '★★★☆☆')}

{animal.get('name', '')}の今日は
{daily_fortune.get('advice', '新しい出会いのチャンス')}

💕恋愛運のピーク
14:00-16:00

🍀今日のラッキーアクション
「初めての道を通る」

素敵な一日を！"""
    
    def send_weekly_fortunes(self):
        """週間占い配信（月曜日）"""
        print(f"Starting weekly fortune delivery at {datetime.now(JST)}")
        
        users_data = self.load_users_data()
        
        for user_id, user_data in users_data.items():
            if not user_data.get('onboarding_complete', False):
                continue
            
            # 有料ユーザーのみ（または全員）
            if not user_data.get('is_premium', True):
                continue
            
            try:
                weekly_message = self.generate_weekly_fortune(user_data)
                
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(text=weekly_message)
                )
                
            except Exception as e:
                print(f"Error sending weekly to {user_id}: {e}")
    
    def generate_weekly_fortune(self, user_data):
        """週間占い生成"""
        name = user_data.get('name', 'あなた')
        animal = user_data.get('animal_character', {})
        
        prompt = f"""
{name}さんの今週の恋愛運を作成してください。

動物占い：{animal.get('name', '')}
恋愛状況：{user_data.get('relationship_status', '')}

150文字程度で：
1. 今週の全体運
2. 特に良い日（曜日）
3. 注意すべき日
4. 週間ラッキーアイテム

グラフィカルに星（★☆）を使って表現。
"""

        try:
            response = model.generate_content(prompt)
            return f"""📅 {name}さんの週間恋愛運 📅

{response.text}

詳細な日別診断は有料プランで！"""
            
        except:
            return f"""📅 {name}さんの週間恋愛運 📅

月：★★★☆☆ 準備期間
火：★★★★☆ 上昇開始
水：★★★★★ 最高潮！
木：★★★★☆ 継続良好
金：★★★☆☆ 一休み
土：★★★★☆ デート日和
日：★★★☆☆ 充電日

今週のテーマ：「素直な気持ち」"""

# スケジューラーのインスタンス
fortune_scheduler = FortuneScheduler()

# アプリケーション起動時に開始
def init_scheduler():
    fortune_scheduler.start()

# アプリケーション終了時に停止
def shutdown_scheduler():
    fortune_scheduler.shutdown()
