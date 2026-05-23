import os
import logging
import mimetypes

from flask import Flask, request, send_from_directory
from sqlalchemy import text

from config import Config
from models import User, db
from routes import register_routes


# Windows can report .css as application/x-css, which modern browsers may reject.
mimetypes.add_type("text/css", ".css")


# 共通ログ設定：AI呼び出し、保存失敗などを error.log に出力する。
logging.basicConfig(
    filename="error.log",
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s"
)


def ensure_user_schema():
    """既存DBにも管理者フラグを追加し、デモ中の手動削除を不要にする。"""
    columns = db.session.execute(text("PRAGMA table_info(user)")).fetchall()
    column_names = {column[1] for column in columns}
    if "is_admin" not in column_names:
        db.session.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))
    if "can_access" not in column_names:
        db.session.execute(text("ALTER TABLE user ADD COLUMN can_access BOOLEAN NOT NULL DEFAULT 0"))
    db.session.commit()


def ensure_user_choice_schema():
    """既存DBの判定イベント列を追加する。"""
    columns = db.session.execute(text("PRAGMA table_info(user_choice)")).fetchall()
    column_names = {column[1] for column in columns}
    migrations = {
        "edited_text": "ALTER TABLE user_choice ADD COLUMN edited_text TEXT",
        "reject_reason": "ALTER TABLE user_choice ADD COLUMN reject_reason TEXT",
        "review_note": "ALTER TABLE user_choice ADD COLUMN review_note TEXT",
        "decision_tier": "ALTER TABLE user_choice ADD COLUMN decision_tier VARCHAR(20)",
        "status": "ALTER TABLE user_choice ADD COLUMN status VARCHAR(20)",
    }
    for column_name, ddl in migrations.items():
        if column_name not in column_names:
            db.session.execute(text(ddl))
    db.session.commit()


def ensure_default_admin():
    """デモ用の管理者アカウントが無い場合だけ作成する。"""
    admin = User.query.filter_by(username="admin").first()
    if admin:
        return
    else:
        admin = User(username="admin", is_admin=True)
        admin.set_password("123456")
        db.session.add(admin)
        db.session.commit()


def create_app():
    """Flaskアプリを作成し、設定・DB・ルートを初期化する。"""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    @app.route('/style.css')
    def style_css():
        """Serve the stylesheet with a browser-safe MIME type."""
        return send_from_directory(app.static_folder, 'style.css', mimetype='text/css')

    register_routes(app)

    @app.after_request
    def force_css_mime_type(response):
        """Serve CSS with the standard MIME type on Windows."""
        if request.path.endswith(".css"):
            response.headers["Content-Type"] = "text/css; charset=utf-8"
        return response

    # デモ段階では自動でテーブルを作成する。本番では Flask-Migrate への置き換えを想定。
    with app.app_context():
        db.create_all()
        ensure_user_schema()
        ensure_user_choice_schema()
        ensure_default_admin()

    return app


app = create_app()


if __name__ == '__main__':
    # 環境変数でローカル起動設定を変更できる。デフォルトは 127.0.0.1:5000。
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host=host, port=port)
