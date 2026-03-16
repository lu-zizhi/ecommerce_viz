from app.services.deepseek import chat
from app import db
import json
import re

# 数据库结构描述，让DeepSeek了解我们的表结构
DB_SCHEMA = """
数据库包含以下表：

1. orders（订单表，共约12万条）
   - order_id: 订单ID
   - date: 下单日期 (DATE格式，如 2022-04-30)
   - status: 订单状态 (Shipped/Cancelled/Pending等)
   - category: 商品类目 (Set/Kurta/Western Dress/Top/Ethnic Dress/Blouse/Bottom/Saree)
   - sku: 商品SKU编码
   - size: 尺码 (XS/S/M/L/XL/XXL等)
   - quantity: 购买数量
   - amount: 销售额 (INR印度卢比)
   - currency: 货币 (INR)
   - ship_city: 收货城市
   - ship_state: 收货省份
   - ship_country: 收货国家
   - fulfilment: 履约方式 (Amazon/Merchant)
   - sales_channel: 销售渠道
   - b2b: 是否B2B订单 (0或1)

2. products（商品表，共约9千条）
   - sku: SKU编码
   - design_no: 款式编号
   - category: 商品类目
   - size: 尺码
   - color: 颜色
   - stock: 库存数量

3. daily_metrics（每日指标表，共91天）
   - date: 日期
   - total_orders: 当日总订单数
   - total_revenue: 当日总销售额
   - avg_order_value: 当日平均客单价
   - cancelled_orders: 当日取消订单数
"""

# 支持的图表类型说明
CHART_TYPES = """
可用的图表类型：
- line: 折线图，适合展示趋势变化（时间序列）
- bar: 柱状图，适合对比不同类别的数量或金额
- pie: 饼图，适合展示占比分布
- scatter: 散点图，适合展示两个变量的相关性
"""


def nl2vis(user_query):
    """
    NL2VIS 核心函数
    输入：用户的自然语言查询
    输出：{sql, chart_type, chart_config, insight, data}
    """

    # Step1: 让DeepSeek把自然语言转成SQL + 图表类型
    step1_messages = [
        {
            'role': 'system',
            'content': f"""你是一个跨境电商数据分析专家。
用户会用自然语言描述他想看的数据，你需要：
1. 生成对应的SQL查询语句
2. 推荐最合适的图表类型

{DB_SCHEMA}

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
- 金额保留2位小数用ROUND函数
"""
        },
        {
            'role': 'user',
            'content': user_query
        }
    ]

    step1_result = chat(step1_messages, temperature=0.1)
    if not step1_result['success']:
        return {'success': False, 'error': step1_result['error']}

    # 解析Step1返回的JSON
    try:
        # 清理可能的markdown代码块
        content = step1_result['content'].strip()
        content = re.sub(r'```json\n?', '', content)
        content = re.sub(r'```\n?', '', content)
        plan = json.loads(content)
    except json.JSONDecodeError:
        return {'success': False, 'error': f'AI返回格式错误：{step1_result["content"]}'}

    # Step2: 执行SQL查询
    sql = plan.get('sql', '')
    # 安全检查：只允许SELECT
    if not sql.strip().upper().startswith('SELECT'):
        return {'success': False, 'error': '只允许SELECT查询'}

    try:
        result = db.session.execute(db.text(sql))
        rows = result.fetchall()
        columns = list(result.keys())
        data = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return {'success': False, 'error': f'SQL执行错误：{str(e)}', 'sql': sql}

    if not data:
        return {'success': False, 'error': '查询结果为空，请换个问题试试', 'sql': sql}

    # Step3: 让DeepSeek根据数据生成ECharts配置 + 洞察文字
    step3_messages = [
        {
            'role': 'system',
            'content': """你是数据可视化专家。
根据查询结果生成ECharts图表配置和业务洞察。

请严格按以下JSON格式返回，不要有任何其他文字：
{
    "echarts_option": { ECharts的option配置对象 },
    "insight": "2-3句话的业务洞察分析"
}

ECharts配置要求：
- 必须包含 tooltip、legend（如果有多系列）、xAxis、yAxis、series
- 饼图不需要xAxis和yAxis
- 颜色使用ECharts默认配色即可
- title不需要设置（页面上已有标题）
- 严禁在JSON中使用任何JavaScript函数，formatter只能用字符串模板如"{b}: {c}"
- axisLabel中不能有function，只能用简单字符串
- 所有值必须是JSON合法类型：字符串、数字、布尔、数组、对象
"""
        },
        {
            'role': 'user',
            'content': f"""
用户问题：{user_query}
图表类型：{plan.get('chart_type')}
图表标题：{plan.get('title')}
查询数据（前20条）：{json.dumps(data[:20], ensure_ascii=False, default=str)}
字段说明：x轴={plan.get('x_field')}，y轴={plan.get('y_field')}
"""
        }
    ]

    step3_result = chat(step3_messages, temperature=0.3)
    if not step3_result['success']:
        return {'success': False, 'error': step3_result['error']}

    try:
        content = step3_result['content'].strip()
        content = re.sub(r'```json\n?', '', content)
        content = re.sub(r'```\n?', '', content)
        vis_result = json.loads(content)
    except json.JSONDecodeError:
        return {'success': False, 'error': f'图表配置解析失败：{step3_result["content"]}'}

    return {
        'success': True,
        'title': plan.get('title', '数据分析结果'),
        'chart_type': plan.get('chart_type'),
        'echarts_option': vis_result.get('echarts_option'),
        'insight': vis_result.get('insight'),
        'sql': sql,
        'data': data
    }