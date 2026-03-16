from flask import Blueprint, render_template, request, jsonify
from app.services.data_processor import import_products, import_orders, compute_daily_metrics
import os

data_bp = Blueprint('data', __name__)

@data_bp.route('/')
def index():
    """数据管理页"""
    return render_template('data.html')


@data_bp.route('/upload', methods=['POST'])
def upload():
    """
    接收上传的CSV文件
    前端传来 file 和 type（orders 或 products）
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有收到文件'})

    file = request.files['file']
    data_type = request.form.get('type', 'orders')  # 默认导入订单

    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'})

    if not file.filename.endswith('.csv'):
        return jsonify({'success': False, 'error': '只支持 CSV 文件'})

    # 保存文件到 data/ 目录
    save_path = os.path.join('data', file.filename)
    file.save(save_path)

    # 根据类型调用不同的导入函数
    if data_type == 'products':
        result = import_products(save_path)
    else:
        result = import_orders(save_path)

    return jsonify(result)


@data_bp.route('/import-local', methods=['POST'])
def import_local():
    """
    直接导入本地 data/ 目录下的文件
    方便开发阶段快速导入，不用每次上传
    """
    data_type = request.json.get('type')
    filename = request.json.get('filename')
    filepath = os.path.join('data', filename)

    if not os.path.exists(filepath):
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
def stats():
    """返回当前数据库中各表的数据量"""
    from app.models import Product, Order, DailyMetrics
    return jsonify({
        'products': Product.query.count(),
        'orders': Order.query.count(),
        'daily_metrics': DailyMetrics.query.count()
    })