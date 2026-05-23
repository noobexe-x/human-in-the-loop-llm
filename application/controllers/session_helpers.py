from flask import session

from models import User, UserChoice, db


def clear_session_state():
    """ブラウザのセッションを消去し、ユーザー切り替え時の状態混在を防ぐ。"""
    session.clear()


def clear_pending_generation_session():
    """進行中の候補判定ラウンド用セッションを消去する。"""
    session.pop('pending_generation_id', None)
    session.pop('pending_prompt', None)
    session.pop('pending_candidates', None)
    session.pop('pending_initial_count', None)


def get_pending_progress(user_id, generation_id, pending_candidates):
    """セッション上の候補ラウンド進捗（判定済み件数など）を返す。"""
    initial = session.get('pending_initial_count')
    if initial is None and generation_id:
        judged_in_db = UserChoice.query.filter_by(
            user_id=user_id,
            generation_id=generation_id,
        ).count()
        initial = judged_in_db + len(pending_candidates)
        session['pending_initial_count'] = initial
    remaining = len(pending_candidates)
    judged = max((initial or 0) - remaining, 0)
    return initial, judged, remaining


def get_current_user():
    """セッションからログイン中ユーザーを取得し、DB上の情報を正とする。"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db.session.get(User, user_id)
