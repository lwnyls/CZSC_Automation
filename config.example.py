"""
配置文件模板
复制本文件为 config.py 并填入你自己的飞书凭证
"""

# ── 飞书机器人 Webhook 地址 ──
# 创建方式：飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-id"

# ── 飞书企业自建应用凭证（用于上传图片） ──
# 创建方式：https://open.feishu.cn/app → 创建企业自建应用
# 需要开通权限：im:resource（上传图片）并启用机器人能力
FEISHU_APP_ID = "your-app-id"
FEISHU_APP_SECRET = "your-app-secret"

# ── 监控配置 ──
MONITOR_PERIODS = ['1m', '5m', '15m']         # 监控的周期
CHECK_INTERVAL = 5                             # 检查间隔（秒）

# ── 截图配置 ──
SCREENSHOT_MAX_KLINES = 300                    # 截图最多显示的K线数量
