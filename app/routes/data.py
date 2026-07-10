from flask import Blueprint, render_template, request, jsonify
from app.services.data_processor import import_products, import_orders, compute_daily_metrics
from flask_login import login_required
from app.models import Order  # 引入订单模型
from app import db
import os
import json
from app.services.data_processor import import_external_generic_orders  # 引入新写的适配器

data_bp = Blueprint('data', __name__)


@data_bp.route('/')
@login_required
def index():
    """数据管理页"""
    return render_template('data.html')


@data_bp.route('/orders', methods=['GET'])
@login_required
def get_orders_list():
    """
    🌟 新增 API：支持高并发检索的服务器端异步分页及条件过滤接口
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all').strip()

    # 构建基础查询语句
    query = Order.query

    # 动态追加模糊检索（支持订单ID和SKU条码过滤）
    if search:
        query = query.filter((Order.order_id.like(f"%{search}%")) | (Order.sku.like(f"%{search}%")))

    # 动态追加状态过滤
    if status and status != 'all':
        query = query.filter(Order.status == status)

    # 执行高性能数据库底层分页切片
    pagination = query.order_by(Order.date.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'orders': [o.to_dict() for o in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })


@data_bp.route('/orders/update-status/<int:id>', methods=['POST'])
@login_required
def update_order_status(id):
    """
    🌟 新增 API：动态修改某条订单的状态
    """
    order = Order.query.get_or_404(id)
    new_status = request.json.get('status', '').strip()

    if not new_status:
        return jsonify({'success': False, 'error': '状态不能为空'})

    try:
        order.status = new_status
        db.session.commit()
        return jsonify({'success': True, 'message': '订单状态更新成功！'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


@data_bp.route('/orders/delete/<int:id>', methods=['POST'])
@login_required
def delete_order(id):
    """
    🌟 新增 API：物理删除单条脏数据
    """
    order = Order.query.get_or_404(id)
    try:
        db.session.delete(order)
        db.session.commit()
        return jsonify({'success': True, 'message': '该订单已成功从数据库抹除！'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


# =========================================================
# ... 保持你原本的 upload, import_local, stats 路由完全不动 ...
# =========================================================

@data_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files: return jsonify({'success': False, 'error': '没有收到文件'})
    file = request.files['file']
    data_type = request.form.get('type', 'orders')
    if file.filename == '': return jsonify({'success': False, 'error': '文件名为空'})
    if not file.filename.endswith('.csv'): return jsonify({'success': False, 'error': '只支持 CSV 文件'})
    save_path = os.path.join('data', file.filename)
    file.save(save_path)
    if data_type == 'products':
        result = import_products(save_path)
    else:
        result = import_orders(save_path)
    return jsonify(result)


@data_bp.route('/import-local', methods=['POST'])
@login_required
def import_local():
    data_type = request.json.get('type')
    filename = request.json.get('filename')
    filepath = os.path.join('data', filename)
    if not os.path.exists(filepath) and data_type != 'metrics':
        return jsonify({'success': False, 'error': f'文件不存在: {filepath}'})
    if data_type == 'products':
        result = import_products(filepath)
    elif data_type == 'orders':
        result = import_orders(filepath)
    elif data_type == 'metrics':
        result = compute_daily_metrics()
    else:
        return jsonify({'success': False, 'error': '未知的数据类型'})
    return jsonify(result)


@data_bp.route('/stats', methods=['GET'])
@login_required
def stats():
    from app.models import Product, Order, DailyMetrics
    return jsonify({
        'products': Product.query.count(),
        'orders': Order.query.count(),
        'daily_metrics': DailyMetrics.query.count()
    })


@data_bp.route('/upload-generic', methods=['POST'])
@login_required
def upload_generic_heterogeneous_data():
    """
    🌟 新增 API：接收任意表头的异构增量 CSV 并进行动态映射入库
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未收到文件'})

    file = request.files['file']
    # 从前端表单中读取用户动态勾选建立的映射字典 JSON 字符串
    mapping_json = request.form.get('mapping', '{}')

    try:
        mapping_dict = json.loads(mapping_json)
    except:
        return jsonify({'success': False, 'error': '映射配置解析失败'})

    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'})

    save_path = os.path.join('data', f"generic_{file.filename}")
    file.save(save_path)

    # 驱动通用映射清洗流水线
    result = import_external_generic_orders(save_path, mapping_dict)

    # 动态清理缓存残留文件
    if os.path.exists(save_path):
        os.remove(save_path)

    return jsonify(result)