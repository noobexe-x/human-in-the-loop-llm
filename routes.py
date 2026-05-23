from application.controllers.admin_controller import register_admin_routes
from application.controllers.auth_controller import register_auth_routes
from application.controllers.dashboard_controller import register_dashboard_routes


def register_routes(app):
    """各ControllerのルートをFlaskアプリへ登録する。"""
    register_auth_routes(app)
    register_admin_routes(app)
    register_dashboard_routes(app)
