# database.py
import sqlite3
import json
from typing import List, Dict, Optional
import os
import streamlit as st


class Database:
    """数据库管理"""

    def __init__(self, db_path: str = "quality_check.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 启用WAL模式
            cursor.execute('PRAGMA journal_mode=WAL;')

            # 创建质检结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quality_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT UNIQUE,
                    final_score INTEGER,
                    total_deduction INTEGER,
                    hit_codes TEXT,
                    optimization TEXT,
                    report_file TEXT,
                    session_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    total INTEGER DEFAULT 0,
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建规则表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    dimension TEXT NOT NULL,
                    error_code TEXT UNIQUE NOT NULL,
                    rule_type TEXT NOT NULL,
                    params TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 为session_date字段添加索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_quality_results_session_date ON quality_results(session_date)')

    def save_quality_result(self, result: Dict):
        """保存质检结果"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                '''INSERT OR REPLACE INTO quality_results
                   (conversation_id, final_score, total_deduction, hit_codes, optimization, report_file, session_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (
                    result.get('会话ID'),
                    result.get('最终得分'),
                    result.get('总扣分', 0),
                    result.get('扣分项编码', ''),
                    result.get('优化建议', ''),
                    result.get('报告文件', ''),
                    result.get('会话日期')
                )
            )

    def get_quality_result(self, conversation_id: str) -> Optional[Dict]:
        """获取质检结果"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """SELECT conversation_id, final_score, total_deduction, hit_codes, optimization, report_file, session_date, created_at
                   FROM quality_results WHERE conversation_id = ?""",
                (conversation_id,)
            )

            row = cursor.fetchone()

        if not row:
            return None

        return {
            '会话ID': row[0],
            '最终得分': row[1],
            '总扣分': row[2],
            '扣分项编码': row[3],
            '优化建议': row[4],
            '报告文件': row[5],
            '会话日期': row[6],
            '创建时间': row[7]
        }

    def get_quality_results(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """获取质检结果列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """SELECT conversation_id, final_score, total_deduction, hit_codes, optimization, report_file, session_date, created_at
                   FROM quality_results ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            )

            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                '会话ID': row[0],
                '最终得分': row[1],
                '总扣分': row[2],
                '扣分项编码': row[3],
                '优化建议': row[4],
                '报告文件': row[5],
                '会话日期': row[6],
                '创建时间': row[7]
            })

        return results

    def get_quality_stats(self) -> Dict:
        """获取质检统计数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 总会话数
            cursor.execute("SELECT COUNT(*) FROM quality_results")
            total_count = cursor.fetchone()[0]

            # 平均得分
            cursor.execute("SELECT AVG(final_score) FROM quality_results")
            avg_score = cursor.fetchone()[0] or 0

            # 满分会话数
            cursor.execute("SELECT COUNT(*) FROM quality_results WHERE final_score = 100")
            perfect_count = cursor.fetchone()[0]

            # 不合格会话数（得分 < 60）
            cursor.execute("SELECT COUNT(*) FROM quality_results WHERE final_score < 60")
            failed_count = cursor.fetchone()[0]

        return {
            '总会话数': total_count,
            '平均得分': round(avg_score, 2),
            '满分会话数': perfect_count,
            '不合格会话数': failed_count
        }

    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        """获取每日统计数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 计算时间范围
            import datetime
            end_date = datetime.datetime.now().date()
            start_date = end_date - datetime.timedelta(days=days)
            start_date_str = start_date.isoformat()

            cursor.execute('''
                SELECT
                    date(session_date) as date,
                    COUNT(*) as session_count,
                    AVG(final_score) as avg_score,
                    COUNT(CASE WHEN final_score = 100 THEN 1 END) as perfect_count,
                    COUNT(CASE WHEN final_score < 60 THEN 1 END) as failed_count
                FROM quality_results
                WHERE session_date >= ?
                GROUP BY date(session_date)
                ORDER BY date(session_date)
            ''', (start_date_str,))

            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'date': row[0],
                'session_count': row[1],
                'avg_score': round(row[2] or 0, 2),
                'perfect_count': row[3],
                'failed_count': row[4]
            })

        return results

    def get_weekly_stats(self, weeks: int = 12) -> List[Dict]:
        """获取每周统计数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 计算时间范围
            import datetime
            end_date = datetime.datetime.now().date()
            start_date = end_date - datetime.timedelta(weeks=weeks)
            start_date_str = start_date.isoformat()

            cursor.execute('''
                SELECT
                    strftime('%Y-W%W', session_date) as week,
                    COUNT(*) as session_count,
                    AVG(final_score) as avg_score,
                    COUNT(CASE WHEN final_score = 100 THEN 1 END) as perfect_count,
                    COUNT(CASE WHEN final_score < 60 THEN 1 END) as failed_count
                FROM quality_results
                WHERE session_date >= ?
                GROUP BY strftime('%Y-W%W', session_date)
                ORDER BY strftime('%Y-W%W', session_date)
            ''', (start_date_str,))

            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'week': row[0],
                'session_count': row[1],
                'avg_score': round(row[2] or 0, 2),
                'perfect_count': row[3],
                'failed_count': row[4]
            })

        return results

    def get_monthly_stats(self, months: int = 12) -> List[Dict]:
        """获取每月统计数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 计算时间范围
            import datetime
            end_date = datetime.datetime.now().date()
            start_date = end_date - datetime.timedelta(days=months * 30)
            start_date_str = start_date.isoformat()

            cursor.execute('''
                SELECT
                    strftime('%Y-%m', session_date) as month,
                    COUNT(*) as session_count,
                    AVG(final_score) as avg_score,
                    COUNT(CASE WHEN final_score = 100 THEN 1 END) as perfect_count,
                    COUNT(CASE WHEN final_score < 60 THEN 1 END) as failed_count
                FROM quality_results
                WHERE session_date >= ?
                GROUP BY strftime('%Y-%m', session_date)
                ORDER BY strftime('%Y-%m', session_date)
            ''', (start_date_str,))

            rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'month': row[0],
                'session_count': row[1],
                'avg_score': round(row[2] or 0, 2),
                'perfect_count': row[3],
                'failed_count': row[4]
            })

        return results

    def calculate_week_over_week(self) -> List[Dict]:
        """计算周环比"""
        weekly_stats = self.get_weekly_stats(13)
        results = []

        for i in range(1, len(weekly_stats)):
            current = weekly_stats[i]
            previous = weekly_stats[i-1]

            score_change = current['avg_score'] - previous['avg_score']
            score_change_percent = (score_change / previous['avg_score'] * 100) if previous['avg_score'] > 0 else 0

            results.append({
                'week': current['week'],
                'current_score': current['avg_score'],
                'previous_score': previous['avg_score'],
                'score_change': round(score_change, 2),
                'score_change_percent': round(score_change_percent, 2),
                'session_count': current['session_count']
            })

        return results

    def calculate_month_over_month(self) -> List[Dict]:
        """计算月同比"""
        monthly_stats = self.get_monthly_stats(13)
        results = []

        for i in range(1, len(monthly_stats)):
            current = monthly_stats[i]
            previous = monthly_stats[i-1]

            score_change = current['avg_score'] - previous['avg_score']
            score_change_percent = (score_change / previous['avg_score'] * 100) if previous['avg_score'] > 0 else 0

            results.append({
                'month': current['month'],
                'current_score': current['avg_score'],
                'previous_score': previous['avg_score'],
                'score_change': round(score_change, 2),
                'score_change_percent': round(score_change_percent, 2),
                'session_count': current['session_count']
            })

        return results

    def get_dimension_trends(self, days: int = 30) -> List[Dict]:
        """获取维度趋势分析"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 计算时间范围
            import datetime
            end_date = datetime.datetime.now().date()
            start_date = end_date - datetime.timedelta(days=days)
            start_date_str = start_date.isoformat()

            # 获取最近30天的质检结果
            cursor.execute('''
                SELECT
                    date(session_date) as date,
                    final_score,
                    hit_codes
                FROM quality_results
                WHERE session_date >= ?
                ORDER BY date(session_date)
            ''', (start_date_str,))

            rows = cursor.fetchall()

        # 维度映射（根据扣分项编码映射到维度）
        dimension_mapping = {
            'Complaint_Mention': 'Dialogue_Logic',
            'Repeat_Response': 'Dialogue_Logic',
            'Privacy_Leak': 'Policy_Compliance',
            'Rude_Language': 'Policy_Compliance',
            'Bad_Attitude': 'Policy_Compliance',
            'Template_Overuse': 'Service_Quality',
            'No_Solution_Provided': 'Service_Quality'
        }

        # 按日期和维度统计
        daily_dimension_stats = {}
        for row in rows:
            date = row[0]
            score = row[1]
            hit_codes = row[2] or ''

            if date not in daily_dimension_stats:
                daily_dimension_stats[date] = {
                    'date': date,
                    'total_score': 0,
                    'total_count': 0,
                    'dimensions': {}
                }

            daily_dimension_stats[date]['total_score'] += score
            daily_dimension_stats[date]['total_count'] += 1

            # 解析扣分项编码
            codes = [code.strip() for code in hit_codes.split(',') if code.strip()]
            for code in codes:
                dimension = dimension_mapping.get(code, 'Other')
                if dimension not in daily_dimension_stats[date]['dimensions']:
                    daily_dimension_stats[date]['dimensions'][dimension] = 0
                daily_dimension_stats[date]['dimensions'][dimension] += 1

        # 计算每日各维度的平均得分和占比
        results = []
        for date, stats in sorted(daily_dimension_stats.items()):
            avg_score = stats['total_score'] / stats['total_count'] if stats['total_count'] > 0 else 0

            dimension_data = []
            for dimension, count in stats['dimensions'].items():
                dimension_data.append({
                    'dimension': dimension,
                    'count': count,
                    'percentage': round(count / stats['total_count'] * 100, 2) if stats['total_count'] > 0 else 0
                })

            results.append({
                'date': date,
                'avg_score': avg_score,
                'session_count': stats['total_count'],
                'dimensions': dimension_data
            })

        return results

    def get_dimension_summary(self) -> Dict:
        """获取维度汇总分析"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 获取所有质检结果
            cursor.execute('''
                SELECT
                    final_score,
                    hit_codes
                FROM quality_results
            ''')

            rows = cursor.fetchall()

        # 维度映射
        dimension_mapping = {
            'Complaint_Mention': 'Dialogue_Logic',
            'Repeat_Response': 'Dialogue_Logic',
            'Privacy_Leak': 'Policy_Compliance',
            'Rude_Language': 'Policy_Compliance',
            'Bad_Attitude': 'Policy_Compliance',
            'Template_Overuse': 'Service_Quality',
            'No_Solution_Provided': 'Service_Quality'
        }

        # 统计维度数据
        dimension_stats = {}
        total_score = 0
        total_count = 0

        for row in rows:
            score = row[0]
            hit_codes = row[1] or ''

            total_score += score
            total_count += 1

            # 解析扣分项编码
            codes = [code.strip() for code in hit_codes.split(',') if code.strip()]
            for code in codes:
                dimension = dimension_mapping.get(code, 'Other')
                if dimension not in dimension_stats:
                    dimension_stats[dimension] = 0
                dimension_stats[dimension] += 1

        # 计算汇总数据
        avg_score = total_score / total_count if total_count > 0 else 0

        dimension_data = []
        for dimension, count in dimension_stats.items():
            dimension_data.append({
                'dimension': dimension,
                'count': count,
                'percentage': round(count / total_count * 100, 2) if total_count > 0 else 0
            })

        return {
            'total_session_count': total_count,
            'average_score': round(avg_score, 2),
            'dimension_distribution': dimension_data
        }

    def save_config(self, key: str, value: str):
        """保存配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT OR REPLACE INTO configs (key, value) VALUES (?, ?)",
                (key, value)
            )

    def get_config(self, key: str) -> Optional[str]:
        """获取配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM configs WHERE key = ?", (key,))
            row = cursor.fetchone()

        return row[0] if row else None

    def get_all_configs(self) -> Dict[str, str]:
        """获取所有配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT key, value FROM configs")
            rows = cursor.fetchall()

        configs = {}
        for row in rows:
            configs[row[0]] = row[1]

        return configs

    def save_rule(self, rule: Dict) -> int:
        """保存规则"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if 'id' in rule and rule['id']:
                # 更新规则
                cursor.execute(
                    """UPDATE rules
                       SET name = ?, dimension = ?, error_code = ?, rule_type = ?, params = ?, is_active = ?
                       WHERE id = ?""",
                    (
                        rule['name'],
                        rule['dimension'],
                        rule['error_code'],
                        rule['rule_type'],
                        rule.get('params', '{}'),
                        rule.get('is_active', 1),
                        rule['id']
                    )
                )
                rule_id = rule['id']
            else:
                # 插入新规则
                cursor.execute(
                    """INSERT INTO rules (name, dimension, error_code, rule_type, params, is_active)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        rule['name'],
                        rule['dimension'],
                        rule['error_code'],
                        rule['rule_type'],
                        rule.get('params', '{}'),
                        rule.get('is_active', 1)
                    )
                )
                rule_id = cursor.lastrowid

        return rule_id

    def get_rules(self, is_active: bool = None) -> List[Dict]:
        """获取规则列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if is_active is not None:
                cursor.execute("SELECT * FROM rules WHERE is_active = ? ORDER BY id", (1 if is_active else 0,))
            else:
                cursor.execute("SELECT * FROM rules ORDER BY id")

            rows = cursor.fetchall()

        rules = []
        for row in rows:
            rules.append({
                'id': row[0],
                'name': row[1],
                'dimension': row[2],
                'error_code': row[3],
                'rule_type': row[4],
                'params': row[5],
                'is_active': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            })

        return rules

    def get_rule(self, rule_id: int) -> Optional[Dict]:
        """获取单个规则"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()

        if not row:
            return None

        return {
            'id': row[0],
            'name': row[1],
            'dimension': row[2],
            'error_code': row[3],
            'rule_type': row[4],
            'params': row[5],
            'is_active': row[6],
            'created_at': row[7],
            'updated_at': row[8]
        }

    def delete_rule(self, rule_id: int) -> bool:
        """删除规则"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            affected = cursor.rowcount

        return affected > 0

    def save_quality_config(self, config: dict):
        """保存质检配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            import json
            config_json = json.dumps(config, ensure_ascii=False)

            cursor.execute(
                "INSERT OR REPLACE INTO configs (key, value) VALUES (?, ?)",
                ("quality_config", config_json)
            )

    def get_quality_config(self) -> Optional[dict]:
        """获取质检配置"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM configs WHERE key = ?", ("quality_config",))
            row = cursor.fetchone()

        if row:
            import json
            try:
                return json.loads(row[0])
            except Exception as e:
                return None
        return None

    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        class ConnectionContext:
            def __init__(self, db_path):
                self.db_path = db_path
                self.conn = None

            def __enter__(self):
                self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
                return self.conn

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.conn:
                    if exc_type is None:
                        self.conn.commit()
                    else:
                        self.conn.rollback()
                    self.conn.close()

        return ConnectionContext(self.db_path)


# 使用 @st.cache_resource 缓存数据库实例
@st.cache_resource
def get_db_instance():
    """获取全局数据库实例（缓存）"""
    return Database()


# 全局数据库实例
db = get_db_instance()