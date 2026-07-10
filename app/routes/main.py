from flask import Blueprint, render_template, jsonify, request
from app.models import Order, DailyMetrics
from app import db
from sqlalchemy import func
from flask_login import login_required
from datetime import datetime

main_bp = Blueprint('main', __name__)


def get_filter_args():
    """公共函数：解析前端传来的筛选参数"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    category = request.args.get('category')
    return start_date, end_date, category


@main_bp.route('/')
@login_required
def index():
    return render_template('dashboard.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


@main_bp.route('/api/daily-metrics')
@login_required
def api_daily_metrics():
    """折线图数据：支持日期和品类动态筛选"""
    start_date, end_date, category = get_filter_args()

    # 注意：如果按品类筛选，必须去查 Order 表实时聚合，因为 daily_metrics 表没有品类维度
    if category and category != 'all':
        query = db.session.query(
            Order.date.label('date'),
            func.count(Order.id).label('total_orders'),
            func.sum(Order.amount).label('total_revenue')
        ).filter(Order.date.isnot(None), Order.category == category)

        if start_date:
            query = query.filter(Order.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(Order.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

        results = query.group_by(Order.date).order_by(Order.date).all()

        return jsonify({
            'dates': [r.date.strftime('%Y-%m-%d') for r in results],
            'revenue': [round(r.total_revenue or 0, 2) for r in results],
            'orders': [r.total_orders for r in results]
        })

    # 如果没有品类筛选，继续走高性能的 daily_metrics 预总表
    query = DailyMetrics.query
    if start_date:
        query = query.filter(DailyMetrics.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(DailyMetrics.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

    metrics = query.order_by(DailyMetrics.date).all()
    return jsonify({
        'dates': [m.date.strftime('%Y-%m-%d') for m in metrics],
        'revenue': [m.total_revenue for m in metrics],
        'orders': [m.total_orders for m in metrics],
        'avg_order_value': [m.avg_order_value for m in metrics]
    })


@main_bp.route('/api/category-sales')
@login_required
def api_category_sales():
    """饼图数据：各品类销售额占比（支持日期过滤）"""
    start_date, end_date, _ = get_filter_args()

    query = db.session.query(
        Order.category,
        func.sum(Order.amount).label('total')
    ).filter(Order.category.isnot(None), Order.status != 'Cancelled')

    if start_date:
        query = query.filter(Order.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Order.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

    results = query.group_by(Order.category).order_by(func.sum(Order.amount).desc()).limit(8).all()

    return jsonify([
        {'name': r.category, 'value': round(r.total or 0, 2)}
        for r in results
    ])


@main_bp.route('/api/state-orders')
@login_required
def api_state_orders():
    """柱状图数据：各省份订单量 Top10（支持日期和品类过滤）"""
    start_date, end_date, category = get_filter_args()

    query = db.session.query(
        Order.ship_state,
        func.count(Order.id).label('count')
    ).filter(Order.ship_state.isnot(None), Order.ship_state != '未知')

    if category and category != 'all':
        query = query.filter(Order.category == category)
    if start_date:
        query = query.filter(Order.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Order.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

    results = query.group_by(Order.ship_state).order_by(func.count(Order.id).desc()).limit(10).all()

    return jsonify({
        'states': [r.ship_state for r in results],
        'counts': [r.count for r in results]
    })


@main_bp.route('/api/order-status')
@login_required
def api_order_status():
    """饼图数据：订单状态分布（支持日期和品类过滤）"""
    start_date, end_date, category = get_filter_args()

    query = db.session.query(
        Order.status,
        func.count(Order.id).label('count')
    )

    if category and category != 'all':
        query = query.filter(Order.category == category)
    if start_date:
        query = query.filter(Order.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Order.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

    results = query.group_by(Order.status).all()

    return jsonify([
        {'name': r.status, 'value': r.count}
        for r in results
    ])


@main_bp.route('/api/summary')
@login_required
def api_summary():
    """看板顶部汇总数字（支持日期和品类过滤）"""
    start_date, end_date, category = get_filter_args()

    # 基础过滤条件
    rev_query = db.session.query(func.sum(Order.amount)).filter(Order.status != 'Cancelled')
    ord_query = Order.query.filter(Order.status != 'Cancelled')
    prod_query = db.session.query(func.count(func.distinct(Order.sku)))
    cancel_query = Order.query.filter(Order.status == 'Cancelled')
    total_count_query = Order.query

    # 动态追加全局过滤
    for q in [rev_query, ord_query, prod_query, cancel_query, total_count_query]:
        if category and category != 'all':
            # 特殊处理：如果是 BaseQuery 对象使用 filter，如果是 db.session.query 对象使用 filter 传入条件
            if hasattr(q, 'filter_by'):
                q = q.filter(Order.category == category)
            else:
                q = q.filter(Order.category == category)
        if start_date:
            q = q.filter(Order.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            q = q.filter(Order.date <= datetime.strptime(end_date, '%Y-%m-%d').date())

        # 重新赋回对应的变量
        if q.session:
            if 'sum' in str(q):
                rev_query = q
            elif 'distinct' in str(q):
                prod_query = q
        else:
            if 'status == :status_1' in str(q.statement):
                cancel_query = q
            elif 'status !=' in str(q.statement):
                ord_query = q
            else:
                total_count_query = q

    # 这里的重构为了绝对安全，直接采用最平铺的实时重算执行
    r_q = db.session.query(func.sum(Order.amount)).filter(Order.status != 'Cancelled')
    o_q = db.session.query(func.count(Order.id)).filter(Order.status != 'Cancelled')
    p_q = db.session.query(func.count(func.distinct(Order.sku)))
    c_q = db.session.query(func.count(Order.id)).filter(Order.status == 'Cancelled')
    t_q = db.session.query(func.count(Order.id))

    for idx, query_obj in enumerate([r_q, o_q, p_q, c_q, t_q]):
        if category and category != 'all':
            query_obj = query_obj.filter(Order.category == category)
        if start_date:
            query_obj = query_obj.filter(Order.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query_obj = query_obj.filter(Order.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        if idx == 0:
            r_q = query_obj
        elif idx == 1:
            o_q = query_obj
        elif idx == 2:
            p_q = query_obj
        elif idx == 3:
            c_q = query_obj
        elif idx == 4:
            t_q = query_obj

    total_revenue = r_q.scalar() or 0
    total_orders = o_q.scalar() or 0
    total_products = p_q.scalar() or 0
    cancelled = c_q.scalar() or 0
    all_count = t_q.scalar() or 0

    cancel_rate = round(cancelled / all_count * 100, 1) if all_count > 0 else 0

    return jsonify({
        'total_revenue': round(total_revenue, 2),
        'total_orders': total_orders,
        'total_products': total_products,
        'cancel_rate': cancel_rate
    })