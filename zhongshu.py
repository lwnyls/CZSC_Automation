"""
缠论中枢生成器
从笔序列中识别中枢（至少3笔重叠）
标准缠论逻辑：中枢延伸直至连续3笔不回中枢区间
"""


class ZhongShu:
    """缠论中枢"""

    def __init__(self, start_timestamp, end_timestamp, zg, zd, gg, dd, bi_count, bi_indices, is_complete=True):
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self.zg = zg
        self.zd = zd
        self.gg = gg
        self.dd = dd
        self.bi_count = bi_count
        self.bi_indices = bi_indices
        self.is_complete = is_complete  # 是否已完整结束（连续3笔不回中枢）

    @property
    def is_valid(self):
        """是否有有效重叠区间"""
        return self.zd < self.zg

    @property
    def range_str(self):
        """中枢区间字符串"""
        return f"[{self.zd:.2f}, {self.zg:.2f}]"

    def contains_price(self, price):
        """判断某价格是否在中枢区间内"""
        return self.zd <= price <= self.zg

    def overlaps_with_bi(self, bi_high, bi_low):
        """判断某笔的价格区间是否与中枢区间重叠"""
        return not (bi_high < self.zd or bi_low > self.zg)


class ZhongShuGenerator:
    """
    中枢生成器（标准缠论逻辑）

    中枢形成：连续3笔的价格区间有重叠 → ZG = min(highs), ZD = max(lows)
    中枢延伸：后续笔与中枢区间[ZD, ZG]重叠 → 纳入，更新ZG/ZD/GG/DD
    中枢结束：连续3笔不与中枢区间重叠 → 中枢完整结束
             若数据结束但仍未出现3笔不回 → 中枢为"进行中"状态
    """

    @staticmethod
    def _bi_high(bi):
        """笔的最高价"""
        return max(bi['start_price'], bi['end_price'])

    @staticmethod
    def _bi_low(bi):
        """笔的最低价"""
        return min(bi['start_price'], bi['end_price'])

    @staticmethod
    def _try_form_zhongshu(bi_list, start_idx):
        """
        尝试从 bi_list[start_idx] 开始构建中枢（标准缠论逻辑）

        返回 (zhongshu_or_None, next_idx)
        """
        if start_idx + 3 > len(bi_list):
            return None, start_idx

        b1, b2, b3 = bi_list[start_idx], bi_list[start_idx + 1], bi_list[start_idx + 2]

        h1, h2, h3 = (ZhongShuGenerator._bi_high(b) for b in (b1, b2, b3))
        l1, l2, l3 = (ZhongShuGenerator._bi_low(b) for b in (b1, b2, b3))

        # 初始中枢区间
        zg = min(h1, h2, h3)
        zd = max(l1, l2, l3)

        # 3笔无重叠，从中断处的下一笔重新搜索
        if not (zd < zg):
            return None, start_idx + 1

        # 初始中枢成立
        gg = max(h1, h2, h3)
        dd = min(l1, l2, l3)
        component_indices = [start_idx, start_idx + 1, start_idx + 2]
        last_overlap_idx = start_idx + 2  # 最后一笔与中枢重叠的笔索引

        # ── 延伸：检查后续笔是否与当前中枢区间重叠 ──
        # 一旦出现不重叠笔，中枢即结束（价格已离开中枢区间）
        i = start_idx + 3

        while i < len(bi_list):
            bi = bi_list[i]
            bh = ZhongShuGenerator._bi_high(bi)
            bl = ZhongShuGenerator._bi_low(bi)

            # 判断该笔是否与中枢区间 [zd, zg] 有交集
            # 有交集的条件：笔的区间与 [zd, zg] 相交，即 bh > zd 且 bl < zg
            if bh <= zd or bl >= zg:
                # 该笔不与中枢重叠 → 中枢结束
                break

            # 该笔与中枢重叠 → 纳入中枢，更新 ZG/ZD/GG/DD
            zg = min(zg, bh)
            zd = max(zd, bl)
            gg = max(gg, bh)
            dd = min(dd, bl)
            component_indices.append(i)
            last_overlap_idx = i
            i += 1

        # 判断中枢是否已完成（出现不重叠笔即完成）
        is_complete = (i < len(bi_list))

        zhongshu = ZhongShu(
            start_timestamp=b1['start_timestamp'],
            end_timestamp=bi_list[last_overlap_idx]['end_timestamp'],
            zg=zg,
            zd=zd,
            gg=gg,
            dd=dd,
            bi_count=len(component_indices),
            bi_indices=component_indices,
            is_complete=is_complete,
        )

        # 下一个搜索起始位置
        # 如果中枢已完成，从 last_overlap_idx + 1 继续搜索新中枢
        # 如果中枢进行中（数据已结束），next_idx = len(bi_list) 结束搜索
        next_idx = last_overlap_idx + 1 if is_complete else len(bi_list)
        return zhongshu, next_idx

    @classmethod
    def from_bi_list(cls, bi_list):
        """
        从笔列表生成中枢列表（标准缠论逻辑）
        bi_list: BiGenerator.generate_bi() 返回的笔字典列表
        返回: [ZhongShu, ...]
        """
        if len(bi_list) < 3:
            return []

        result = []
        idx = 0

        while idx <= len(bi_list) - 3:
            zs, next_idx = cls._try_form_zhongshu(bi_list, idx)
            if zs is not None:
                result.append(zs)
                idx = next_idx
            else:
                idx = next_idx

        return result

    @classmethod
    def to_render_data(cls, zhongshu_list):
        """
        将中枢列表转为前端渲染数据
        返回: {
            'zhongshu_boxes': [
                {
                    'start_timestamp': ...,
                    'end_timestamp': ...,
                    'zg': ...,
                    'zd': ...,
                    'gg': ...,
                    'dd': ...,
                    'bi_count': ...,
                    'is_complete': ...,   // 新增：中枢是否已完成
                },
                ...
            ]
        }
        """
        return {
            'zhongshu_boxes': [
                {
                    'start_timestamp': zs.start_timestamp,
                    'end_timestamp': zs.end_timestamp,
                    'zg': zs.zg,
                    'zd': zs.zd,
                    'gg': zs.gg,
                    'dd': zs.dd,
                    'bi_count': zs.bi_count,
                    'is_complete': zs.is_complete,
                }
                for zs in zhongshu_list
            ]
        }
