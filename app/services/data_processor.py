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


def import_external_generic_orders(filepath, mapping_dict):
    """
    🌟 终极强健版：通用异构数据映射与日期智能嗅探适配器（集成多重编码兼容 + 脏行自动跳过）
    """
    try:
        # 1. 智能编码盲盒级兼容
        encodings = ['utf-8', 'gbk', 'utf-8-sig', 'gb2312']
        df = None

        for enc in encodings:
            try:
                # 🌟 核心升级：加入 on_bad_lines='skip'，如果CSV里某一行格式坏了（如列数不对），自动跳过它而不是直接崩溃
                df = pd.read_csv(filepath, dtype=str, encoding=enc, on_bad_lines='skip')
                print(f"👉 [ETL 编码审计] 成功使用 {enc} 编码完成文件内容解析！")
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if df is None:
            return {'success': False, 'error': '文件编码格式过于特殊，系统无法解码，请务必保证CSV为常规UTF-8或GBK编码'}

        # 如果文件读出来是空的，直接熔断
        if df.empty:
            return {'success': False, 'error': '上传的CSV文件内容为空或行格式完全不匹配，请检查文件结构'}

        # 清理列名的前后隐藏空格
        df.columns = [col.strip() for col in df.columns]

        # 2. 动态逆向映射：把用户的自定义列名转换为系统标准字段名
        inverse_map = {v: k for k, v in mapping_dict.items() if v}
        df = df.rename(columns=inverse_map)

        # 3. 检查系统核心必填字段是否已成功捕获
        required_fields = ['order_id', 'date', 'sku', 'quantity', 'amount']
        missing = [f for f in required_fields if f not in df.columns]
        if missing:
            return {'success': False, 'error': f'映射失败！您的配置中缺失核心必填项: {missing}'}

        imported_count = 0
        skipped_count = 0

        # 4. 开启高性能的逐行清洗与数据类型硬核熔断转换
        for _, row in df.iterrows():
            if pd.isna(row['order_id']) or str(row['order_id']).strip() == '':
                continue

            # 规避重复订单入库
            existing = Order.query.filter_by(order_id=str(row['order_id'])).first()
            if existing:
                skipped_count += 1
                continue

            # 日期智能嗅探与自愈算法
            raw_date = str(row['date']).strip()
            parsed_date = None
            for fmt in ('%m-%d-%y', '%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%m/%d/%y', '%Y%m%d'):
                try:
                    parsed_date = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    continue

            if not parsed_date:
                parsed_date = datetime.utcnow().date()

            # 安全格式化数值类型
            try:
                qty_val = int(float(str(row['quantity']).replace(',', '')))
            except:
                qty_val = 1

            try:
                amount_val = float(str(row['amount']).replace(',', ''))
            except:
                amount_val = 0.0

            # 组装 ORM 实体
            new_order = Order(
                order_id=str(row['order_id']),
                date=parsed_date,
                status=str(row.get('status', 'Shipped')).strip(),
                category=str(row.get('category', 'Other')).strip(),
                sku=str(row['sku']).strip(),
                size=str(row.get('size', 'M')).strip(),
                quantity=qty_val,
                amount=amount_val,
                ship_state=str(row.get('ship_state', '未知')).strip(),
                b2b=int(float(row.get('b2b', 0))) if str(row.get('b2b')).isdigit() else 0
            )
            db.session.add(new_order)
            imported_count += 1

            if imported_count % 1000 == 0:
                db.session.commit()

        db.session.commit()
        return {'success': True, 'imported': imported_count, 'skipped': skipped_count}

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': f'ETL适配管道发生异常崩溃: {str(e)}'}