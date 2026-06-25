# MNQ2606 K线实时监控系统

基于 Flask + ECharts 的微纳指期货 K 线实时监控 Web 应用，支持多周期 K 线生成与实时更新。

## 项目结构

```
ruiying/
├── app.py           # Flask Web 后端（API + 静态页面 + 后台轮询）
├── kline.py         # K 线生成器（从 tick 构建多周期 K 线）
├── reader.py        # 数据读取器（从 SQLite 读取 tick 数据）
├── collector.py     # 数据采集器（从交易软件采集 tick 数据）
├── data.db          # SQLite 数据库（存储 tick 数据）
├── data/            # TXT 数据文件目录（按日期保存的原始行情数据）
├── templates/
│   └── index.html   # 前端页面（ECharts K 线图）
├── requirements.txt # Python 依赖
└── README.md        # 项目说明
```

## 功能特性

### 后端
- **多周期支持**：5秒、1分钟、5分钟、15分钟、30分钟、1小时
- **实时更新**：后台线程每秒轮询数据库，自动检测新 tick 并更新所有周期 K 线
- **REST API**：
  - `GET /` — K 线监控页面
  - `GET /api/klines?period=1m&count=500` — 获取指定周期 K 线数据
  - `GET /api/info` — 获取数据库和 K 线概览信息
  - `GET /api/periods` — 获取支持的周期列表

### 前端
- **ECharts 专业 K 线图**：蜡烛图 + 成交量柱状图
- **MA 均线**：MA5、MA10、MA20
- **周期切换**：一键切换 5秒 / 1分 / 5分 / 15分 / 30分 / 1时
- **实时刷新**：每 2 秒自动拉取最新 K 线数据
- **交互功能**：支持缩放、拖拽、十字光标
- **深色主题**：A 股风格，红涨绿跌

## 快速开始

### 环境要求
- Python 3.8+
- Flask >= 3.0

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
python app.py
```

启动后访问：**http://localhost:5000**

## 数据说明

- **数据源**：`data.db` SQLite 数据库
- **表结构**：`tick_data(id, timestamp, buy1)`
- **tick 数据**：从行情交易系统实时采集的买一价数据
- **K 线生成**：基于 tick 数据按时间周期聚合生成 OHLC K 线

## 架构说明

```
data.db (tick 数据)
     │
     ▼
reader.py ──读取 tick──▶ kline.py (多周期 K 线)
     │                        │
     ▼                        ▼
  app.py ◀──── API 请求 ──── 前端 (ECharts)
     │
     ▼
后台轮询线程 (每秒检测新 tick → 更新 K 线)
```
