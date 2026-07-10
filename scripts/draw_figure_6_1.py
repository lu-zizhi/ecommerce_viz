import matplotlib.pyplot as plt

# 设置中文字体（确保你的电脑支持，Windows通常为SimHei，Mac可改为Arial Unicode MS）
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 全链路耗时阶段数据
labels = ['动态 Schema 路由\n(2.15s, 4.5%)',
          '大模型代码生成\n(29.80s, 62.7%)',
          '数据库引擎执行\n(3.85s, 8.1%)',
          'Agent 闭环纠错\n(11.72s, 24.7%)']
times = [2.15, 29.80, 3.85, 11.72]

# 提取科技感配色
colors = ['#91cc75', '#5470c6', '#fac858', '#ee6666']
explode = (0.05, 0.05, 0.05, 0.05)  # 让各区块微微分离，增加质感

# 绘制环形图
fig, ax = plt.subplots(figsize=(8, 6))
wedges, texts, autotexts = ax.pie(times, explode=explode, labels=labels, colors=colors,
                                  autopct='%1.1f%%', startangle=140, pctdistance=0.85,
                                  textprops={'fontsize': 11})

# 绘制中心空白圆（形成环形图）
centre_circle = plt.Circle((0,0),0.70,fc='white')
fig.gca().add_artist(centre_circle)

# 在中心添加总耗时文字
plt.text(0, 0, '平均单次查询\n总耗时\n47.52 秒', ha='center', va='center', fontsize=14, fontweight='bold')

plt.tight_layout()

# 保存高质量图片用于论文
plt.savefig('figure_6_1_latency_distribution.png', dpi=300, bbox_inches='tight')
# plt.show()