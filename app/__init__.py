from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

# 创建数据库对象（此时还没有绑定app，后面在create_app里绑定）
db = SQLAlchemy()


def create_app():
    # 创建 Flask 实例，告诉它静态文件和模板在哪里
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # 加载 config.py 里的配置
    app.config.from_object(Config)

    # 把数据库绑定到这个 app
    db.init_app(app)

    # 注册 Blueprint（路由模块）
    # 💡 Blueprint 就是把路由分文件管理，每个模块各管各的
    from app.routes.main import main_bp
    from app.routes.data import data_bp
    from app.routes.ai import ai_bp

    app.register_blueprint(main_bp)  # 首页/看板路由
    app.register_blueprint(data_bp, url_prefix='/data')  # 数据管理路由，url前缀/data
    app.register_blueprint(ai_bp, url_prefix='/ai')  # AI分析路由，url前缀/ai

    # 自动创建数据库表（如果不存在）
    with app.app_context():
        from app import models  # 先导入模型，让SQLAlchemy知道有哪些表
        db.create_all()

    return app