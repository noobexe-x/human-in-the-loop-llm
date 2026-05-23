from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from application.constants.decision_constants import DECISION_TIER_LABELS


# db は app.py で init_app する。モデル層が Flask インスタンスへ直接依存しないようにする。
db = SQLAlchemy()


class User(db.Model):
    """テーブル1：ユーザーアカウント。認証に必要な情報だけを保存する。"""

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    can_access = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)


class AiGeneration(db.Model):
    """テーブル2：AI生成ログ。ユーザー入力とAI APIの完全な返答を保存する。"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    input_text = db.Column(db.Text, nullable=False)
    ai_response_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='ai_generations')


class UserChoice(db.Model):
    """テーブル3：ユーザー判定イベント。候補選択と4段階判定を1行で保存する。"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # テーブル2へ関連付け、選択内容から当時のAI返答全体を追跡できるようにする。
    generation_id = db.Column(db.Integer, db.ForeignKey('ai_generation.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    selected_text = db.Column(db.Text, nullable=False)
    edited_text = db.Column(db.Text, nullable=True)
    reject_reason = db.Column(db.Text, nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    decision_tier = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='choices')
    generation = db.relationship('AiGeneration', backref='choices')

    def canonical_text(self):
        """採用済みコンテンツとしてPromptへ渡す正例テキスト。"""
        if self.decision_tier == "revise_adopt" and self.edited_text:
            return self.edited_text.strip()
        if self.decision_tier == "adopt":
            return self.selected_text.strip()
        return None

    def tier_label(self):
        if not self.decision_tier:
            return "未判定"
        return DECISION_TIER_LABELS.get(self.decision_tier, self.decision_tier)
