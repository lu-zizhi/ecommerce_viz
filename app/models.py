from app import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    """用户表"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(256), nullable=False, comment='密码哈希')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        """生成密码哈希，绝对不允许明文存入数据库"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Product(db.Model):
    """商品表"""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=False, comment='SKU编码')
    design_no = db.Column(db.String(64), comment='款式编号')
    category = db.Column(db.String(64), comment='商品类目')
    size = db.Column(db.String(32), comment='尺码')
    color = db.Column(db.String(32), comment='颜色')
    stock = db.Column(db.Integer, default=0, comment='库存数量')
    mrp = db.Column(db.Float, comment='建议零售价')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'design_no': self.design_no,
            'category': self.category,
            'size': self.size,
            'color': self.color,
            'stock': self.stock,
            'mrp': self.mrp
        }


class Order(db.Model):
    """订单表"""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), unique=True, nullable=False, comment='订单ID')
    date = db.Column(db.Date, comment='下单日期')
    status = db.Column(db.String(64), comment='订单状态')
    fulfilment = db.Column(db.String(32), comment='履约方式')
    sales_channel = db.Column(db.String(64), comment='销售渠道')
    category = db.Column(db.String(64), comment='商品类目')
    sku = db.Column(db.String(64), comment='SKU编码')
    size = db.Column(db.String(32), comment='尺码')
    quantity = db.Column(db.Integer, default=0, comment='购买数量')
    amount = db.Column(db.Float, comment='销售额')
    currency = db.Column(db.String(16), default='INR', comment='货币')
    ship_city = db.Column(db.String(64), comment='收货城市')
    ship_state = db.Column(db.String(64), comment='收货省份')
    ship_country = db.Column(db.String(32), comment='收货国家')
    b2b = db.Column(db.Boolean, default=False, comment='是否B2B订单')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'status': self.status,
            'fulfilment': self.fulfilment,
            'sales_channel': self.sales_channel,
            'category': self.category,
            'sku': self.sku,
            'size': self.size,
            'quantity': self.quantity,
            'amount': self.amount,
            'currency': self.currency,
            'ship_city': self.ship_city,
            'ship_state': self.ship_state,
            'ship_country': self.ship_country,
            'b2b': self.b2b
        }


class DailyMetrics(db.Model):
    """每日汇总指标表"""
    __tablename__ = 'daily_metrics'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, comment='日期')
    total_orders = db.Column(db.Integer, default=0, comment='总订单数')
    total_revenue = db.Column(db.Float, default=0.0, comment='总销售额')
    avg_order_value = db.Column(db.Float, default=0.0, comment='平均客单价')
    cancelled_orders = db.Column(db.Integer, default=0, comment='取消订单数')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'date': self.date.strftime('%Y-%m-%d'),
            'total_orders': self.total_orders,
            'total_revenue': self.total_revenue,
            'avg_order_value': self.avg_order_value,
            'cancelled_orders': self.cancelled_orders
        }

class ChatMessage(db.Model):
    """AI 智能分析多轮对话历史表"""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='所属用户')
    role = db.Column(db.String(16), nullable=False, comment='角色: user 或 assistant')
    content = db.Column(db.Text, nullable=False, comment='消息内容(文本或结构化JSON)')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }