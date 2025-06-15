import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent,
    ImageMessage, QuickReply, QuickReplyButton, MessageAction
)
import google.generativeai as genai
from datetime import datetime, time
import re

# カスタムモジュール
from fortune_logic import FortuneCalculator
from database import DatabaseManager

app = Flask(__name__)

# 環境変数から取得（デフォルト値付き）
line_bot_api = LineBotApi(os.environ.get('LINE_CHANNEL_ACCESS_TOKEN', ''))
handler = WebhookHandler(os.environ.get('LINE_CHANNEL_SECRET', ''))

# Gemini設定
genai.configure(api_key=os.environ.get('GEMINI_API_KEY', ''))
model = genai.GenerativeModel('gemini-pro')
vision_model = genai.GenerativeModel('gemini-pro-vision')

# データベース初期化を試みる
try:
    db_initialized = DatabaseManager.init_db()
    USE_DATABASE = db_initialized
except Exception as e:
    print(f"Database initialization failed: {e}")
    USE_DATABASE = False

# JSONファイル操作関数（フォールバック用）
def load_users_data_json():
    try:
        with open('users_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users_data_json(data):
    with open('users_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ユーザーデータ操作のラッパー関数
def get_user_data(user_id):
    """ユーザーデータを取得"""
    if USE_DATABASE:
        return DatabaseManager.get_user(user_id)
    else:
        users_data = load_users_data_json()
        return users_data.get(user_id)

def save_user_data(user_id, user_data):
    """ユーザーデータを保存"""
    if USE_DATABASE:
        return DatabaseManager.save_user(user_id, user_data)
    else:
        users_data = load_users_data_json()
        users_data[user_id] = user_data
        save_users_data_json(users_data)
        return True

@app.route("/")
def home():
    return """
    <h1>ポチ恋 Bot is running! 💕</h1>
    <p>1タップ恋愛占い - PostgreSQL版</p>
    """

@app.route("/callback", methods=['POST', 'GET'])
def callback():
    if request.method == 'GET':
        return 'OK', 200

    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id

    # 新規ユーザーをデータベースに追加
    user_data = get_user_data(user_id)
    if not user_data:
        user_data = {
            "created_at": datetime.now().isoformat(),
            "onboarding_stage": 0,
            "onboarding_complete": False
        }
        save_user_data(user_id, user_data)

    welcome_message = """💕ポチ恋へようこそ💕

算命学×動物占い×AI手相診断で
あなただけの恋愛運を毎朝お届け！

まずは、お呼びする名前を
教えてください😊

（例：ゆき、たろう）"""

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=welcome_message)
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # ユーザーデータ確認
    user_data = DatabaseManager.get_user(user_id)
    if not user_data:
        user_data = {
            "created_at": datetime.now().isoformat(),
            "onboarding_stage": 0,
            "onboarding_complete": False
        }
        DatabaseManager.save_user(user_id, user_data)

    # リセットコマンドは常に優先
    if user_message in ["リセット", "reset", "最初から", "やり直し"]:
        user_data = {
            "created_at": datetime.now().isoformat(),
            "onboarding_stage": 0,
            "onboarding_complete": False
        }
        DatabaseManager.save_user(user_id, user_data)
        
        reply = """データをリセットしました！

もう一度最初から始めましょう💕

お呼びする名前を教えてください😊
（例：ゆき、たろう）"""
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return

    # オンボーディング中かチェック
    if not user_data.get("onboarding_complete", False):
        handle_onboarding(event, user_id, user_data)
        return

    # 通常の処理
    handle_regular_message(event, user_id, user_data)

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_simple(event):
    """手相画像の簡易処理"""
    user_id = event.source.user_id
    
    user_data = DatabaseManager.get_user(user_id)
    if not user_data:
        return
    
    # オンボーディング中の手相受付
    if user_data.get("onboarding_stage") == 5:
        # 簡易的な手相分析
        user_data["palm_analysis"] = "手相から素晴らしい恋愛運を感じます！感情線がはっきりしていて、愛情深い性格が表れています。"
        user_data["palm_uploaded_at"] = datetime.now().isoformat()
        user_data["onboarding_complete"] = True
        
        # データベースに保存
        DatabaseManager.save_user(user_id, user_data)
        
        # 初回診断を生成
        fortune = generate_first_fortune_with_all_data(user_data)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=fortune)
        )

def handle_onboarding(event, user_id, user_data):
    stage = user_data.get("onboarding_stage", 0)
    message = event.message.text

    if stage == 0:  # 名前
        user_data["name"] = message
        user_data["onboarding_stage"] = 1
        reply = f"""ありがとうございます、{message}さん✨

次に、性別を教えてください！

👩 女性
👨 男性
🌈 その他/答えたくない"""

        # クイックリプライを使用
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="女性", text="女性")),
            QuickReplyButton(action=MessageAction(label="男性", text="男性")),
            QuickReplyButton(action=MessageAction(label="その他", text="その他"))
        ])
        
        # データベースに保存
        DatabaseManager.save_user(user_id, user_data)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply, quick_reply=quick_reply)
        )
        return

    elif stage == 1:  # 性別
        if message in ["女性", "男性", "その他"]:
            user_data["gender"] = message
            user_data["onboarding_stage"] = 2
            reply = """生年月日を教えてください📅

（例：1995年4月15日）

これで算命学と動物占いが
できるようになります✨"""
        else:
            reply = "ボタンから選んでください😊"

    elif stage == 2:  # 生年月日
        if validate_birthday(message):
            user_data["birthday"] = message
            
            # 算命学と動物占いを計算
            try:
                sanmeigaku = FortuneCalculator.calculate_sanmeigaku(message)
                animal = FortuneCalculator.calculate_animal_character(message)
                
                if sanmeigaku and animal:
                    user_data["sanmeigaku"] = sanmeigaku
                    user_data["animal_character"] = animal
                    
                    reply = f"""素敵！{user_data['name']}さんは
{animal['name']}タイプですね🐾

{animal['traits']}な性格で、
{animal['love']}が特徴です💕

次に、今の恋愛状況は？

1️⃣ 片想い中
2️⃣ 恋人がいる
3️⃣ 復縁したい
4️⃣ 出会いを探してる"""
                else:
                    # エラー時のフォールバック
                    reply = """生年月日を受け付けました！

次に、今の恋愛状況は？

1️⃣ 片想い中
2️⃣ 恋人がいる
3️⃣ 復縁したい
4️⃣ 出会いを探してる"""
                    
            except Exception as e:
                print(f"占い計算エラー: {e}")
                reply = """生年月日を受け付けました！

次に、今の恋愛状況は？

1️⃣ 片想い中
2️⃣ 恋人がいる
3️⃣ 復縁したい
4️⃣ 出会いを探してる"""
            
            user_data["onboarding_stage"] = 3
        else:
            reply = "正しい形式で入力してください😊\n例：1995年4月15日"

    elif stage == 3:  # 恋愛状況
        status_map = {
            "1": "片想い",
            "2": "交際中", 
            "3": "復縁希望",
            "4": "出会い待ち"
        }

        if message in status_map:
            user_data["relationship_status"] = status_map[message]
            user_data["onboarding_stage"] = 4
            reply = """恋愛で一番の悩みは？

1️⃣ タイミングがわからない
2️⃣ 相手の気持ちが不明
3️⃣ 自信がない
4️⃣ 出会いがない

数字で答えてね！"""
        else:
            reply = "1〜4の数字で答えてください😊"

    elif stage == 4:  # 悩み
        concern_map = {
            "1": "タイミング",
            "2": "相手の気持ち",
            "3": "自信",
            "4": "出会い"
        }

        if message in concern_map:
            user_data["main_concern"] = concern_map[message]
            user_data["onboarding_stage"] = 5
            
            reply = """最後に、より精度の高い
占いのために...

📸 手相の写真を送ってください

撮影のコツ：
・明るい場所で
・手のひら全体が写るように
・線がはっきり見えるように

[スキップする] と入力でスキップ可"""
        else:
            reply = "1〜4の数字で答えてください😊"
    
    elif stage == 5:  # 手相待ち
        if message.lower() in ["スキップ", "スキップする", "skip"]:
            user_data["onboarding_complete"] = True
            user_data["palm_analysis"] = None
            
            # データベースに保存
            DatabaseManager.save_user(user_id, user_data)
            
            # 初回診断を生成
            fortune = generate_first_fortune_with_all_data(user_data)
            reply = fortune
        else:
            # 画像は後で処理されるので、ここでは手相以外のテキストに対応
            reply = """手相の写真を送ってください📸

または「スキップする」と入力して
次に進むこともできます！"""

    # データベースに保存
    DatabaseManager.save_user(user_id, user_data)

    # 返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

def validate_birthday(text):
    patterns = [
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
        r'平成(\d{1,2})年(\d{1,2})月(\d{1,2})日',
        r'昭和(\d{1,2})年(\d{1,2})月(\d{1,2})日',
        r'(\d{4})/(\d{1,2})/(\d{1,2})',
        r'(\d{4})-(\d{1,2})-(\d{1,2})'
    ]

    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False

def analyze_palm_image(image_data):
    """手相画像をGemini Vision APIで解析（一時的に簡易版）"""
    # 画像処理ライブラリが使えないため、一時的に固定メッセージを返す
    return "手相から温かい愛情運を感じます。詳細な分析は後日お伝えします。"

def generate_first_fortune_with_all_data(user_data):
    """全データを使った初回診断"""
    animal = user_data.get('animal_character', {})
    sanmeigaku = user_data.get('sanmeigaku', {})
    palm = user_data.get('palm_analysis', '')
    
    prompt = f"""あなたは、ユーザーに親友のように寄り添い、具体的でポジティブな未来を示すカリスマ占い師です。以下の入力情報に基づき、出力要件を厳守して、ユーザーの心を掴む初回診断メッセージを生成してください。

入力情報
* 名前: {user_data.get('name')}
* 性別: {user_data.get('gender')}
* 生年月日: {user_data.get('birthday')}
* 動物占い結果（性格）: {animal.get('traits', '')}
* 動物占い結果（恋愛傾向）: {animal.get('love', '')}
* 算命学結果（十干十二支）: {sanmeigaku.get('element', '')}
* 算命学結果（性格特性）: {sanmeigaku.get('traits', '')}
* 恋愛状況: {user_data.get('relationship_status')}
* 悩み: {user_data.get('main_concern')}
* 手相分析（任意）: {palm if palm else 'なし'}

出力要件
* **文字数:** 300〜400字で厳守
* **構成:** 以下の5つのパートで構成すること
   1. **褒め・共感 (約50字):** {user_data.get('name')}さんを呼びかけ、{user_data.get('relationship_status')}と{user_data.get('main_concern')}に共感し、その気持ちを肯定する。
   2. **性格分析 (約100字):** {animal.get('traits', '')}と{sanmeigaku.get('traits', '')}を組み合わせ、**まず「〇〇な△△」のようなキャッチコピーを生成し、**その後にポジティブな言葉で「あなただけの特別な魅力」として表現する。手相情報があれば、それも加味して深みを出す。**もし手相情報がなければ、この要素には一切触れないこと。**
   3. **今週の具体的な恋愛運 (約100字):** {user_data.get('relationship_status')}に応じたポジティブな出来事が起こる「曜日」と「時間帯（例: 14:15-14:45）」、「場所（例: カフェ、職場の休憩室）」を具体的に断定して予言する。
   4. **悩みへの具体的解決策 (約100字):** {user_data.get('main_concern')}を解決するための、非常に具体的で簡単なアクションを提示する。{animal.get('love', '')}の傾向も踏まえて、その人らしいアプローチを提案する。
   5. **明日への期待感 (約50字):** 未来への希望を抱かせる、力強く前向きなメッセージで締めくくる。

* **トーン:**
   * 親友のように親しみやすく、タメ口も少し交える感じで。
   * 希望を持たせる前向きな表現を徹底する。
   * 「〜かもしれません」ではなく「〜です！」「〜します！」と断定する。
   * 絵文字を各文に1つ程度使用し、感情を豊かに表現する。"""

    try:
        response = model.generate_content(prompt)
        return f"""🔮 {user_data.get('name')}さんの診断結果 🔮

{response.text}

💫 明日から毎朝7時に
あなただけの占いをお届けします！"""
    except:
        return f"""🔮 {user_data.get('name')}さんの診断結果 🔮

{animal.get('name', '')}タイプのあなたは
{animal.get('traits', '')}な魅力の持ち主！

今週は恋愛運が上昇中✨
特に木曜の午後が最高のタイミング。

{user_data.get('main_concern')}の悩みは
もうすぐ解決の兆しが見えそう💕

明日の朝7時に詳細な占いをお届けします！"""

def generate_daily_morning_fortune(user_data):
    """毎朝の占い生成（パーソナライズ版）"""
    now = datetime.now()
    animal = user_data.get('animal_character', {})
    sanmeigaku = user_data.get('sanmeigaku', {})
    
    # 今日の運勢を算命学で計算
    daily_fortune = FortuneCalculator.get_daily_element_fortune(
        sanmeigaku.get('jikkan', '甲')
    )
    
    prompt = f"""
{user_data.get('name')}さんへの今日の占いを作成してください。

【基本情報】
日付：{now.strftime('%m月%d日')}
動物占い：{animal.get('name', '')}
算命学：{sanmeigaku.get('element', '')}
今日の相性：{daily_fortune.get('compatibility', '')}

【ユーザー情報】
恋愛状況：{user_data.get('relationship_status')}
悩み：{user_data.get('main_concern')}

250文字程度で以下を含めて：
1. 今日の総合運（5段階の星）
2. 恋愛運と具体的な時間帯
3. ラッキーアクション（具体的に）
4. 注意点

親しみやすく、前向きな内容で。
"""

    try:
        response = model.generate_content(prompt)
        
        return f"""おはようございます、{user_data.get('name')}さん☀️

【{now.strftime('%m月%d日')}の運勢】
算命学×{animal.get('name', '')}の診断

{response.text}

詳細診断を見る >"""
        
    except:
        return f"""おはようございます、{user_data.get('name')}さん☀️

【{now.strftime('%m月%d日')}の運勢】
総合運：{daily_fortune.get('compatibility', '★★★')}

{animal.get('name', '')}の今日は
新しいことに挑戦する日！

💕恋愛運
午後2-4時がゴールデンタイム

🔮ラッキーアクション
利き手じゃない方で何かをする

詳細診断を見る >"""

def handle_regular_message(event, user_id, user_data):
    user_message = event.message.text

    if "診断" in user_message or "占い" in user_message:
        reply = generate_daily_morning_fortune(user_data)
    elif "相性" in user_message:
        reply = """相性診断をご希望ですね💕

相手の生年月日を教えてください！
（例：1996年8月20日）

※算命学による本格相性診断は
有料プランでさらに詳しく！"""
    elif "料金" in user_message or "プラン" in user_message:
        reply = """💰 料金プラン 💰

【月額プラン】
通常：980円/月
初月：100円（90%OFF）

【特典】
✅ 毎朝の詳細占い（時間別）
✅ 算命学の相性診断
✅ 手相の定期診断
✅ 恋愛相談チャット
✅ 新月・満月の特別占い

まずは100円でお試し！"""
    else:
        # クイックリプライで選択肢を提示
        reply = "何をお知りになりたいですか？"
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="今日の占い", text="占い")),
            QuickReplyButton(action=MessageAction(label="相性診断", text="相性")),
            QuickReplyButton(action=MessageAction(label="料金プラン", text="料金"))
        ])
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply, quick_reply=quick_reply)
        )
        return

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    # スケジューラーを起動
    from scheduler import init_scheduler, shutdown_scheduler
    import atexit
    
    # スケジューラー開始
    init_scheduler()
    
    # 終了時の処理
    atexit.register(shutdown_scheduler)
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
