import os

from dotenv import load_dotenv


# .env から SECRET_KEY や DeepSeek API 設定などの値を読み込む。
load_dotenv()


class Config:
    """アプリ設定をここに集約し、ルートやサービス層へ散らばらないようにする。"""

    # Flask-SQLAlchemy は相対パスの SQLite DB を instance/chat.db に配置する。
    SQLALCHEMY_DATABASE_URI = 'sqlite:///chat.db'
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # デモ用のトークン上限。.env の DEMO_MAX_TOKENS で調整できる。
    DEMO_MAX_TOKENS = int(os.getenv("DEMO_MAX_TOKENS", "500"))

    # DeepSeek は OpenAI SDK 互換 API として呼び出す。
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
    DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL')
