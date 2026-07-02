"""
缠论买卖点判断模块
基于笔和中枢数据，判断一、二、三类买卖点
"""


class TradePoint:
    """缠论买卖点"""

    # 买卖点类型
    TYPE_BUY = "buy"          # 买点
    TYPE_SELL = "sell"        # 卖点

    # 买卖点级别
    LEVEL_1 = 1   # 一类买卖点
    LEVEL_2 = 2   # 二类买卖点
    LEVEL_3 = 3   # 三类买卖点

    def __init__(self, point_type, level, timestamp, price, zhongshu=None, description=""):
        """
        Args:
            point_type: TYPE_BUY / TYPE_SELL
            level: 1/2/3
            timestamp: 买卖点对应的时间戳
            price: 买卖点对应的价格
            zhongshu: 相关的中枢对象
            description: 附加描述
        """
        self.point_type = point_type
        self.level = level
        self.timestamp = timestamp
        self.price = price
        self.zhongshu = zhongshu
        self.description = description

    @property
    def level_str(self):
        return f"一类{'买点' if self.point_type == self.TYPE_BUY else '卖点'}"

    @property
    def summary(self):
        type_str = "买点" if self.point_type == self.TYPE_BUY else "卖点"
        return f"L{self.level} {type_str} @ {self.price:.2f} ({self.timestamp})"

    def to_dict(self):
        return {
            'type': self.point_type,
            'level': self.level,
            'timestamp': self.timestamp,
            'price': self.price,
            'level_str': self.level_str,
            'summary': self.summary,
            'description': self.description,
        }


class TradePointGenerator:
    """
    买卖点生成器

    判断逻辑（以买点为例，卖点对称）：

    一类买点：
    - 下跌趋势中，最后一个中枢之后，出现新的底分型（价格创新低）
    - 即：中枢 DD 被跌破，随后形成底分型

    二类买点：
    - 一类买点之后，价格回调不破一类买点的最低点，形成更高的低点
    - 即：一类买点后，下一个底分型的最低点 > 一类买点价格

    三类买点：
    - 中枢完成后，价格回调不破 ZD（中枢低点），随后向上突破 ZG
    - 即：价格回到中枢区间上方，且不进入 ZD 以下

    注：以上为简化实现，严格缠论还需要考虑走势类型、背驰等
    """

    @classmethod
    def _bi_high(cls, bi):
        """笔的最高价"""
        return max(bi['start_price'], bi['end_price'])

    @classmethod
    def _bi_low(cls, bi):
        """笔的最低价"""
        return min(bi['start_price'], bi['end_price'])

    @classmethod
    def _bi_direction(cls, bi):
        """笔的方向：up/down"""
        return 'up' if bi['end_price'] > bi['start_price'] else 'down'

    @classmethod
    def find_trade_points(cls, bi_list, zhongshu_list):
        """
        从笔列表和中枢列表中识别买卖点

        Args:
            bi_list: BiGenerator.generate_bi() 返回的笔字典列表
            zhongshu_list: ZhongShuGenerator.from_bi_list() 返回的中枢列表

        Returns:
            list of TradePoint
        """
        if len(bi_list) < 3 or len(zhongshu_list) == 0:
            return []

        results = []

        # ── 对每个已完成的中枢，判断三类买卖点 ──
        for i, zs in enumerate(zhongshu_list):
            if not zs.is_complete:
                continue  # 只处理已完成的中枢

            # 找到中枢之后的笔（直接切片，避免 index() 查找错误）
            zs_end_idx = max(zs.bi_indices)
            subsequent_bis = bi_list[zs_end_idx + 1:]

            if len(subsequent_bis) < 2:
                continue

            # ── 三类买点：中枢完成后，价格回调不破 ZD，随后向上 ──
            cls._check_level3_buy(zs, subsequent_bis, bi_list, results)

            # ── 三类卖点：中枢完成后，价格反弹不破 ZG，随后向下 ──
            cls._check_level3_sell(zs, subsequent_bis, bi_list, results)

            # ── 一类买点：中枢 DD 被跌破，随后形成底分型（价格新低后回升）──
            cls._check_level1_buy(zs, subsequent_bis, bi_list, results)

            # ── 一类卖点：中枢 GG 被突破，随后形成顶分型（价格新高后回落）──
            cls._check_level1_sell(zs, subsequent_bis, bi_list, results)

        # ── 二类买点：一类买点之后，回调不破前低 ──
        cls._check_level2_buy(results, bi_list)

        # ── 二类卖点：一类卖点之后，反弹不破前高 ──
        cls._check_level2_sell(results, bi_list)

        return results

    @classmethod
    def _check_level1_buy(cls, zs, subsequent_bis, bi_list, results):
        """
        一类买点判断：
        中枢 DD 被跌破（创新低），该向下笔的终点即为底分型（一类买点）
        注：笔的定义保证了向下笔结束后必然反转为向上笔，无需额外检查
        """
        zs_dd = zs.dd  # 中枢最低点

        for bi in subsequent_bis:
            if cls._bi_direction(bi) != 'down':
                continue

            bi_low = cls._bi_low(bi)

            # 价格跌破中枢 DD（创新低），该笔终点即为一类买点
            if bi_low < zs_dd:
                results.append(TradePoint(
                    point_type=TradePoint.TYPE_BUY,
                    level=1,
                    timestamp=bi['end_timestamp'],
                    price=bi_low,
                    zhongshu=zs,
                    description=f"跌破中枢DD({zs_dd:.2f})，一类买点"
                ))
                return  # 每个中枢只取第一个一类买点

    @classmethod
    def _check_level1_sell(cls, zs, subsequent_bis, bi_list, results):
        """
        一类卖点判断：
        中枢 GG 被突破（创新高），该向上笔的终点即为顶分型（一类卖点）
        注：笔的定义保证了向上笔结束后必然反转为向下笔，无需额外检查
        """
        zs_gg = zs.gg  # 中枢最高点

        for bi in subsequent_bis:
            if cls._bi_direction(bi) != 'up':
                continue

            bi_high = cls._bi_high(bi)

            # 价格突破中枢 GG（创新高），该笔终点即为一类卖点
            if bi_high > zs_gg:
                results.append(TradePoint(
                    point_type=TradePoint.TYPE_SELL,
                    level=1,
                    timestamp=bi['end_timestamp'],
                    price=bi_high,
                    zhongshu=zs,
                    description=f"突破中枢GG({zs_gg:.2f})，一类卖点"
                ))
                return  # 每个中枢只取第一个一类卖点

    @classmethod
    def _find_bi_index_by_timestamp(cls, bi_list, timestamp, timestamp_key='end_timestamp'):
        """通过 timestamp 查找笔在列表中的位置"""
        for i, bi in enumerate(bi_list):
            if bi.get(timestamp_key) == timestamp:
                return i
        return -1

    @classmethod
    def _check_level2_buy(cls, results, bi_list):
        """
        二类买点判断：
        一类买点之后，价格回调形成更高的低点
        """
        # 找到所有一类买点
        level1_buys = [r for r in results if r.level == 1 and r.point_type == TradePoint.TYPE_BUY]
        if not level1_buys:
            return

        for l1 in level1_buys:
            l1_price = l1.price
            l1_time = l1.timestamp

            # 找到一类买点之后的笔
            l1_idx = cls._find_bi_index_by_timestamp(bi_list, l1_time)
            if l1_idx < 0 or l1_idx >= len(bi_list) - 2:
                continue

            subsequent = bi_list[l1_idx + 1:]

            # 找回调笔（向下笔），其最低点 > 一类买点价格
            for bi in subsequent:
                if cls._bi_direction(bi) == 'down':
                    bi_low = cls._bi_low(bi)
                    if bi_low > l1_price:
                        # 二类买点：回调不破前低
                        results.append(TradePoint(
                            point_type=TradePoint.TYPE_BUY,
                            level=2,
                            timestamp=bi['end_timestamp'],
                            price=bi_low,
                            description=f"一类买点后回调不破前低({l1_price:.2f})，二类买点"
                        ))
                        break  # 每个一类买点只取第一个二类买点

    @classmethod
    def _check_level2_sell(cls, results, bi_list):
        """
        二类卖点判断：
        一类卖点之后，价格反弹形成更低的高点
        """
        # 找到所有一类卖点
        level1_sells = [r for r in results if r.level == 1 and r.point_type == TradePoint.TYPE_SELL]
        if not level1_sells:
            return

        for l1 in level1_sells:
            l1_price = l1.price
            l1_time = l1.timestamp

            # 找到一类卖点之后的笔
            l1_idx = cls._find_bi_index_by_timestamp(bi_list, l1_time)
            if l1_idx < 0 or l1_idx >= len(bi_list) - 2:
                continue

            subsequent = bi_list[l1_idx + 1:]

            # 找反弹笔（向上笔），其最高点 < 一类卖点价格
            for bi in subsequent:
                if cls._bi_direction(bi) == 'up':
                    bi_high = cls._bi_high(bi)
                    if bi_high < l1_price:
                        # 二类卖点：反弹不破前高
                        results.append(TradePoint(
                            point_type=TradePoint.TYPE_SELL,
                            level=2,
                            timestamp=bi['end_timestamp'],
                            price=bi_high,
                            description=f"一类卖点后反弹不破前高({l1_price:.2f})，二类卖点"
                        ))
                        break

    @classmethod
    def _check_level3_buy(cls, zs, subsequent_bis, bi_list, results):
        """
        三类买点判断：
        中枢完成后，价格回调不进入中枢区间（不破 ZD），随后向上突破
        """
        zs_zd = zs.zd
        zs_zg = zs.zg

        # 找中枢完成后的回调笔（向下笔），其最低点 >= ZD（不进入中枢）
        for j, bi in enumerate(subsequent_bis):
            if cls._bi_direction(bi) != 'down':
                continue

            bi_low = cls._bi_low(bi)

            # 回调不进入中枢（低点 >= ZD）
            if bi_low >= zs_zd:
                # 检查后续是否有向上突破的笔
                if j + 1 < len(subsequent_bis):
                    next_bi = subsequent_bis[j + 1]
                    if cls._bi_direction(next_bi) == 'up' and cls._bi_high(next_bi) > zs_zg:
                        # 三类买点：回调不进中枢，随后向上突破 ZG
                        results.append(TradePoint(
                            point_type=TradePoint.TYPE_BUY,
                            level=3,
                            timestamp=bi['end_timestamp'],
                            price=bi_low,
                            zhongshu=zs,
                            description=f"中枢完成后回调不进区间[{zs_zd:.2f},{zs_zg:.2f}]，三类买点"
                        ))
                        return  # 每个中枢只取第一个三类买点

    @classmethod
    def _check_level3_sell(cls, zs, subsequent_bis, bi_list, results):
        """
        三类卖点判断：
        中枢完成后，价格反弹不进入中枢区间（不破 ZG），随后向下突破
        """
        zs_zd = zs.zd
        zs_zg = zs.zg

        # 找中枢完成后的反弹笔（向上笔），其最高点 <= ZG（不进入中枢）
        for j, bi in enumerate(subsequent_bis):
            if cls._bi_direction(bi) != 'up':
                continue

            bi_high = cls._bi_high(bi)

            # 反弹不进入中枢（高点 <= ZG）
            if bi_high <= zs_zg:
                # 检查后续是否有向下突破的笔
                if j + 1 < len(subsequent_bis):
                    next_bi = subsequent_bis[j + 1]
                    if cls._bi_direction(next_bi) == 'down' and cls._bi_low(next_bi) < zs_zd:
                        # 三类卖点：反弹不进中枢，随后向下突破 ZD
                        results.append(TradePoint(
                            point_type=TradePoint.TYPE_SELL,
                            level=3,
                            timestamp=bi['end_timestamp'],
                            price=bi_high,
                            zhongshu=zs,
                            description=f"中枢完成后反弹不进区间[{zs_zd:.2f},{zs_zg:.2f}]，三类卖点"
                        ))
                        return

    @classmethod
    def to_render_data(cls, trade_points):
        """
        将买卖点列表转为前端渲染数据

        Returns:
            {
                'trade_points': [
                    {
                        'type': 'buy'/'sell',
                        'level': 1/2/3,
                        'timestamp': ...,
                        'price': ...,
                        'level_str': ...,
                        'summary': ...,
                        'description': ...,
                    },
                    ...
                ]
            }
        """
        return {
            'trade_points': [tp.to_dict() for tp in trade_points]
        }
