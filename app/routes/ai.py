from flask import Blueprint, render_template, request, jsonify
from app.services.nl2vis import nl2vis
from flask_login import login_required, current_user  # 引入用户上下文
from app.models import ChatMessage
import json

ai_bp = Blueprint('ai', __name__)


@ai_bp.route('/')
@login_required
def index():
    return render_template('ai_chat.html')


@ai_bp.route('/query', methods=['POST'])
@login_required
def query():
    """接收自然语言查询，引入会话上下文"""
    data = request.json
    user_query = data.get('query', '').strip()

    if not user_query:
        return jsonify({'success': False, 'error': '请输入查询内容'})

    # 🌟 传入当前登录用户的 ID，驱动多轮对话
    result = nl2vis(user_query, current_user.id)
    return jsonify(result)


@ai_bp.route('/history', methods=['GET'])
@login_required
def get_history():
    """🌟 新增接口：获取该用户所有的历史聊天气泡记录，供前端页面初始化加载"""
    messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.created_at.asc()).all()

    formatted_history = []
    for m in messages:
        if m.role == 'user':
            formatted_history.append({
                'id': m.id,
                'role': 'user',
                'text': m.content
            })
        else:
            # 如果是 AI 回复，尝试解析内部的 JSON 数据包
            try:
                raw_data = json.loads(m.content)
                formatted_history.append({
                    'id': m.id,
                    'role': 'assistant',
                    'text': f"✅ 已生成「{raw_data.get('title', '数据分析结果')}」",
                    'raw_data': raw_data  # 把完整的图表配置带回前端缓存
                })
            except:
                formatted_history.append({
                    'id': m.id,
                    'role': 'assistant',
                    'text': m.content
                })

    return jsonify(formatted_history)