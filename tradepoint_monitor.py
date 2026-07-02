"""
买卖点监控模块
监控各周期买卖点，发现新买卖点时发送飞书通知（含K线截图）
"""
import time
import threading
import requests
from typing import Dict, Optional, Set

from config import (
    FEISHU_WEBHOOK, FEISHU_APP_ID, FEISHU_APP_SECRET,
    MONITOR_PERIODS, CHECK_INTERVAL,
)

# 买卖点类型与级别对应的 Emoji
EMOJI_MAP = {
    ('buy', 1): '🟢', ('buy', 2): '🔵', ('buy', 3): '🟣',
    ('sell', 1): '🔴', ('sell', 2): '🟠', ('sell', 3): '🟤',
}

# 买卖点中文描述
LABEL_MAP = {
    ('buy', 1): '一类买点', ('buy', 2): '二类买点', ('buy', 3): '三类买点',
    ('sell', 1): '一类卖点', ('sell', 2): '二类卖点', ('sell', 3): '三类卖点',
}


def _get_tenant_access_token() -> Optional[str]:
    """获取飞书 tenant_access_token"""
    try:
        resp = requests.post(
            'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
            json={'app_id': FEISHU_APP_ID, 'app_secret': FEISHU_APP_SECRET},
            timeout=10
        )
        data = resp.json()
        if data.get('code') == 0:
            return data.get('tenant_access_token')
        print(f"[飞书] 获取token失败: {data}")
    except Exception as e:
        print(f"[飞书] 获取token异常: {e}")
    return None


def _upload_image(image_bytes: bytes) -> Optional[str]:
    """上传图片到飞书，返回 image_key"""
    token = _get_tenant_access_token()
    if not token:
        return None

    try:
        resp = requests.post(
            'https://open.feishu.cn/open-apis/im/v1/images',
            headers={'Authorization': f'Bearer {token}'},
            data={'image_type': 'message'},
            files={'image': ('chart.png', image_bytes, 'image/png')},
            timeout=15
        )
        data = resp.json()
        if data.get('code') == 0:
            return data['data']['image_key']
        print(f"[飞书] 上传图片失败: {data}")
    except Exception as e:
        print(f"[飞书] 上传图片异常: {e}")
    return None


class TradePointMonitor:
    """
    买卖点监控器
    跟踪各周期最新买卖点，发现新买卖点时发送飞书通知
    """

    def __init__(self, generators_ref, lock_ref):
        """
        Args:
            generators_ref: 引用 app.py 中的 generators 字典
            lock_ref: 引用 app.py 中的 lock 对象
        """
        self.generators = generators_ref
        self.lock = lock_ref

        # 已通知的买卖点签名集合：period -> set of signatures
        # signature = f"{timestamp}_{level}_{type}"
        self.notified: Dict[str, Set[str]] = {}
        self.notified_lock = threading.Lock()

        self.running = False
        self.thread: Optional[threading.Thread] = None

    def _make_signature(self, tp: dict) -> str:
        """生成买卖点唯一签名，用于去重"""
        return f"{tp['timestamp']}_{tp['level']}_{tp['type']}"

    def _send_feishu(self, period: str, tp: dict, kline_data: dict, bi_data: dict, latest_price: Optional[float] = None):
        """发送飞书通知（交互式卡片消息，含K线截图）"""
        from chart_screenshot import generate_chart_image

        key = (tp['type'], tp['level'])
        emoji = EMOJI_MAP.get(key, '⚪')
        label = LABEL_MAP.get(key, f"L{tp['level']} {tp['type']}")

        # 生成截图（合并K线数据和缠论数据）
        try:
            merged = {**kline_data, **bi_data}
            image_bytes = generate_chart_image(merged, period, latest_price)
            image_key = _upload_image(image_bytes)
        except Exception as e:
            print(f"[截图] 生成/上传失败: {e}")
            image_key = None

        # 构建卡片元素
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"**周期:** {period}\n"
                        f"**价格:** {tp['price']:.2f}\n"
                        f"**时间:** {tp['timestamp']}\n"
                        f"**说明:** {tp.get('description', '')}"
                    )
                }
            }
        ]

        # 如果截图上传成功，添加图片元素
        if image_key:
            elements.append({
                "tag": "img",
                "img_key": image_key,
                "alt": {"tag": "plain_text", "content": "K线截图"}
            })

        # 使用飞书交互式卡片
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"{emoji} {label} 出现"
                    },
                    "template": "red" if tp['type'] == 'sell' else "green"
                },
                "elements": elements
            }
        }

        try:
            resp = requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
            result = resp.json()
            if result.get("code") == 0:
                print(f"[飞书通知] 发送成功: {period} {label} @ {tp['price']:.2f} 截图={'有' if image_key else '无'}")
            else:
                print(f"[飞书通知] 发送失败: {result}")
        except Exception as e:
            print(f"[飞书通知] 发送异常: {e}")

    def _initialize_notified(self):
        """启动时预加载当前已有买卖点作为基线，避免发送旧买卖点"""
        with self.lock:
            for period in MONITOR_PERIODS:
                gen = self.generators.get(period)
                if not gen:
                    continue
                bi_data = gen.get_bi_data(500)
                trade_points = bi_data.get('trade_points', [])
                if trade_points:
                    self.notified[period] = {
                        self._make_signature(tp) for tp in trade_points
                    }
                    print(f"[买卖点监控] {period}: 预加载 {len(trade_points)} 个历史买卖点（不发通知）")

    def _check_period(self, period: str):
        """检查单个周期的买卖点"""
        with self.lock:
            gen = self.generators.get(period)
            if not gen:
                return

            bi_data = gen.get_bi_data(500)
            trade_points = bi_data.get('trade_points', [])
            latest_bar = gen.latest_bar
            latest_price = latest_bar.close if latest_bar else None

        if not trade_points:
            return

        # 检查每个买卖点是否已通知过
        with self.notified_lock:
            if period not in self.notified:
                self.notified[period] = set()

            notified_set = self.notified[period]

            for tp in trade_points:
                sig = self._make_signature(tp)
                if sig in notified_set:
                    continue  # 已通知过，跳过

                # 新买卖点，获取K线数据并发送通知（含截图）
                with self.lock:
                    kline_data = gen.get_klines_echarts_with_include(500)
                self._send_feishu(period, tp, kline_data, bi_data, latest_price)
                notified_set.add(sig)

            # 限制每个周期保留的签名数量（最近200个）
            if len(notified_set) > 200:
                # set 无序，直接清空重建（保留最近从 trade_points 中提取的）
                recent_sigs = {self._make_signature(tp) for tp in trade_points}
                self.notified[period] = recent_sigs

    def _monitor_loop(self):
        """监控主循环"""
        print(f"[买卖点监控] 启动成功，监控周期: {MONITOR_PERIODS}")
        while self.running:
            try:
                for period in MONITOR_PERIODS:
                    self._check_period(period)
            except Exception as e:
                print(f"[买卖点监控] 检查异常: {e}")

            time.sleep(CHECK_INTERVAL)

    def start(self):
        """启动监控线程"""
        if self.running:
            print("[买卖点监控] 已在运行中")
            return

        # 先预加载当前已有买卖点，避免发送旧数据
        self._initialize_notified()

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """停止监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def get_status(self) -> dict:
        """获取监控状态"""
        with self.notified_lock:
            return {
                "running": self.running,
                "monitor_periods": MONITOR_PERIODS,
                "check_interval": CHECK_INTERVAL,
                "notified_count": sum(len(v) for v in self.notified.values()),
                "notified_by_period": {k: len(v) for k, v in self.notified.items()},
            }
