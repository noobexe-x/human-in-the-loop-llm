from application.constants.decision_constants import DECISION_TIER_LABELS, STATUS_PUBLISHED, STATUS_REJECTED
from models import AiGeneration, User, UserChoice, db


def search_non_admin_users(search_query):
    """管理画面用に、IDまたはユーザー名で一般ユーザーを検索する。"""
    query = User.query.filter_by(is_admin=False)
    if search_query:
        if search_query.isdigit():
            query = query.filter(User.id == int(search_query))
        else:
            query = query.filter(User.username.ilike(f"%{search_query}%"))
    return query.order_by(User.id).all()


def get_non_admin_user_by_username(username):
    """管理者が閲覧できる一般ユーザーだけを取得する。"""
    return User.query.filter_by(username=username, is_admin=False).first()


def get_user_question_history(user_id):
    """指定ユーザーのAI問い合わせ履歴を古い順で取得する。"""
    return (
        AiGeneration.query
        .filter_by(user_id=user_id)
        .order_by(AiGeneration.id)
        .all()
    )


def get_user_choice_history(user_id):
    """指定ユーザーの選択履歴を古い順で取得する。"""
    return (
        UserChoice.query
        .filter_by(user_id=user_id)
        .order_by(UserChoice.id)
        .all()
    )


def get_user_decision_tier_counts(user_id):
    """4段階判定の件数をUserChoiceから直接集計する。"""
    counts = {tier: 0 for tier in DECISION_TIER_LABELS}
    choices = UserChoice.query.filter_by(user_id=user_id).all()
    for choice in choices:
        if choice.decision_tier in counts:
            counts[choice.decision_tier] += 1
    return counts


def get_user_published_choices(user_id, limit=10):
    """Promptへ正例として戻す採用済みコンテンツを取得する。"""
    return (
        UserChoice.query
        .filter_by(user_id=user_id, status=STATUS_PUBLISHED)
        .order_by(UserChoice.created_at.desc())
        .limit(limit)
        .all()
    )


def get_user_rejected_choices(user_id, limit=10):
    """Prompt調整に使う不採用理由がある判定を取得する。"""
    return (
        UserChoice.query
        .filter_by(user_id=user_id, status=STATUS_REJECTED)
        .filter(UserChoice.reject_reason.isnot(None))
        .filter(UserChoice.reject_reason != "")
        .order_by(UserChoice.created_at.desc())
        .limit(limit)
        .all()
    )


def create_user(username, password, grant_access=False):
    """管理者が一般ユーザーを作成する。公開登録は提供しない。"""
    username = username.strip()
    if not username:
        return False, "ユーザー名を入力してください。"
    if not password:
        return False, "パスワードを入力してください。"
    if User.query.filter_by(username=username).first():
        return False, "このユーザー名はすでに使用されています。"

    user = User(username=username, is_admin=False, can_access=grant_access)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return True, None


def set_user_access(user_id, can_access):
    """一般ユーザーのシステム利用権限を更新する。管理者は対象外。"""
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        return False, "対象ユーザーが見つかりません。"
    user.can_access = can_access
    db.session.commit()
    return True, None
