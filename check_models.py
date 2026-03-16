import inspect
from app.models import Order

# 打印 models.py 的实际文件路径
import app.models as m
print(f"models.py 路径：{inspect.getfile(m)}")

# 打印 Order 模型的所有字段
print("\nOrder 模型定义的字段：")
for col in Order.__table__.columns:
    print(f"  {col.name} - {col.type}")