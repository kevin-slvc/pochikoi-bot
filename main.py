import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
import google.generativeai as genai
from datetime import datetime
import re

app = Flask(__name__)

# 環境変数から取得
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

# Gemini設定
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-pro')

# JSONファイル操作関数
def load_users_data():
    try:
        with open('users_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_users_data(data):
    with open('users_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# グローバル変数として読み込み
users_data = load_users_data()

@app.route("/")
def home():
    return """
    <h1>ポチ恋 Bot is running! 💕</h1>
    <p>1タップ恋愛占い</p>
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

    # 新規ユーザーをデータに追加
    if user_id not in users_data:
        users_data[user_id] = {
            "created_at": datetime.now().isoformat(),
            "onboarding_stage": 0
        }
        save_users_data(users_data)

    welcome_message = """💕ポチ恋へようこそ💕

30秒で終わる質問に答えて
あなた専用の恋愛運を
チェックしましょう✨

まずは生年月日を教えてください
（例：1995年4月15日）"""

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=welcome_message)
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # ユーザーデータ確認
    if user_id not in users_data:
        users_data[user_id] = {
            "created_at": datetime.now().isoformat(),
            "onboarding_stage": 0
        }

    user = users_data[user_id]

    # オンボーディング中かチェック
    if "onboarding_complete" not in user or not user["onboarding_complete"]:
        handle_onboarding(event, user_id)
        return

    # 通常の処理
    handle_regular_message(event, user_id)

def handle_onboarding(event, user_id):
    user = users_data[user_id]
    stage = user.get("onboarding_stage", 0)
    message = event.message.text

    if stage == 0:  # ウェルカムメッセージ
        reply = """💕ポチ恋へようこそ💕

30秒で終わる質問に答えて
あなた専用の恋愛運を
チェックしましょう✨

まずは生年月日を教えてください
（例：1995年4月15日）"""
        user["onboarding_stage"] = 1

    elif stage == 1:  # 生年月日受け取り
        if validate_birthday(message):
            user["birthday"] = message
            user["onboarding_stage"] = 2
            reply = """ありがとうございます💕

次の質問です！
今の恋愛状況は？

1️⃣ 片想い中
2️⃣ 恋人がいる
3️⃣ 復縁したい
4️⃣ 出会いを探してる

数字で答えてね！"""
        else:
            reply = "正しい形式で入力してください😊\n例：1995年4月15日"

    elif stage == 2:  # 恋愛状況
        status_map = {
            "1": "片想い",
            "2": "交際中", 
            "3": "復縁希望",
            "4": "出会い待ち"
        }

        if message in status_map:
            user["relationship_status"] = status_map[message]
            user["onboarding_stage"] = 3
            reply = """最後の質問！

恋愛で一番の悩みは？

1️⃣ タイミングがわからない
2️⃣ 相手の気持ちが不明
3️⃣ 自信がない
4️⃣ 出会いがない

数字で答えてね！"""
        else:
            reply = "1〜4の数字で答えてください😊"

    elif stage == 3:  # 悩み
        concern_map = {
            "1": "タイミング",
            "2": "相手の気持ち",
            "3": "自信",
            "4": "出会い"
        }

        if message in concern_map:
            user["main_concern"] = concern_map[message]
            user["onboarding_complete"] = True

            # 初回診断を生成
            fortune = generate_first_fortune(user)
            reply = fortune
        else:
            reply = "1〜4の数字で答えてください😊"

    # データ保存
    save_users_data(users_data)

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

def generate_first_fortune(user):
    prompt = f"""
    初回の特別診断を作成してください。

    生年月日：{user['birthday']}
    恋愛状況：{user['relationship_status']}
    主な悩み：{user['main_concern']}

    200文字程度で、以下を含めて：
    1. 基本性格の良い面
    2. 恋愛での強み
    3. 今週の恋愛運
    4. 具体的なアドバイス

    絵文字を使って親しみやすく。
    最後に「毎日の詳細な占いは有料プラン（月額980円）で！」
    """

    try:
        response = model.generate_content(prompt)
        return "🔮 あなたの診断結果 🔮\n\n" + response.text
    except:
        return """🔮 あなたの診断結果 🔮

素敵な恋愛体質の持ち主ですね💕
今週は特に出会い運が高まっています！

積極的に行動することで
良い結果が期待できそう✨

毎日の詳細な占いは
有料プラン（月額980円）で！"""

def handle_regular_message(event, user_id):
    user = users_data[user_id]
    user_message = event.message.text

    if "診断" in user_message or "占い" in user_message:
        reply = generate_daily_fortune(user)
    elif "相性" in user_message:
        reply = """相性診断をご希望ですね💕

相手の生年月日を教えてください！
（例：1996年8月20日）

※詳細な相性診断は有料プランで
もっと詳しく見れます！"""
    elif "料金" in user_message or "プラン" in user_message:
        reply = """💰 料金プラン 💰

【月額プラン】
通常：980円/月
初月：100円（90%OFF）

【できること】
✅ 毎日の詳細占い
✅ LINE添削（無制限）
✅ 恋愛相談24時間
✅ 最適タイミング通知

まずは100円でお試し！"""
    else:
        reply = """メニューから選んでください💕

・今日の占い→「診断」
・相性診断→「相性」
・料金プラン→「料金」

と送信してね！"""

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

def generate_daily_fortune(user):
    prompt = f"""
    今日の恋愛運を占ってください。

    ユーザー情報：
    生年月日：{user.get('birthday', '不明')}
    恋愛状況：{user.get('relationship_status', '不明')}

    100文字程度で簡潔に。
    最後に「詳細は有料プランで！」を追加。
    """

    try:
        response = model.generate_content(prompt)
        return "💫 今日の恋愛運 💫\n\n" + response.text
    except:
        return """💫 今日の恋愛運 💫

今日は恋愛運が上昇中！
積極的な行動が吉です💕

詳細は有料プランで！"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)