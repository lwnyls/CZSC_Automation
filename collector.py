"""
获取行情数据并存储到 SQLite 数据库和 TXT 文件
"""
import uiautomation as auto
import sqlite3
import time
import datetime

def init_database():
    """初始化 SQLite 数据库"""
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tick_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        buy1 REAL
    )
    ''')
    
    conn.commit()
    return conn

def find_trading_window():
    """查找行情交易系统窗口"""
    window = None
    
    try:
        window = auto.WindowControl(searchDepth=1, Name='行情交易系统   V5.1.1.6')
        if window.Exists():
            print("✓ 找到窗口：" + window.Name)
            return window
    except Exception as e:
        print(f"方法 1 失败：{e}")
    
    try:
        window = auto.WindowControl(searchDepth=1, SubName='行情交易')
        if window.Exists():
            print("✓ 找到窗口：" + window.Name)
            return window
    except Exception as e:
        print(f"方法 2 失败：{e}")
    
    return None

def find_buy1_controls(window):
    """找到所有包含买1数据的控件"""
    buy1_controls = []
    
    def traverse(ctrl):
        try:
            try:
                pattern = ctrl.GetLegacyIAccessiblePattern()
                if pattern and pattern.Value:
                    value = pattern.Value
                    if value.startswith('买1;') and ';' in value:
                        buy1_controls.append(ctrl)
            except:
                pass
            
            try:
                children = ctrl.GetChildren()
                for child in children:
                    traverse(child)
            except:
                pass
                
        except:
            pass
    
    traverse(window)
    return buy1_controls

def extract_price_from_control(ctrl):
    """从控件中提取价格值"""
    try:
        pattern = ctrl.GetLegacyIAccessiblePattern()
        if pattern and pattern.Value:
            value = pattern.Value
            if ';' in value:
                parts = value.split(';')
                if len(parts) >= 2:
                    try:
                        return float(parts[1].strip())
                    except:
                        pass
    except:
        pass
    return None

DATA_DIR = 'data'

def get_today_filename():
    """获取今日文件名"""
    return datetime.datetime.now().strftime("%Y-%m-%d") + ".txt"

def write_to_txt(time_str, buy1_price):
    """写入 TXT 文件到 data/ 目录"""
    import os
    os.makedirs(DATA_DIR, exist_ok=True)
    filename = os.path.join(DATA_DIR, get_today_filename())
    line = f"{time_str},{buy1_price}\n"
    
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(line)

def main():
    print("=" * 70)
    print("行情数据采集程序")
    print("数据将同时保存到 SQLite 和 TXT 文件")
    print("=" * 70)
    
    conn = init_database()
    cursor = conn.cursor()
    print("✓ 数据库初始化完成")
    
    window = find_trading_window()
    if not window:
        print("✗ 未找到行情交易系统窗口")
        return
    
    print("\n正在定位买1控件...")
    buy1_controls = find_buy1_controls(window)
    
    if not buy1_controls:
        print("✗ 未找到买1控件")
        return
    
    print(f"✓ 找到 {len(buy1_controls)} 个买1控件")
    
    buy1_ctrl = buy1_controls[0]
    print("✓ 开始采集数据...")
    print("=" * 70)
    
    try:
        while True:
            now = datetime.datetime.now()
            time_str = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            buy1_price = extract_price_from_control(buy1_ctrl)
            
            if buy1_price is not None:
                print(f"{time_str} - 买1: {buy1_price}")
                
                # 保存到 SQLite
                cursor.execute('''
                INSERT INTO tick_data (timestamp, buy1)
                VALUES (?, ?)
                ''', (time_str, buy1_price))
                conn.commit()
                
                # 写入 TXT 文件
                write_to_txt(time_str, buy1_price)
                
                # 查询记录数
                cursor.execute('SELECT COUNT(*) FROM tick_data')
                total_count = cursor.fetchone()[0]
                print(f"  已保存 {total_count} 条记录 (SQLite + TXT)")
            else:
                print(f"{time_str} - 未获取到数据")
            
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        print("用户终止程序")
    finally:
        conn.close()
        print("✓ 数据库连接已关闭")

if __name__ == '__main__':
    main()
