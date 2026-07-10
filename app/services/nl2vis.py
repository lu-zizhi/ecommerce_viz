from app.services.deepseek import chat
from app import db
from app.models import ChatMessage  # 新增导入
import json
import re
import time
import traceback

SCHEMA_ORDERS = """1. orders（订单表，共约12万条）
   - order_id: 订单ID
   - date: 下单日期 (DATE格式。注意：本数据集所有数据均发生在2022年3月至2022年6月之间！请直接查询，严禁使用 CURDATE()、NOW() 等当前时间函数！)
   - status: 订单状态 (Shipped/Cancelled/Pending等)
   - category: 商品类目 (Set/Kurta/Western Dress/Top/Ethnic Dress/Blouse/Bottom/Saree)
   - sku: 商品SKU编码
   - size: 尺码 (XS/S/M/L/XL/XXL等)
   - quantity: 购买数量
   - amount: 销售额 (INR印度卢比)
   - currency: 货币 (INR)
   - ship_city: 收货城市
   - ship_state: 收货省份
   - ship_country: 收货国家(注意：印度的值为 'IN'，不要用中文'印度'去查)
   - fulfilment: 履约方式 (Amazon/Merchant)
   - sales_channel: 销售渠道
   - b2b: 是否B2B订单 (0或1)"""

SCHEMA_PRODUCTS = """2. products（商品表，共约9千条）
   - sku: SKU编码
   - design_no: 款式编号
   - category: 商品类目
   - size: 尺码
   - color: 颜色
   - stock: 库存数量"""

SCHEMA_METRICS = """3. daily_metrics（每日指标表，共91天）
   - date: 日期
   - total_orders: 当日总订单数
   - total_revenue: 当日总销售额
   - avg_order_value: 当日平均客单价
   - cancelled_orders: 当日取消订单数"""

CHART_TYPES = """可用的图表类型：
- line: 折线图，适合展示趋势变化（时间序列）
- bar: 柱状图，适合对比不同类别的数量或金额
- pie: 饼图，适合展示占比分布
- scatter: 散点图，适合展示两个变量的相关性"""


def get_dynamic_schema(user_query):
    """基于关键词的轻量级路由，只拼装需要的表结构"""
    schemas = [SCHEMA_ORDERS]
    if any(kw in user_query for kw in ['每天', '每日', '趋势', '大盘', '客单价']):
        schemas.append(SCHEMA_METRICS)
    if any(kw in user_query for kw in ['库存', '商品', '颜色', '款式']):
        schemas.append(SCHEMA_PRODUCTS)
    return "\n".join(schemas)


def nl2vis(user_query, user_id):
    """🌟 升级版：支持多轮会话记忆的 NL2VIS 核心 Agent"""
    start_time = time.time()
    total_tokens = 0

    db_schema = get_dynamic_schema(user_query)

    # 1. 🌟 从数据库读取该用户最近 6 条（3轮）历史对话作为上下文记忆
    history_messages = ChatMessage.query.filter_by(user_id=user_id)\
        .order_by(ChatMessage.created_at.desc()).limit(6).all()
    history_messages.reverse()  # 恢复正向时间轴顺序

    # 2. 构造 Step 1 专家 System Prompt
    step1_messages = [
        {
            'role': 'system',
            'content': f"""你是一个跨境电商数据分析专家。用户会用自然语言描述他想看的数据，你需要生成对应的SQL并推荐图表。
【重要】用户可能正在与你进行多轮连续追问。请结合上下文历史对话理解用户的真实意图。如果用户提出修改上一步图表的要求（例如“把刚才的图表换成折线图”或“只要看其中B2B的部分”），请基于历史中已生成的SQL和图表配置进行微调升级。

数据库包含以下表：
{db_schema}

{CHART_TYPES}

请严格按照以下JSON格式返回，不要有任何其他文字：
{{
    "sql": "SELECT语句",
    "chart_type": "line或bar或pie或scatter",
    "x_field": "x轴字段名",
    "y_field": "y轴字段名",
    "title": "图表标题"
}}
注意：
- SQL只能是SELECT语句，结果行数限制在50行以内。
- 日期字段使用DATE_FORMAT格式化，金额保留2位小数。"""
        }
    ]

    # 3. 🌟 把历史记忆无缝注入给大模型
    for msg in history_messages:
        # 如果是 assistant 角色，为了防止大模型复读之前的完整图表配置，我们只把关键的 SQL 规划喂回去
        if msg.role == 'assistant' and msg.content.startswith('{'):
            try:
                vis_json = json.loads(msg.content)
                clean_content = f"我已经为您生成了图表。执行的SQL是: {vis_json.get('sql')}，推荐图表类型是: {vis_json.get('chart_type')}。"
                step1_messages.append({'role': 'assistant', 'content': clean_content})
            except:
                step1_messages.append({'role': msg.role, 'content': msg.content})
        else:
            step1_messages.append({'role': msg.role, 'content': msg.content})

    # 4. 放入本次用户的新问题
    step1_messages.append({'role': 'user', 'content': user_query})

    # 调用大模型生成 SQL 规划
    step1_result = chat(step1_messages, temperature=0.1)
    total_tokens += step1_result.get('tokens', 0)

    if not step1_result['success']:
        return {'success': False, 'error': step1_result['error']}

    try:
        content = step1_result['content'].strip()
        content = re.sub(r'```json\n?', '', content)
        content = re.sub(r'```\n?', '', content)
        plan = json.loads(content)
    except json.JSONDecodeError:
        return {'success': False, 'error': f"AI返回格式错误：{step1_result['content']}"}

    sql = plan.get('sql', '')
    if not sql.strip().upper().startswith('SELECT'):
        return {'success': False, 'error': '只允许SELECT查询'}

    # 执行数据库查询（包含 Self-Correction 自愈代码）
    try:
        result = db.session.execute(db.text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        data = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        error_msg = str(e)
        print(f"[Agent 自愈触发] 原始SQL报错: {error_msg}")
        retry_messages = [
            {'role': 'system', 'content': f"你是一个高级数据库诊断专家。之前的SQL执行失败了，请仔细阅读错误信息，修复SQL语句。\n{db_schema}\n请严格输出和之前一样的JSON格式。"},
            {'role': 'user', 'content': f"用户的原始问题是：{user_query}\n你生成的错SQL是：{sql}\n报错信息：{error_msg}\n请分析原因并修复，仅返回完整的JSON结果。"}
        ]
        retry_result = chat(retry_messages, temperature=0.1)
        total_tokens += retry_result.get('tokens', 0)

        if retry_result['success']:
            try:
                retry_content = retry_result['content'].strip()
                retry_content = re.sub(r'```json\n?', '', retry_content)
                retry_content = re.sub(r'```\n?', '', retry_content)
                retry_plan = json.loads(retry_content)
                sql = retry_plan.get('sql', sql)

                result = db.session.execute(db.text(sql))
                rows = result.fetchall()
                columns = list(result.keys())
                data = [dict(zip(columns, row)) for row in rows]
            except Exception as retry_e:
                return {'success': False, 'error': f"SQL执行错误：{str(retry_e)}", 'sql': sql}
        else:
            return {'success': False, 'error': f"SQL执行错误：{error_msg}", 'sql': sql}

    if not data:
        return {'success': False, 'error': '查询结果为空，请换个问题试试', 'sql': sql}

    # Step 3: 生成 ECharts 配置与深度业务洞察
    step3_messages = [
        {
            'role': 'system',
            'content': """你是资深跨境电商数据分析专家。根据查询结果生成ECharts图表配置和深度业务洞察。
            请严格按以下JSON格式返回，不要有任何其他文字：
            {
                "echarts_option": { ECharts的option配置对象 },
                "insight": {
                    "what": "数据表现：用1句话概括数据反映的核心客观事实（列出关键指标数字）。",
                    "why": "归因推测": "结合跨境电商业务逻辑，深度推测产生该现象的1-2个深层原因。",
                    "how": "落地建议": "给出具有极强可执行性的运营、营销或库存优化策略。"
                }
            }
ECharts配置要求：必须包含 tooltip、legend、xAxis、yAxis、series，饼图不需要双轴，严禁使用任何JS匿名函数。"""
        },
        {
            'role': 'user',
            'content': f"用户问题：{user_query}\n图表类型：{plan.get('chart_type')}\n图表标题：{plan.get('title')}\n查询数据（前20条）：{json.dumps(data[:20], ensure_ascii=False, default=str)}"
        }
    ]

    step3_result = chat(step3_messages, temperature=0.3)
    total_tokens += step3_result.get('tokens', 0)

    if not step3_result['success']:
        return {'success': False, 'error': step3_result['error']}

    try:
        content = step3_result['content'].strip()
        content = re.sub(r'```json\n?', '', content)
        content = re.sub(r'```\n?', '', content)
        vis_result = json.loads(content)
    except json.JSONDecodeError:
        return {'success': False, 'error': f'图表配置解析失败：{step3_result["content"]}'}

    # 5. 🌟 核心组装：准备最终返回给前端的大包
    final_response = {
        'success': True,
        'title': plan.get('title', '数据分析结果'),
        'chart_type': plan.get('chart_type'),
        'echarts_option': vis_result.get('echarts_option'),
        'insight': vis_result.get('insight', {}),
        'sql': sql,
        'data': data,
        'latency': round(time.time() - start_time, 2),
        'total_tokens': total_tokens
    }

    # 6. 🌟 异步持久化记忆落库：保存当前这轮的用户问题和 AI 的结构化回复
    try:
        user_msg = ChatMessage(user_id=user_id, role='user', content=user_query)
        ai_msg = ChatMessage(user_id=user_id, role='assistant', content=json.dumps(final_response, ensure_ascii=False))
        db.session.add(user_msg)
        db.session.add(ai_msg)
        db.session.commit()
    except Exception as save_err:
        db.session.rollback()
        print(f"[Warning] 聊天记录落库失败: {save_err}")

    return final_response