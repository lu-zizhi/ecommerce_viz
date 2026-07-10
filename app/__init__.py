from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager  # 确保引入了登录管理器
from config import Config


db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)

    # 2. 初始化数据库
    db.init_app(app)

    # 3. 把登录管理器正式注册到当前运行的 app 对象中
    print("====== [系统状态] 正在向 Flask 核心注入登录管理器... ======")
    login_manager.init_app(app)

    login_manager.login_view = 'auth.login'  # 设定未登录时重定向的路由
    login_manager.login_message = '请先登录以访问跨境电商可视化系统'
    login_manager.login_message_category = 'warning'

    # 4. 告诉 Flask-Login 怎么通过 Session 里的用户 ID 去数据库捞人
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 5. 注册全套业务蓝图（确保包含新写的 auth_bp）
    from app.routes.main import main_bp
    from app.routes.data import data_bp
    from app.routes.ai import ai_bp
    from app.routes.auth import auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(data_bp, url_prefix='/data')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # 6. 自动建表（此时 users 表会被自动刷进数据库）
    with app.app_context():
        db.create_all()

    return app