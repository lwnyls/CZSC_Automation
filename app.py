"""
Flask 后端 - K线实时渲染服务
"""

import threading
import time
from flask import Flask, render_template, jsonify, request

from reader import MarketDataReader
from kline import KLineGenerator
from tradepoint_monitor import TradePointMonitor

app = Flask(__name__)

# 全局状态
reader = MarketDataReader()
generators = {}  # period -> KLineGenerator
lock = threading.Lock()
DEFAULT_PERIOD = '1m'

# 买卖点监控器
trade_point_monitor = None


def init_generators():
    """初始化K线生成器，加载历史数据"""
    print("正在加载 tick 数据...")
    ticks = reader.get_all_ticks()
    print(f"共 {len(ticks)} 条 tick 数据")

    for period in ['5s', '1m', '5m', '15m', '30m', '1h']:
        gen = KLineGenerator(period=period)
        gen.build_from_ticks(ticks)
        generators[period] = gen
        print(f"  {period}: {gen.total_bars} 根K线")

    print("初始化完成")


def poll_new_ticks():
    """后台线程：轮询新 tick 数据并更新所有K线"""
    global generators
    print("启动新数据轮询线程...")

    while True:
        try:
            with lock:
                # 使用任意一个 generator 的 last_tick_id
                gen = generators.get(DEFAULT_PERIOD)
                if gen:
                    last_id = gen.last_tick_id
                else:
                    last_id = 0

                new_ticks = reader.get_ticks_since(last_id)
                if new_ticks:
                    for period, gen in generators.items():
                        gen.add_ticks_batch(new_ticks)
        except Exception as e:
            print(f"轮询异常: {e}")

        time.sleep(1)  # 每秒检查一次


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/klines')
def api_klines():
    """
    获取K线数据
    参数:
        period: 周期 (1m, 5m, 15m, 30m, 1h)
        count: 返回最近N根K线，默认500
        include: 是否启用缠论K线包含处理 (true/false)，默认false
    """
    period = request.args.get('period', DEFAULT_PERIOD)
    count = int(request.args.get('count', 500))
    include = request.args.get('include', 'false').lower() == 'true'

    with lock:
        gen = generators.get(period)
        if not gen:
            return jsonify({'error': f'不支持的周期: {period}'}), 400

        if include:
            data = gen.get_klines_echarts_with_include(count)
        else:
            data = gen.get_klines_echarts(count)
        latest_bar = gen.latest_bar

    return jsonify({
        'period': period,
        'total_bars': gen.total_bars,
        'included_count': len(data['timestamps']),
        'latest': {
            'timestamp': latest_bar.timestamp,
            'open': latest_bar.open,
            'high': latest_bar.high,
            'low': latest_bar.low,
            'close': latest_bar.close,
            'volume': latest_bar.volume,
        } if latest_bar else None,
        **data,
    })


@app.route('/api/info')
def api_info():
    """获取数据库和K线基本信息"""
    with lock:
        info = {
            'tick_count': reader.get_count(),
            'time_range': reader.get_time_range(),
            'periods': {},
        }
        for period, gen in generators.items():
            latest = gen.latest_bar
            info['periods'][period] = {
                'total_bars': gen.total_bars,
                'latest_close': latest.close if latest else None,
                'latest_time': latest.timestamp if latest else None,
            }

    return jsonify(info)


@app.route('/api/periods')
def api_periods():
    """获取支持的周期列表"""
    return jsonify({
        'periods': list(generators.keys()),
        'default': DEFAULT_PERIOD,
    })


@app.route('/api/bi')
def api_bi():
    """获取缠论笔数据（内部自动进行包含处理）"""
    period = request.args.get('period', DEFAULT_PERIOD)
    count = int(request.args.get('count', 500))

    with lock:
        gen = generators.get(period)
        if not gen:
            return jsonify({'error': f'不支持的周期: {period}'}), 400
        data = gen.get_bi_data(count)

    return jsonify(data)


@app.route('/api/monitor/status')
def api_monitor_status():
    """获取买卖点监控状态"""
    if trade_point_monitor:
        return jsonify(trade_point_monitor.get_status())
    return jsonify({'running': False})


if __name__ == '__main__':
    init_generators()

    # 启动后台轮询线程
    poll_thread = threading.Thread(target=poll_new_ticks, daemon=True)
    poll_thread.start()

    # 启动买卖点监控线程
    trade_point_monitor = TradePointMonitor(generators, lock)
    trade_point_monitor.start()

    print("\n启动 Web 服务...")
    app.run(host='0.0.0.0', port=5000, debug=False)
