import logging

from flask import flash, redirect, render_template, request, url_for

from application.constants.decision_constants import DECISION_TIER_OPTIONS
from application.services.admin_service import (
    create_user,
    get_non_admin_user_by_username,
    get_user_choice_history,
    get_user_decision_tier_counts,
    get_user_published_choices,
    get_user_question_history,
    get_user_rejected_choices,
    search_non_admin_users,
    set_user_access,
)
from application.services.content_library_service import get_pending_choices as get_user_pending_choices
from models import db

from .session_helpers import clear_session_state, get_current_user


def require_admin_user():
    """管理画面用にログイン済み管理者を返す。失敗時は遷移レスポンスを返す。"""
    current_user = get_current_user()
    if not current_user:
        clear_session_state()
        return None, redirect(url_for('login'))
    if not current_user.is_admin:
        flash("管理者のみアクセスできます。")
        return None, redirect(url_for('dashboard'))
    return current_user, None


def register_admin_routes(app):
    """管理コンソールとユーザー詳細画面のルートを登録する。"""

    @app.route('/admin')
    def admin_panel():
        current_user, error_response = require_admin_user()
        if error_response:
            return error_response

        search_query = request.args.get('q', '').strip()
        users = search_non_admin_users(search_query)

        return render_template(
            'admin.html',
            username=current_user.username,
            is_admin=current_user.is_admin,
            users=users,
            search_query=search_query
        )

    @app.route('/admin/users/<int:user_id>/access', methods=['POST'])
    def admin_set_user_access(user_id):
        _current_user, error_response = require_admin_user()
        if error_response:
            return error_response

        can_access = request.form.get('can_access') == '1'
        search_query = request.form.get('q', '').strip()
        try:
            success, message = set_user_access(user_id, can_access)
            if success:
                flash("システム利用権限を更新しました。")
            else:
                flash(message)
        except Exception as e:
            db.session.rollback()
            logging.error(f"利用権限更新時のエラー: {str(e)}")
            flash("利用権限の更新中にエラーが発生しました。")

        if search_query:
            return redirect(url_for('admin_panel', q=search_query))
        return redirect(url_for('admin_panel'))

    @app.route('/admin/users/create', methods=['POST'])
    def admin_create_user():
        _current_user, error_response = require_admin_user()
        if error_response:
            return error_response

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        grant_access = request.form.get('can_access') == '1'
        search_query = request.form.get('q', '').strip()

        try:
            success, message = create_user(username, password, grant_access=grant_access)
            if success:
                flash("ユーザーを作成しました。")
            else:
                flash(message)
        except Exception as e:
            db.session.rollback()
            logging.error(f"ユーザー作成時のエラー: {str(e)}")
            flash("ユーザー作成中にエラーが発生しました。")

        if search_query:
            return redirect(url_for('admin_panel', q=search_query))
        return redirect(url_for('admin_panel'))

    @app.route('/admin/users')
    def admin_user_detail():
        current_user, error_response = require_admin_user()
        if error_response:
            return error_response

        target_username = request.args.get('username', '').strip()
        target_user = get_non_admin_user_by_username(target_username)
        if not target_user:
            flash("指定した一般ユーザーが見つかりません。")
            return redirect(url_for('admin_panel'))

        input_history = get_user_question_history(target_user.id)
        choice_history = get_user_choice_history(target_user.id)
        decision_tier_counts = get_user_decision_tier_counts(target_user.id)
        published_choices = get_user_published_choices(target_user.id)
        rejected_choices = get_user_rejected_choices(target_user.id)
        pending_choices = get_user_pending_choices(target_user.id)

        return render_template(
            'admin_user.html',
            username=current_user.username,
            is_admin=current_user.is_admin,
            target_user=target_user,
            input_history=input_history,
            choice_history=choice_history,
            decision_tier_counts=decision_tier_counts,
            published_choices=published_choices,
            rejected_choices=rejected_choices,
            pending_choices=pending_choices,
            decision_tier_options=DECISION_TIER_OPTIONS,
        )
