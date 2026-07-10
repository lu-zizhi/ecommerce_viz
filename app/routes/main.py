from flask import Blueprint, render_template, jsonify
from app.models import Order, DailyMetrics
from app import db
from sqlalchemy import func
from flask_login import login_required  # 引入加锁工具

main_bp = Blueprint('main', __name__)
@main_bp.route('/')
@login_required  # 挂上这把锁
def index():
    return render_template('dashboard.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@main_bp.route('/api/daily-metrics')
@login_required
def api_daily_metrics():
    """折线图数据：每日销售额和订单数"""
    metrics = DailyMetrics.query.order_by(DailyMetrics.date).all()
    return jsonify({
        'dates': [m.date.strftime('%Y-%m-%d') for m in metrics],
        'revenue': [m.total_revenue for m in metrics],
        'orders': [m.total_orders for m in metrics],
        'avg_order_value': [m.avg_order_value for m in metrics]
    })


@main_bp.route('/api/category-sales')
@login_required
def api_category_sales():
    """饼图数据：各品类销售额占比"""
    results = db.session.query(
        Order.category,
        func.sum(Order.amount).label('total')
    ).filter(
        Order.category.isnot(None),
        Order.status != 'Cancelled'
    ).group_by(Order.category).order_by(func.sum(Order.amount).desc()).limit(8).all()

    return jsonify([
        {'name': r.category, 'value': round(r.total or 0, 2)}
        for r in results
    ])


@main_bp.route('/api/state-orders')
@login_required
def api_state_orders():
    """柱状图数据：各省份订单量 Top10"""
    results = db.session.query(
        Order.ship_state,
        func.count(Order.id).label('count')
    ).filter(
        Order.ship_state.isnot(None),
        Order.ship_state != '未知'
    ).group_by(Order.ship_state).order_by(func.count(Order.id).desc()).limit(10).all()

    return jsonify({
        'states': [r.ship_state for r in results],
        'counts': [r.count for r in results]
    })


@main_bp.route('/api/order-status')
@login_required
def api_order_status():
    """饼图数据：订单状态分布"""
    results = db.session.query(
        Order.status,
        func.count(Order.id).label('count')
    ).group_by(Order.status).all()

    return jsonify([
        {'name': r.status, 'value': r.count}
        for r in results
    ])


@main_bp.route('/api/summary')
@login_required
def api_summary():
    """看板顶部汇总数字"""
    total_revenue = db.session.query(
        func.sum(Order.amount)
    ).filter(Order.status != 'Cancelled').scalar() or 0

    total_orders = Order.query.filter(
        Order.status != 'Cancelled'
    ).count()

    total_products = db.session.query(
        func.count(func.distinct(Order.sku))
    ).scalar() or 0

    cancelled = Order.query.filter(
        Order.status == 'Cancelled'
    ).count()

    cancel_rate = round(cancelled / Order.query.count() * 100, 1) if Order.query.count() > 0 else 0

    return jsonify({
        'total_revenue': round(total_revenue, 2),
        'total_orders': total_orders,
        'total_products': total_products,
        'cancel_rate': cancel_rate
    })