# MNQ K线实时监控系统

基于 Flask + ECharts 的微纳指期货 K 线实时监控 Web 应用，支持多周期 K 线生成、缠论分析（笔/中枢/买卖点）与飞书实时通知。

## 项目结构

```
ruiying/
├── app.py                  # Flask Web 后端（API + 后台轮询 + 监控启动）
├── kline.py                # K线生成器（多周期K线 + 包含处理 + 笔/中枢/买卖点）
├── zhongshu.py             # 缠论中枢生成器（3笔重叠 + 延伸 + 完成判定）
├── tradepoint.py           # 缠论买卖点判断（一/二/三类买卖点）
├── tradepoint_monitor.py   # 买卖点监控（自动检测 + 飞书通知 + 截图）
├── chart_screenshot.py     # K线截图生成（matplotlib，含笔/中枢/买卖点标记）
├── reader.py               # 数据读取器（从 SQLite 读取 tick 数据）
├── collector.py            # 数据采集器（从交易软件采集 tick 数据，不提交）
├── config.py               # 配置文件（飞书凭证等，不提交）
├── config.example.py       # 配置模板（复制为 config.py 后填写）
├── data.db                 # SQLite 数据库（存储 tick 数据）
├── data/                   # TXT 数据文件目录（按日期保存的原始行情数据）
├── templates/
│   └── index.html          # 前端页面（ECharts K线图）
├── requirements.txt        # Python 依赖
└── README.md               # 项目说明
```

## 功能特性

### 后端
- **多周期支持**：5秒、1分钟、5分钟、15分钟、30分钟、1小时
- **实时更新**：后台线程每秒轮询数据库，自动检测新 tick 并更新所有周期 K 线
- **缠论分析**：
  - K线包含处理（严格缠论规则递归合并）
  - 笔（Bi）自动识别（顶底分型 → 连接成笔）
  - 中枢（ZhongShu）识别（3笔重叠 + 延伸 + 完成判定）
  - 买卖点判断（一/二/三类买卖点）
- **买卖点监控**：自动检测新买卖点，发送飞书通知（含K线截图）
- **REST API**：
  - `GET /` — K线监控页面
  - `GET /api/klines?period=1m&count=500` — 获取K线数据（支持包含处理）
  - `GET /api/bi?period=1m&count=500` — 获取缠论笔/中枢/买卖点数据
  - `GET /api/info` — 获取数据库和K线概览信息
  - `GET /api/periods` — 获取支持的周期列表
  - `GET /api/monitor/status` — 获取买卖点监控状态

### 前端
- **ECharts 专业 K线图**：蜡烛图 + 成交量柱状图
- **MA 均线**：MA5、MA10、MA20
- **缠论标记**：
  - 笔（金色线段连接顶底分型）
  - 分型（顶分型红▼/底分型绿▲）
  - 中枢（紫色矩形，已完成实框/进行中虚框）
  - 买卖点（买点绿色↑/卖点红色↓，标注级别）
- **周期切换**：一键切换 5秒 / 1分 / 5分 / 15分 / 30分 / 1时
- **实时刷新**：每 2 秒自动拉取最新数据
- **悬停优化**：鼠标悬停时暂停刷新，tooltip 不消失
- **深色主题**：A股风格，红涨绿跌

### 飞书通知
- 买卖点出现时自动发送飞书卡片消息
- 消息包含：买卖点类型、周期、价格、时间、说明
- 附带K线截图（最近300根K线 + 笔 + 中枢 + 买卖点标记）
- 启动时预加载历史买卖点，只通知新出现的买卖点

## 缠论算法说明

### 中枢
| 概念 | 说明 |
|------|------|
| 中枢形成 | 连续3笔价格区间有重叠 |
| ZG | 中枢高点 = min(各笔最高价) |
| ZD | 中枢低点 = max(各笔最低价) |
| GG | 中枢最高点 = max(各笔最高价) |
| DD | 中枢最低点 = min(各笔最低价) |
| 中枢延伸 | 后续笔与 [ZD, ZG] 重叠则纳入 |
| 中枢结束 | 出现1笔不与中枢区间重叠 |

### 买卖点
| 类型 | 买点 | 卖点 |
|------|------|------|
| 一类 | 跌破中枢DD后，向下笔终点 | 突破中枢GG后，向上笔终点 |
| 二类 | 一类买点后回调不破前低 | 一类卖点后反弹不破前高 |
| 三类 | 中枢完成后回调不进ZD，随后突破ZG | 中枢完成后反弹不进ZG，随后跌破ZD |

## 快速开始

### 环境要求
- Python 3.8+
- Flask >= 3.0

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置飞书通知（可选）

1. 复制配置模板：
```bash
cp config.example.py config.py
```

2. 在 `config.py` 中填入你的飞书凭证：
   - **Webhook 地址**：飞书群 → 设置 → 群机器人 → 添加自定义机器人
   - **App ID / App Secret**：https://open.feishu.cn/app 创建企业自建应用
   - 需开通权限：`im:resource`（上传图片）并启用机器人能力

### 启动服务

```bash
python app.py
```

启动后访问：**http://localhost:5000**

## 数据说明

- **数据源**：`data.db` SQLite 数据库
- **表结构**：`tick_data(id, timestamp, buy1)`
- **tick 数据**：从行情交易系统实时采集的买一价数据
- **K线生成**：基于 tick 数据按时间周期聚合生成 OHLC K线

## 架构说明

```
data.db (tick 数据)
     │
     ▼
reader.py ──读取 tick──▶ kline.py (多周期K线 + 包含处理)
     │                        │
     │                        ├── zhongshu.py (中枢识别)
     │                        ├── tradepoint.py (买卖点判断)
     │                        ▼
     │                   tradepoint_monitor.py (监控 + 飞书通知)
     │                        │
     ▼                        ├── chart_screenshot.py (截图生成)
  app.py ◀──── API 请求 ──── 前端 (ECharts)
     │
     ▼
后台轮询线程 (每秒检测新 tick → 更新 K线)
后台监控线程 (每5秒检测新买卖点 → 发飞书通知)
```
