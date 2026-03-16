from app import create_app, db

app = create_app()

with app.app_context():
    # 强制删除所有表
    db.drop_all()
    print("所有表已删除")

    # 重新创建所有表
    db.create_all()
    print("所有表已重新创建")

    # 打印所有表名确认
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"当前数据库中的表：{tables}")

    # 打印 orders 表字段确认
    columns = inspector.get_columns('orders')
    print("\norders 表字段：")
    for col in columns:
        print(f"  {col['name']} - {col['type']}")