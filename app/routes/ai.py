from flask import Blueprint, render_template, request, jsonify
from app.services.nl2vis import nl2vis

# 定义蓝图
ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/')
def index():
    return render_template('ai_chat.html')


@ai_bp.route('/query', methods=['POST'])
def query():
    """
    接收自然语言查询，返回图表配置和洞察
    """
    data = request.json
    user_query = data.get('query', '').strip()

    if not user_query:
        return jsonify({'success': False, 'error': '请输入查询内容'})

    result = nl2vis(user_query)
    return jsonify(result)
