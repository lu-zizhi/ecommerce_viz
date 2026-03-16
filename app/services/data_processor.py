import pandas as pd
from app import db
from app.models import Product, Order, DailyMetrics
from datetime import datetime


def import_products(filepath):
    """
    从 Sale Report.csv 导入商品数据
    清洗逻辑：去重、填充空值、格式统一
    """
    try:
        # 读取CSV，自动处理编码
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='gbk')

        # 去掉完全重复的行
        df = df.drop_duplicates()

        # 填充空值
        df['Stock'] = df['Stock'].fillna(0)
        df['Color'] = df['Color'].fillna('未知')
        df['Size'] = df['Size'].fillna('未知')

        success_count = 0
        skip_count = 0

        for _, row in df.iterrows():
            # 跳过SKU为空的行
            if pd.isna(row.get('SKU Code')):
                skip_count += 1
                continue

            # 如果SKU已存在则跳过（避免重复导入）
            existing = Product.query.filter_by(sku=str(row['SKU Code'])).first()
            if existing:
                skip_count += 1
                continue

            product = Product(
                sku=str(row['SKU Code']),
                design_no=str(row.get('Design No.', '')),
                category=str(row.get('Category', '')),
                size=str(row.get('Size', '')),
                color=str(row.get('Color', '')),
                stock=int(row.get('Stock', 0))
            )
            db.session.add(product)
            success_count += 1

        db.session.commit()
        return {'success': True, 'imported': success_count, 'skipped': skip_count}

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def import_orders(filepath):
    """
    从 Amazon Sale Report.csv 导入订单数据
    清洗逻辑：日期格式统一、金额空值处理、状态标准化
    """
    try:
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='gbk')

        # 去掉完全重复的行
        df = df.drop_duplicates()

        # 去掉没有订单ID的行
        df = df.dropna(subset=['Order ID'])

        # 填充空值
        df['Amount'] = df['Amount'].fillna(0)
        df['Qty'] = df['Qty'].fillna(0)
        df['ship-city'] = df['ship-city'].fillna('未知')
        df['ship-state'] = df['ship-state'].fillna('未知')
        df['ship-country'] = df['ship-country'].fillna('IN')

        success_count = 0
        skip_count = 0

        for _, row in df.iterrows():
            # 如果订单已存在则跳过
            existing = Order.query.filter_by(order_id=str(row['Order ID'])).first()
            if existing:
                skip_count += 1
                continue

            # 日期格式处理：原始格式 04-30-22 → 转成 datetime
            try:
                order_date = datetime.strptime(str(row['Date']), '%m-%d-%y').date()
            except:
                order_date = None

            order = Order(
                order_id=str(row['Order ID']),
                date=order_date,
                status=str(row.get('Status', '')),
                fulfilment=str(row.get('Fulfilment', '')),
                sales_channel=str(row.get('Sales Channel ', '')).strip(),
                category=str(row.get('Category', '')),
                sku=str(row.get('SKU', '')),
                size=str(row.get('Size', '')),
                quantity=int(row.get('Qty', 0)),
                amount=float(row.get('Amount', 0)),
                currency=str(row.get('currency', 'INR')),
                ship_city=str(row.get('ship-city', '')),
                ship_state=str(row.get('ship-state', '')),
                ship_country=str(row.get('ship-country', '')),
                b2b=bool(row.get('B2B', False))
            )
            db.session.add(order)
            success_count += 1

            # 每1000条提交一次，避免内存占用过大
            if success_count % 1000 == 0:
                db.session.commit()

        db.session.commit()
        return {'success': True, 'imported': success_count, 'skipped': skip_count}

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}


def compute_daily_metrics():
    """
    从订单表汇总每日指标，写入 daily_metrics 表
    用于图表快速查询
    """
    try:
        # 用 SQLAlchemy 查出所有有效订单
        orders = Order.query.filter(Order.date.isnot(None)).all()

        if not orders:
            return {'success': False, 'error': '订单表为空，请先导入订单数据'}

        # 转成 DataFrame 方便用 Pandas 汇总
        data = [{
            'date': o.date,
            'amount': o.amount or 0,
            'status': o.status
        } for o in orders]

        df = pd.DataFrame(data)

        # 按日期分组汇总
        daily = df.groupby('date').agg(
            total_orders=('amount', 'count'),
            total_revenue=('amount', 'sum'),
            cancelled_orders=('status', lambda x: (x.str.contains('Cancel', na=False)).sum())
        ).reset_index()

        # 计算平均客单价
        daily['avg_order_value'] = daily.apply(
            lambda r: r['total_revenue'] / r['total_orders'] if r['total_orders'] > 0 else 0,
            axis=1
        )

        # 清空旧数据，重新写入
        DailyMetrics.query.delete()

        for _, row in daily.iterrows():
            metric = DailyMetrics(
                date=row['date'],
                total_orders=int(row['total_orders']),
                total_revenue=round(float(row['total_revenue']), 2),
                avg_order_value=round(float(row['avg_order_value']), 2),
                cancelled_orders=int(row['cancelled_orders'])
            )
            db.session.add(metric)

        db.session.commit()
        return {'success': True, 'days': len(daily)}

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}