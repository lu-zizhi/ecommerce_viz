from app.services.deepseek import chat
from app import db
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

# 还原你原本的 CHART_TYPES
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


def nl2vis(user_query):
    start_time = time.time()  # 新增：记录开始时间
    total_tokens = 0  # 新增：初始化Token统计

    db_schema = get_dynamic_schema(user_query)

    # 还原你原本的 step1 提示词细节
    step1_messages = [
        {
            'role': 'system',
            'content': f"""你是一个跨境电商数据分析专家。用户会用自然语言描述他想看的数据，你需要：
1. 生成对应的SQL查询语句
2. 推荐最合适的图表类型

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
- SQL只能是SELECT语句，不能有UPDATE/DELETE/DROP等
- 结果行数限制在50行以内，使用LIMIT
- 日期字段使用DATE_FORMAT格式化
- 金额保留2位小数用ROUND函数"""
        },
        {
            'role': 'user',
            'content': user_query
        }
    ]

    step1_result = chat(step1_messages, temperature=0.1)
    total_tokens += step1_result.get('tokens', 0)  # 累加 Token

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

    # 还原错误捕获，在内部无损插入纠错逻辑
    try:
        result = db.session.execute(db.text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        data = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        error_traceback = traceback.format_exc()
        error_msg = str(e)
        print(f"[Self-Correction Triggered] 原始SQL报错: {error_msg}")

        # 专门为论文截图定制的终端打印格式
        print("\n" + "=" * 20 + " [Agent 触发反思与自愈机制] " + "=" * 20)
        print("❌ 数据库执行抛出异常，捕获到以下 Traceback 堆栈：")
        print(error_traceback)  # 这里会打印出长长的一大串红色报错
        print("正在挂起主线程，拦截异常传播...")
        print("正在将报错日志(Emsg)注入 Reflection Prompt，驱动大模型重写SQL...")
        print("=" * 68 + "\n")

        retry_messages = [
            {
                'role': 'system',
                'content': f"你是一个高级数据库诊断专家。之前的SQL执行失败了，请仔细阅读错误信息，修复SQL语句。\n数据库结构如下：\n{db_schema}\n请严格输出和之前一样的JSON格式，包含修改后的sql等字段。"
            },
            {
                'role': 'user',
                'content': f"用户的原始问题是：{user_query}\n你刚才生成的SQL是：{sql}\n在MySQL中执行时遇到了以下报错：\n{error_msg}\n\n请分析报错原因，修复SQL，并仅返回完整的JSON结果。"
            }
        ]
        retry_result = chat(retry_messages, temperature=0.1)
        total_tokens += retry_result.get('tokens', 0)  # 累加纠错 Token

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
                print(f"[Self-Correction Success] SQL已成功修复并执行！")
            except Exception as retry_e:
                return {'success': False, 'error': f"SQL执行错误：{str(retry_e)}", 'sql': sql}
        else:
            return {'success': False, 'error': f"SQL执行错误：{error_msg}", 'sql': sql}

    if not data:
        return {'success': False, 'error': '查询结果为空，请换个问题试试', 'sql': sql}

    # 还原你最原始的 step3 提示词！绝对不乱改 ECharts 规则
    step3_messages = [
        {
            'role': 'system',
            'content': """你是资深跨境电商数据分析专家。根据查询结果生成ECharts图表配置和深度业务洞察。
            请严格按以下JSON格式返回，不要有任何其他文字：
            {
                "echarts_option": { ECharts的option配置对象 },
                "insight": {
                    "what": "数据表现：用1句话概括数据反映的核心客观事实（列出关键指标数字）。",
                    "why": "归因推测：结合跨境电商业务逻辑（如选品、测款、季节性、供应链、尺码匹配等），深度推测产生该现象的1-2个深层原因。",
                    "how": "落地建议：给出具有极强可执行性的运营、营销或库存优化策略。"
                }
            }
ECharts配置要求：
- 必须包含 tooltip、legend（如果有多系列）、xAxis、yAxis、series
- 饼图不需要xAxis和yAxis
- 颜色使用ECharts默认配色即可
- title不需要设置（页面上已有标题）
- 严禁在JSON中使用任何JavaScript函数，formatter只能用字符串模板如"{b}: {c}"
- axisLabel中不能有function，只能用简单字符串
- 所有值必须是JSON合法类型：字符串、数字、布尔、数组、对象"""
        },
        {
            'role': 'user',
            'content': f"用户问题：{user_query}\n图表类型：{plan.get('chart_type')}\n图表标题：{plan.get('title')}\n查询数据（前20条）：{json.dumps(data[:20], ensure_ascii=False, default=str)}\n字段说明：x轴={plan.get('x_field')}，y轴={plan.get('y_field')}"
        }
    ]

    step3_result = chat(step3_messages, temperature=0.3)
    total_tokens += step3_result.get('tokens', 0)  # 累加 Token

    if not step3_result['success']:
        return {'success': False, 'error': step3_result['error']}

    try:
        content = step3_result['content'].strip()
        content = re.sub(r'```json\n?', '', content)
        content = re.sub(r'```\n?', '', content)
        vis_result = json.loads(content)
    except json.JSONDecodeError:
        return {'success': False, 'error': f'图表配置解析失败：{step3_result["content"]}'}

    insight_data = vis_result.get('insight', {})
    if isinstance(insight_data, str):
        # 兜底：万一大模型没有按对象格式返回，依然返回了字符串
        insight_data = {"what": insight_data, "why": "无", "how": "无"}

    return {
        'success': True,
        'title': plan.get('title', '数据分析结果'),
        'chart_type': plan.get('chart_type'),
        'echarts_option': vis_result.get('echarts_option'),
        'insight': insight_data,
        'sql': sql,
        'data': data,
        'latency': round(time.time() - start_time, 2),
        'total_tokens': total_tokens
    }