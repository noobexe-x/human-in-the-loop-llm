from flask import flash, redirect, render_template, request, session, url_for

from models import User

from .session_helpers import clear_session_state, get_current_user


def register_auth_routes(app):
    """ホーム、ログイン、ログアウトのルートを登録する。"""

    @app.route('/')
    def home():
        current_user = get_current_user()
        if current_user:
            if current_user.is_admin:
                return redirect(url_for('admin_panel'))
            if current_user.can_access:
                return redirect(url_for('dashboard'))
            clear_session_state()
        return render_template('home.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        # ログイン画面へ入る時点で旧ログイン状態を消し、同じブラウザでのテストをしやすくする。
        if request.method == 'GET' and 'user_id' in session:
            clear_session_state()

        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if not user.is_admin and not user.can_access:
                    flash('システム利用権限がありません。管理者にお問い合わせください。')
                    return render_template('login.html')
                # ログイン成功後にセッションを書き直し、前ユーザーの未選択候補が混ざらないようにする。
                clear_session_state()
                session['user_id'] = user.id
                session['username'] = user.username
                session['is_admin'] = user.is_admin
                if user.is_admin:
                    return redirect(url_for('admin_panel'))
                return redirect(url_for('dashboard'))
            flash('ユーザー名またはパスワードが正しくありません。')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        clear_session_state()
        return redirect(url_for('home'))
