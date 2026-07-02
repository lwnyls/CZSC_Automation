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

    # ───────────────── 缠论 K线包含处理 ─────────────────

    @staticmethod
    def _has_inclusion(bar1: KLineBar, bar2: KLineBar) -> bool:
        """判断两根K线是否存在包含关系（一根完全包裹另一根）"""
        return (bar1.high >= bar2.high and bar1.low <= bar2.low) or \
               (bar2.high >= bar1.high and bar2.low <= bar1.low)

    @staticmethod
    def _merge_two_bars(bar1: KLineBar, bar2: KLineBar, trend_up: bool) -> KLineBar:
        """
        严格缠论K线合并：按趋势方向处理高低点
        - 向上趋势：high 取两者最大值，low 取两者最大值
        - 向下趋势：high 取两者最小值，low 取两者最小值
        - open/close 取后一根（bar2）的值
        """
        if trend_up:
            new_high = max(bar1.high, bar2.high)
            new_low = max(bar1.low, bar2.low)
        else:
            new_high = min(bar1.high, bar2.high)
            new_low = min(bar1.low, bar2.low)

        # 约束 open/close 在 [low, high] 内，防止ECharts渲染异常
        new_open = max(new_low, min(new_high, bar2.open))
        new_close = max(new_low, min(new_high, bar2.close))

        return KLineBar(
            timestamp=bar1.timestamp,
            open=new_open,
            high=new_high,
            low=new_low,
            close=new_close,
            volume=bar1.volume + bar2.volume,
        )

    def _process_inclusion_strict(self, bars: List[KLineBar]) -> List[KLineBar]:
        """
        严格递归K线包含处理
        遍历每根K线，持续检查末尾两根是否包含，递归合并直到无包含
        返回处理后的新列表（不修改原数据）
        """
        if len(bars) < 2:
            return list(bars)

        result: List[KLineBar] = []

        for bar in bars:
            result.append(bar)
            # 递归合并：只要末尾两根存在包含关系，就继续合并
            while len(result) >= 2 and self._has_inclusion(result[-2], result[-1]):
                # 判断趋势方向：看合并K线对前面那根K线的收盘价方向
                if len(result) >= 3:
                    trend_up = result[-3].close <= result[-2].close
                else:
                    # 仅有两根K线且发生包含，默认向上趋势
                    trend_up = True

                merged = self._merge_two_bars(result[-2], result[-1], trend_up)
                result.pop()
                result.pop()
                result.append(merged)

        return result

    def get_klines_echarts_with_include(self, count: int = 0) -> dict:
        """获取经过包含处理的 ECharts 格式数据"""
        bars = self.bars[-count:] if count > 0 else self.bars
        processed = self._process_inclusion_strict(bars)
        timestamps = [b.timestamp for b in processed]
        ohlc = [[b.open, b.close, b.low, b.high] for b in processed]
        volumes = [b.volume for b in processed]
        return {
            'timestamps': timestamps,
            'ohlc': ohlc,
            'volumes': volumes,
        }

    def get_bi_data(self, count: int = 0) -> dict:
        """获取缠论分型和笔的渲染数据（内部自动进行包含处理）"""
        bars = self.bars[-count:] if count > 0 else self.bars
        processed = self._process_inclusion_strict(bars)
        return BiGenerator.from_klines(processed, raw_bars=bars)

    @property
    def total_bars(self) -> int:
        return len(self.bars)

    @property
    def latest_bar(self) -> Optional[KLineBar]:
        return self.bars[-1] if self.bars else None

    # ───────────────── 缠论 分型与笔 ─────────────────

@dataclass
class Fenxing:
    """缠论分型"""
    index: int          # 在包含处理后K线列表中的索引（中间K线位置）
    timestamp: str      # 时间
    price: float        # 顶分型取high，底分型取low
    type: str           # 'top' 或 'bottom'


class BiGenerator:
    """
    笔生成器
    对包含处理后的K线识别分型，按严格缠论规则连接相邻顶底分型生成笔
    """

    # 分型确认的前向检查根数，顶/底分型形成后，后续这么多根K线内必须有确认信号
    CONFIRM_LOOKAHEAD = 5

    @staticmethod
    def find_fenxing(bars: list) -> list:
        """
        找出所有已确认的顶分型和底分型（严格缠论定义）

        分型确认规则：
        - 顶分型：右K线收盘后，在 CONFIRM_LOOKAHEAD 根K线内，
                  至少有一根K线的最高价 < 顶分型中间K线的最高价
        - 底分型：右K线收盘后，在 CONFIRM_LOOKAHEAD 根K线内，
                  至少有一根K线的最低价 > 底分型中间K线的最低价

        未经确认的分型（形态上成立但价格未确认）会被过滤掉。
        数据末尾因后续K线不足而无法确认的分型也会被过滤。
        """
        if len(bars) < 3:
            return []

        fenxings = []
        for i in range(1, len(bars) - 1):
            prev_bar = bars[i - 1]
            curr_bar = bars[i]
            next_bar = bars[i + 1]

            is_top = curr_bar.high > prev_bar.high and curr_bar.high > next_bar.high
            is_bottom = curr_bar.low < prev_bar.low and curr_bar.low < next_bar.low

            if not (is_top or is_bottom):
                continue

            # ── 分型确认：检查后续 K 线 ──
            confirmed = False
            lookahead_end = min(i + 2 + BiGenerator.CONFIRM_LOOKAHEAD, len(bars))
            for j in range(i + 2, lookahead_end):
                if is_top and bars[j].high < curr_bar.high:
                    confirmed = True
                    break
                if is_bottom and bars[j].low > curr_bar.low:
                    confirmed = True
                    break

            if confirmed:
                fenxings.append(Fenxing(
                    index=i,
                    timestamp=curr_bar.timestamp,
                    price=curr_bar.high if is_top else curr_bar.low,
                    type='top' if is_top else 'bottom'
                ))

        return fenxings

    @staticmethod
    def _raw_spacing(f1, f2, raw_index_map: dict) -> int:
        """计算两个分型之间（不含两端）的原始K线数量"""
        idx1 = raw_index_map.get(f1.timestamp)
        idx2 = raw_index_map.get(f2.timestamp)
        if idx1 is None or idx2 is None:
            return 0
        return abs(idx2 - idx1) - 1

    @staticmethod
    def _is_extreme(top_fx, bottom_fx, processed_bars: list) -> bool:
        """
        验证：顶分型 price 是否区间最高，底分型 price 是否区间最低
        使用处理后K线价格做比较，保持与分型价格一致
        """
        lo = min(top_fx.index, bottom_fx.index)
        hi = max(top_fx.index, bottom_fx.index)
        for idx in range(lo, hi + 1):
            bar = processed_bars[idx]
            if bar.high > top_fx.price:
                return False  # 有更高的high，顶不是最高
            if bar.low < bottom_fx.price:
                return False  # 有更低的low，底不是最低
        return True

    @staticmethod
    def generate_bi(fenxings: list, raw_bars: list = None, processed_bars: list = None) -> list:
        """
        根据已确认的分型生成严格笔（新笔定义）

        步骤：
        1. 分型不允许共用K线，顶底极端K线间至少3根原始K线
        2. 同类型分型：仅比较直接相邻的（中间无其他分型），
           前低后高留后（顶），前高后低留后（底），其它保留
        3. 余下分型中顶底相邻即划为一笔，顶必须是笔中最高，底必须是最低
        """
        if len(fenxings) < 2:
            return []

        # 构建原始K线时间→索引映射（用于间距计算）
        raw_index_map = None
        if raw_bars:
            raw_index_map = {b.timestamp: i for i, b in enumerate(raw_bars)}

        # ── 步骤2：仅过滤「直接相邻」的同类型分型 ──
        filtered = [fenxings[0]]
        for f in fenxings[1:]:
            prev = filtered[-1]
            if f.type == prev.type:
                if (f.type == 'top' and prev.price < f.price) or \
                   (f.type == 'bottom' and prev.price > f.price):
                    filtered[-1] = f
                else:
                    filtered.append(f)
            else:
                filtered.append(f)

        # ── 步骤3：顶底交替成笔 ──
        bi_list = []
        current = filtered[0]

        for f in filtered[1:]:
            if f.type == current.type:
                # 同类型更极端 → 更新 current 并延伸最后一笔终点
                if (f.type == 'top' and f.price > current.price) or \
                   (f.type == 'bottom' and f.price < current.price):
                    old = current
                    current = f
                    if bi_list and bi_list[-1]['end_timestamp'] == old.timestamp:
                        bi_list[-1]['end_timestamp'] = f.timestamp
                        bi_list[-1]['end_price'] = f.price
                continue

            # ── 反向分型：两道间距 + 极值检查 → 成笔 ──
            # 第一关：处理后的K线间距（分型不共用K线）
            if abs(f.index - current.index) < 3:
                continue
            # 第二关：原始K线间距（极端K线之间至少3根）
            if raw_index_map:
                if BiGenerator._raw_spacing(current, f, raw_index_map) < 3:
                    continue

            if current.type == 'bottom' and f.type == 'top':
                if f.price <= current.price:
                    continue
                if processed_bars and not BiGenerator._is_extreme(f, current, processed_bars):
                    continue
                bi_list.append({
                    'start_timestamp': current.timestamp, 'start_price': current.price,
                    'end_timestamp': f.timestamp, 'end_price': f.price, 'direction': 'up',
                })
                current = f
            elif current.type == 'top' and f.type == 'bottom':
                if f.price >= current.price:
                    continue
                if processed_bars and not BiGenerator._is_extreme(current, f, processed_bars):
                    continue
                bi_list.append({
                    'start_timestamp': current.timestamp, 'start_price': current.price,
                    'end_timestamp': f.timestamp, 'end_price': f.price, 'direction': 'down',
                })
                current = f

        return bi_list

    @classmethod
    def from_klines(cls, bars: list, raw_bars: list = None) -> dict:
        """一站式：从包含处理后的K线生成分型和笔数据"""
        fenxings = cls.find_fenxing(bars)
        bi_list = cls.generate_bi(fenxings, raw_bars, bars)
        return {
            'fenxings': [
                {'timestamp': f.timestamp, 'price': f.price, 'type': f.type}
                for f in fenxings
            ],
            'bi_lines': bi_list,
        }



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
