import logging

from flask import flash, redirect, render_template, request, session, url_for

from application.constants.decision_constants import DECISION_TIER_DESCRIPTIONS, DECISION_TIER_OPTIONS
from application.services.ai_service import MIN_CANDIDATES, get_ai_candidates
from application.services.content_library_service import get_pending_choices as get_user_pending_choices
from application.services.decision_service import build_user_choice, validate_decision_form
from models import AiGeneration, UserChoice, db

from .session_helpers import (
    clear_pending_generation_session,
    clear_session_state,
    get_current_user,
    get_pending_progress,
)


def flash_decision_result(decision_tier, remaining_count):
    """単候補の判定結果を通知する。"""
    progress = f"（残り {remaining_count} 件）" if remaining_count else "（このラウンドの候補はすべて判定済み）"
    if decision_tier == 'adopt':
        flash(f"採用しました。コンテンツライブラリへ反映しました。{progress}")
    elif decision_tier == 'revise_adopt':
        flash(f"修正内容を採用しました。コンテンツライブラリへ反映しました。{progress}")
    elif decision_tier == 'reject':
        flash(f"不採用理由を保存しました。次回生成の調整に使います。{progress}")
    else:
        flash(f"要確認として保存しました。次回生成には反映しません。{progress}")


def require_dashboard_user():
    """通常ユーザー用画面に入れるユーザーを返す。失敗時は遷移レスポンスを返す。"""
    current_user = get_current_user()
    if not current_user:
        clear_session_state()
        return None, redirect(url_for('login'))
    if current_user.is_admin:
        return None, redirect(url_for('admin_panel'))
    if not current_user.can_access:
        flash('システム利用権限がありません。管理者にお問い合わせください。')
        clear_session_state()
        return None, redirect(url_for('login'))
    return current_user, None


def handle_chat_action(user_id):
    """AI候補生成を実行し、判定待ち候補をセッション（session）へ保存する。"""
    message = request.form.get('message', '').strip()
    if not message:
        flash("メッセージを空にすることはできません。")
        return None

    # テーブル2：今回の入力とAIの完全な返答を先に保存する。
    ai_response_text, candidates = get_ai_candidates(message, user_id=user_id)
    generation = AiGeneration(
        user_id=user_id,
        input_text=message,
        ai_response_text=ai_response_text
    )
    db.session.add(generation)
    try:
        db.session.commit()
        if not candidates:
            flash("利用できる候補がありませんでした。入力内容を調整して再生成してください。")
            return redirect(url_for('dashboard'))
        if len(candidates) < MIN_CANDIDATES:
            flash(
                f"候補が{len(candidates)}個しか生成されませんでした。"
                f"通常は{MIN_CANDIDATES}個以上出ます。必要なら再生成してください。"
            )

        # 候補はセッションに一時保存し、次の選択操作を待つ。
        session['pending_generation_id'] = generation.id
        session['pending_prompt'] = message
        session['pending_candidates'] = candidates
        session['pending_initial_count'] = len(candidates)
    except Exception as e:
        db.session.rollback()
        logging.error(f"AI生成記録保存時のエラー: {str(e)}")
        flash("AI生成記録の保存中にエラーが発生しました。")
    return None


def handle_decide_action(user_id):
    """候補への4段階判定を保存し、残り候補をセッション（session）へ戻す。"""
    selected_text = request.form.get('selected_text', '').strip()
    decision_tier = request.form.get('decision_tier', '').strip()
    edited_text = request.form.get('edited_text', '').strip()
    reject_reason = request.form.get('reject_reason', '').strip()
    review_note = request.form.get('review_note', '').strip()
    generation_id = request.form.get('generation_id') or session.get('pending_generation_id')
    generation = AiGeneration.query.filter_by(id=generation_id, user_id=user_id).first()
    pending_candidates = session.get('pending_candidates', [])

    if not generation:
        flash("生成記録が見つかりません。もう一度入力してください。")
        return None
    if selected_text not in pending_candidates:
        flash("この候補は既に判定済みか、現在の一覧にありません。")
        return None
    if UserChoice.query.filter_by(
        user_id=user_id,
        generation_id=generation.id,
        selected_text=selected_text,
    ).first():
        session['pending_candidates'] = [
            candidate for candidate in pending_candidates if candidate != selected_text
        ]
        flash("この候補は既に判定済みです。")
        return redirect(url_for('dashboard'))

    is_valid, error_message, cleaned_fields = validate_decision_form(
        decision_tier=decision_tier,
        selected_text=selected_text,
        edited_text=edited_text,
        reject_reason=reject_reason,
        review_note=review_note,
    )
    if not is_valid:
        flash(error_message)
        return None

    choice = build_user_choice(
        user_id=user_id,
        generation=generation,
        decision_tier=decision_tier,
        cleaned_fields=cleaned_fields,
    )
    db.session.add(choice)
    try:
        db.session.commit()
        remaining_candidates = [
            candidate for candidate in pending_candidates
            if candidate != selected_text
        ]
        session['pending_candidates'] = remaining_candidates
        flash_decision_result(
            decision_tier,
            remaining_count=len(remaining_candidates),
        )
        return redirect(url_for('dashboard'))
    except Exception as e:
        db.session.rollback()
        logging.error(f"判定保存時のエラー: {str(e)}")
        flash("判定内容の保存中にエラーが発生しました。")
        return None


def handle_finish_review_action():
    """進行中の候補判定ラウンドを終了する。"""
    generation_id = request.form.get('generation_id') or session.get('pending_generation_id')
    if not generation_id:
        flash("進行中の候補ラウンドはありません。")
    else:
        clear_pending_generation_session()
        flash("このラウンドを終了しました。未判定の候補は破棄されます。")
    return redirect(url_for('dashboard'))


def register_dashboard_routes(app):
    """一般ユーザー用ダッシュボードのルートを登録する。"""

    @app.route('/dashboard', methods=['GET', 'POST'])
    def dashboard():
        # ダッシュボードの表示はDB上の現在ユーザーを基準にし、セッション上の名前だけを信用しない。
        current_user, error_response = require_dashboard_user()
        if error_response:
            return error_response

        user_id = current_user.id
        username = current_user.username

        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'chat':
                response = handle_chat_action(user_id)
                if response:
                    return response

            elif action == 'decide':
                response = handle_decide_action(user_id)
                if response:
                    return response

            elif action == 'finish_review':
                return handle_finish_review_action()

        # Dashboardは通常ユーザー専用なので、自分の履歴だけを表示する。
        input_history = AiGeneration.query.filter_by(user_id=user_id).order_by(AiGeneration.id).all()
        choice_history = UserChoice.query.filter_by(user_id=user_id).order_by(UserChoice.id).all()
        pending_review = get_user_pending_choices(user_id)
        pending_generation_id = session.get('pending_generation_id')
        pending_prompt = session.get('pending_prompt')
        pending_candidates = session.get('pending_candidates', [])
        pending_initial_count, pending_judged_count, _pending_remaining = get_pending_progress(
            user_id,
            pending_generation_id,
            pending_candidates,
        )

        return render_template(
            'dashboard.html',
            input_history=input_history,
            choice_history=choice_history,
            pending_review=pending_review,
            username=username,
            is_admin=False,
            pending_generation_id=pending_generation_id,
            pending_prompt=pending_prompt,
            pending_candidates=pending_candidates,
            pending_initial_count=pending_initial_count,
            pending_judged_count=pending_judged_count,
            decision_tier_options=DECISION_TIER_OPTIONS,
            decision_tier_descriptions=DECISION_TIER_DESCRIPTIONS,
        )
