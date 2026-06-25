"""
MarketDataReader - 从 SQLite 数据库读取 tick 数据
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Tuple


class MarketDataReader:
    """市场数据读取器，从 data.db 读取 tick 数据"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.db')
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_ticks(self) -> List[Tuple[str, float]]:
        """获取所有 tick 数据，返回 [(timestamp, price), ...]"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, buy1 FROM tick_data ORDER BY id ASC")
            rows = cursor.fetchall()
            return [(row['timestamp'], row['buy1']) for row in rows]
        finally:
            conn.close()

    def get_ticks_since(self, last_id: int = 0) -> List[Tuple[int, str, float]]:
        """获取指定 id 之后的 tick 数据，返回 [(id, timestamp, price), ...]"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, timestamp, buy1 FROM tick_data WHERE id > ? ORDER BY id ASC",
                (last_id,)
            )
            rows = cursor.fetchall()
            return [(row['id'], row['timestamp'], row['buy1']) for row in rows]
        finally:
            conn.close()

    def get_ticks_in_range(self, start_time: str, end_time: str) -> List[Tuple[str, float]]:
        """获取指定时间范围内的 tick 数据"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT timestamp, buy1 FROM tick_data WHERE timestamp >= ? AND timestamp <= ? ORDER BY id ASC",
                (start_time, end_time)
            )
            rows = cursor.fetchall()
            return [(row['timestamp'], row['buy1']) for row in rows]
        finally:
            conn.close()

    def get_latest_tick(self) -> Optional[Tuple[int, str, float]]:
        """获取最新一条 tick 数据"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, timestamp, buy1 FROM tick_data ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return (row['id'], row['timestamp'], row['buy1'])
            return None
        finally:
            conn.close()

    def get_count(self) -> int:
        """获取总记录数"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM tick_data")
            return cursor.fetchone()['cnt']
        finally:
            conn.close()

    def get_time_range(self) -> Tuple[str, str]:
        """获取数据的时间范围 (最早, 最晚)"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MIN(timestamp) as min_t, MAX(timestamp) as max_t FROM tick_data")
            row = cursor.fetchone()
            return (row['min_t'], row['max_t'])
        finally:
            conn.close()

    def get_latest_id(self) -> int:
        """获取最新的 id"""
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) as max_id FROM tick_data")
            row = cursor.fetchone()
            return row['max_id'] or 0
        finally:
            conn.close()


if __name__ == '__main__':
    reader = MarketDataReader()
    count = reader.get_count()
    time_range = reader.get_time_range()
    latest = reader.get_latest_tick()
    print(f"总记录数: {count}")
    print(f"时间范围: {time_range[0]} ~ {time_range[1]}")
    print(f"最新 tick: id={latest[0]}, time={latest[1]}, price={latest[2]}")
