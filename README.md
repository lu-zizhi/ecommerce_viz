# 基于大模型的跨境电商数据可视化系统

## 项目简介

本系统是一个基于大语言模型的跨境电商数据可视化平台，支持运营人员通过自然语言对话即可快速获得业务洞察和可视化结果。系统集成 DeepSeek 大模型，实现 NL2VIS（自然语言转可视化）核心功能，提升运营决策效率与敏捷性。

## 技术栈

| 层次     | 技术                   | 说明                  |
| -------- | ---------------------- | --------------------- |
| 后端框架 | Flask + Blueprint      | 模块化路由管理        |
| 前端渲染 | Jinja2 + ECharts 5.x   | 模板引擎 + 交互式图表 |
| 数据库   | MySQL + SQLAlchemy ORM | 关系型数据库          |
| AI 核心  | DeepSeek API           | NL2VIS 引擎           |
| 数据处理 | Pandas + openpyxl      | 数据清洗与分析        |
| 开发环境 | Python 3.10 + PyCharm  | Windows 11            |

## 系统功能

- **数据看板**：展示销售额趋势、品类占比、订单状态、省份分布等核心指标
- **数据管理**：支持 CSV/Excel 文件上传、清洗、导入数据库
- **智能分析**：基于 NL2VIS 方法，用户输入自然语言，AI 自动生成 SQL、推荐图表类型、渲染可视化结果并输出业务洞察

## 🏗️ 核心功能与设计思路

### 1. 智能分析 (NL2VIS Pipeline)

这是系统的“大脑”。为了解决 AI 幻觉并确保数据 100% 准确，系统采用了**三步走**闭环逻辑：

- **意图提取**：将 `DB_SCHEMA`（表结构描述）注入 Prompt，引导 AI 生成 SQL。
- **数据校验**：后端执行 SQL，确保查询结果来自真实的 12 万条订单数据，而非 AI 编造。
- **视觉渲染**：将真实查询结果反馈给 AI，生成 `ECharts Option` 和文字版的“业务洞察”。

### 2. 高性能数据清洗 (Pandas ETL)

针对跨境电商原始 CSV 数据存在的编码混乱、重复记录等问题，系统构建了自动化清洗流水线：

- **防御性读取**：自动尝试 `UTF-8` 与 `GBK` 编码，确保数据解析不乱码。
- **去重与补全**：利用 `drop_duplicates()` 剔除冗余，通过 `fillna(0)` 保证金额字段在数据库中的非空约束。
- **类型标准化**：利用 `datetime` 模块将非标准字符串统一为 DATE 格式，为后续时间轴分析打下基础。

### 3. 系统稳定性与安全性设计

- **事务回滚 (`rollback`)**：在 12 万条数据导入过程中，若遇异常（如断电、格式错误），系统自动执行 `db.session.rollback()`，确保数据库撤销当前未成功的操作，回到干净状态，维护数据的一致性。
- **分批提交**：采用每 1000 条数据提交一次 `commit` 的策略，平衡了内存占用与磁盘写入效率。
- **输入防御**：后端强制校验生成的 SQL 是否以 `SELECT` 开头，严禁执行破坏性指令。

## 项目结构

```
ecommerce_viz/
├── app/                        # 核心应用模块
│   ├── routes/                 # 路由层（Blueprint）
│   │   ├── __init__.py
│   │   ├── main.py             # 看板路由
│   │   ├── data.py             # 数据管理路由
│   │   └── ai.py               # NL2VIS 路由
│   ├── services/               # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── data_processor.py   # 数据清洗与导入
│   │   ├── deepseek.py         # DeepSeek API 封装
│   │   └── nl2vis.py           # NL2VIS 核心引擎
│   ├── static/                 # 静态资源
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   ├── templates/              # Jinja2 页面模板
│   │   ├── base.html           # 公共布局
│   │   ├── dashboard.html      # 数据看板页
│   │   ├── data.html           # 数据管理页
│   │   └── ai_chat.html        # 智能分析页
│   ├── __init__.py             # Flask 工厂函数
│   └── models.py               # SQLAlchemy 数据模型
├── data/                       # 原始数据集
│   ├── Amazon Sale Report.csv  # 订单数据（12万条）
│   ├── Sale Report.csv         # 商品数据（9千条）
│   └── International sale Report.csv
├── .gitignore
├── config.py                   # 配置管理
├── requirements.txt            # 依赖清单
└── run.py                      # 启动入口
```

## 数据集

本系统使用 Kaggle 公开跨境电商数据集：

| 表名          | 数据量     | 说明                           |
| ------------- | ---------- | ------------------------------ |
| orders        | 120,378 条 | Amazon 订单数据（2022年3-6月） |
| products      | 9,170 条   | 商品 SKU 数据                  |
| daily_metrics | 91 天      | 每日汇总指标                   |

## 快速启动

### 1. 安装依赖
```bash
python -m pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填写数据库密码和 DeepSeek API Key：
```
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ecommerce_viz
DB_USER=root
DB_PASSWORD=你的MySQL密码
DEEPSEEK_API_KEY=你的API Key
```

### 3. 初始化数据库
```bash
python run.py  # 启动时自动建表
```

### 4. 导入数据

访问 `http://127.0.0.1:5000/data`，依次点击：
1. 导入商品数据
2. 导入订单数据
3. 汇总每日指标

### 5. 启动系统
```bash
python run.py
```

访问 `http://127.0.0.1:5000`

## NL2VIS 核心流程

```
用户自然语言输入
        ↓
  Prompt 模板封装
        ↓
  DeepSeek API 调用
        ↓
  生成 SQL + 图表类型
        ↓
   SQL只读权限审查
   	    ↓
   执行 SQL 查询，返回格式化数据
        ↓
  生成 ECharts 配置
        ↓
  渲染图表 + 业务洞察
```

## 开发者

- 姓名：路昺豪
- 学号：E22214087
- 专业：软件工程
- 指导教师：颜老师