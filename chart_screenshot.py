"""
K线截图生成模块
用 matplotlib 生成当前K线图截图，包含笔、中枢、买卖点标记
"""
import io
from typing import Optional

import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime

from config import SCREENSHOT_MAX_KLINES


# 中文字体配置
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


def generate_chart_image(bi_data: dict, period: str, latest_price: Optional[float] = None) -> bytes:
    """
    生成K线截图

    Args:
        bi_data: get_bi_data() 返回的数据，包含 timestamps, ohlc, bi_lines, zhongshu_boxes, trade_points
        period: 周期
        latest_price: 最新价格（可选，显示在标题）

    Returns:
        PNG 图片的字节数据
    """
    timestamps = bi_data.get('timestamps', [])
    ohlc = bi_data.get('ohlc', [])
    bi_lines = bi_data.get('bi_lines', [])
    zhongshu_boxes = bi_data.get('zhongshu_boxes', [])
    trade_points = bi_data.get('trade_points', [])

    if not timestamps or not ohlc:
        # 无数据，生成空白图
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.text(0.5, 0.5, '暂无数据', ha='center', va='center', fontsize=16, color='gray')
        ax.set_axis_off()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='#1a1a2e')
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()

    # 最多显示指定数量的K线
    show_count = min(SCREENSHOT_MAX_KLINES, len(timestamps))
    timestamps_show = timestamps[-show_count:]
    ohlc_show = ohlc[-show_count:]

    # 根据K线数量动态调整图宽，避免过密
    fig_width = max(12, min(30, show_count * 0.08))

    # 转换时间戳为可读格式
    x_labels = []
    for ts in timestamps_show:
        try:
            if isinstance(ts, str):
                # 尝试解析常见格式
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S']:
                    try:
                        x_labels.append(datetime.strptime(ts, fmt))
                        break
                    except ValueError:
                        continue
                else:
                    x_labels.append(ts)
            else:
                x_labels.append(str(ts))
        except Exception:
            x_labels.append(str(ts))

    fig, ax = plt.subplots(figsize=(fig_width, 6), facecolor='#1a1a2e')
    ax.set_facecolor('#1a1a2e')

    # 绘制K线
    width = max(0.3, min(0.7, 8.0 / show_count)) if show_count > 0 else 0.6
    for i, (open_p, close_p, low_p, high_p) in enumerate(ohlc_show):
        color = '#e94560' if close_p >= open_p else '#0cce80'
        # 影线
        ax.plot([i, i], [low_p, high_p], color=color, linewidth=0.8, solid_capstyle='round')
        # 实体
        body_low = min(open_p, close_p)
        body_high = max(open_p, close_p)
        rect = Rectangle((i - width/2, body_low), width, max(body_high - body_low, 0.001),
                         facecolor=color, edgecolor=color, linewidth=0.5)
        ax.add_patch(rect)

    # 绘制笔（金色线段）
    if bi_lines:
        ts_to_idx = {}
        for i, ts in enumerate(timestamps_show):
            ts_to_idx[ts] = i

        for bi in bi_lines:
            start_ts = bi['start_timestamp']
            end_ts = bi['end_timestamp']
            if start_ts in ts_to_idx and end_ts in ts_to_idx:
                idx1 = ts_to_idx[start_ts]
                idx2 = ts_to_idx[end_ts]
                ax.plot([idx1, idx2], [bi['start_price'], bi['end_price']],
                        color='#FFD700', linewidth=1.2, alpha=0.85, zorder=5)

    # 绘制中枢（紫色半透明矩形）
    if zhongshu_boxes:
        for zs in zhongshu_boxes:
            start_ts = zs['start_timestamp']
            end_ts = zs['end_timestamp']
            if start_ts in ts_to_idx and end_ts in ts_to_idx:
                idx1 = ts_to_idx[start_ts]
                idx2 = ts_to_idx[end_ts]
                rect = Rectangle((idx1, zs['zd']), idx2 - idx1, zs['zg'] - zs['zd'],
                                 facecolor='rgba(147,112,219,0.15)' if False else (0.58, 0.44, 0.86, 0.12),
                                 edgecolor=(0.58, 0.44, 0.86, 0.6), linewidth=1, zorder=2)
                ax.add_patch(rect)

    # 绘制买卖点标记
    if trade_points:
        for tp in trade_points:
            ts = tp['timestamp']
            if ts in ts_to_idx:
                idx = ts_to_idx[ts]
                price = tp['price']
                is_buy = tp['type'] == 'buy'
                level = tp['level']

                if is_buy:
                    marker = '^'
                    color = '#0cce80'
                    label = f'L{level}买'
                    offset = -5
                else:
                    marker = 'v'
                    color = '#e94560'
                    label = f'L{level}卖'
                    offset = 5

                ax.plot(idx, price, marker=marker, color=color, markersize=10, zorder=10)
                ax.annotate(label, (idx, price), xytext=(0, offset * 3), textcoords='offset points',
                            ha='center', fontsize=7, color=color, fontweight='bold')

    # 坐标轴样式
    ax.set_xlim(-1, len(ohlc_show))
    ax.tick_params(axis='x', colors='#888', labelsize=7)
    ax.tick_params(axis='y', colors='#888', labelsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#0f3460')
    ax.spines['left'].set_color('#0f3460')
    ax.grid(True, axis='y', color='#0f3460', linestyle='--', linewidth=0.5, alpha=0.5)

    # X轴时间标签（稀疏显示）
    step = max(1, len(x_labels) // 10)
    ax.set_xticks(range(0, len(x_labels), step))
    ax.set_xticklabels([str(x_labels[i])[5:16] if isinstance(x_labels[i], datetime) else str(x_labels[i])
                        for i in range(0, len(x_labels), step)], rotation=30, ha='right')

    # 标题
    title = f'MNQ {period} 周期'
    if latest_price is not None:
        title += f'  最新价: {latest_price:.2f}'
    ax.set_title(title, color='#e0e0e0', fontsize=13, pad=10)

    plt.tight_layout()

    # 输出为字节
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, facecolor='#1a1a2e')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
