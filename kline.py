"""
KLineGenerator - K线生成器
从 tick 数据生成K线，支持多种时间周期，新 tick 到来时自动更新最新K线
"""

from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class KLineBar:
    """单根K线"""
    timestamp: str       # K线所属时间 (周期开始时间)
    open: float          # 开盘价
    high: float          # 最高价
    low: float           # 最低价
    close: float         # 收盘价
    volume: int = 0      # 成交量(tick数量)

    def to_list(self) -> list:
        """转为前端需要的格式 [timestamp, open, close, low, high]"""
        return [self.timestamp, self.open, self.close, self.low, self.high]

    def update(self, price: float):
        """用新价格更新当前K线"""
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        self.volume += 1


class KLineGenerator:
    """
    K线生成器
    - 存储全量K线数据
    - 支持多种时间周期 (1m, 5m, 15m, 30m, 1h, 4h, 1d)
    - 新 tick 到来时自动更新最新时间周期的那根K线
    """

    # 周期映射 (秒)
    PERIOD_MAP = {
        '5s': 5,
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400,
    }

    def __init__(self, period: str = '1m'):
        if period not in self.PERIOD_MAP:
            raise ValueError(f"不支持的周期: {period}, 可选: {list(self.PERIOD_MAP.keys())}")
        self.period = period
        self.period_seconds = self.PERIOD_MAP[period]
        # 全量K线数据，按时间排序
        self.bars: List[KLineBar] = []
        # 快速查找: timestamp -> index
        self._bar_index: Dict[str, int] = {}
        # 最后处理的 tick id
        self.last_tick_id: int = 0

    def _get_bar_timestamp(self, tick_time: datetime) -> str:
        """将 tick 时间对齐到K线周期的开始时间"""
        ts = tick_time.timestamp()
        aligned = int(ts // self.period_seconds) * self.period_seconds
        return datetime.fromtimestamp(aligned).strftime('%Y-%m-%d %H:%M:%S')

    def _parse_tick_time(self, timestamp_str: str) -> datetime:
        """解析 tick 时间戳字符串"""
        # 格式: '2026-06-23 20:50:49.370'
        try:
            return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

    def build_from_ticks(self, ticks: list):
        """
        从 tick 数据构建全量K线
        ticks: [(timestamp, price), ...] 或 [(id, timestamp, price), ...]
        """
        self.bars.clear()
        self._bar_index.clear()

        has_id = len(ticks[0]) == 3 if ticks else False

        for tick in ticks:
            if has_id:
                tick_id, ts_str, price = tick
                self.last_tick_id = tick_id
            else:
                ts_str, price = tick

            self._add_tick(ts_str, price)

    def add_tick(self, tick_id: int, timestamp: str, price: float):
        """
        添加单个新 tick，自动更新或创建K线
        tick_id: tick 的数据库 id
        timestamp: 时间戳字符串
        price: 价格
        """
        if tick_id <= self.last_tick_id:
            return  # 跳过已处理的 tick
        self.last_tick_id = tick_id
        self._add_tick(timestamp, price)

    def add_ticks_batch(self, ticks: list):
        """
        批量添加新 tick
        ticks: [(id, timestamp, price), ...]
        """
        for tick_id, ts_str, price in ticks:
            self.add_tick(tick_id, ts_str, price)

    def _add_tick(self, timestamp_str: str, price: float):
        """内部方法：添加一个 tick 到K线"""
        tick_time = self._parse_tick_time(timestamp_str)
        bar_ts = self._get_bar_timestamp(tick_time)

        if bar_ts in self._bar_index:
            # 更新已存在的K线
            idx = self._bar_index[bar_ts]
            self.bars[idx].update(price)
        else:
            # 创建新K线
            bar = KLineBar(
                timestamp=bar_ts,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=1
            )
            idx = len(self.bars)
            self._bar_index[bar_ts] = idx
            self.bars.append(bar)

    def get_klines(self, count: int = 0) -> List[Dict]:
        """
        获取K线数据
        count: 返回最后 N 根K线，0 表示全部
        """
        bars = self.bars[-count:] if count > 0 else self.bars
        return [
            {
                'timestamp': b.timestamp,
                'open': b.open,
                'high': b.high,
                'low': b.low,
                'close': b.close,
                'volume': b.volume,
            }
            for b in bars
        ]

    def get_klines_echarts(self, count: int = 0) -> dict:
        """
        获取 ECharts 需要的格式
        返回: {
            'timestamps': [...],
            'ohlc': [[open, close, low, high], ...],
            'volumes': [...]
        }
        """
        bars = self.bars[-count:] if count > 0 else self.bars
        timestamps = [b.timestamp for b in bars]
        ohlc = [[b.open, b.close, b.low, b.high] for b in bars]
        volumes = [b.volume for b in bars]
        return {
            'timestamps': timestamps,
            'ohlc': ohlc,
            'volumes': volumes,
        }

    @property
    def total_bars(self) -> int:
        return len(self.bars)

    @property
    def latest_bar(self) -> Optional[KLineBar]:
        return self.bars[-1] if self.bars else None


if __name__ == '__main__':
    from reader import MarketDataReader

    reader = MarketDataReader()
    print(f"数据库记录数: {reader.get_count()}")
    print(f"时间范围: {reader.get_time_range()}")

    # 测试不同周期
    for period in ['1m', '5m', '15m', '1h']:
        gen = KLineGenerator(period=period)
        ticks = reader.get_all_ticks()
        gen.build_from_ticks(ticks)
        latest = gen.latest_bar
        print(f"\n{period} K线: {gen.total_bars} 根")
        if latest:
            print(f"  最新: {latest.timestamp} O={latest.open} H={latest.high} L={latest.low} C={latest.close} V={latest.volume}")
