# task_manager.py
import uuid
import json
import sqlite3
import traceback
import logging
from typing import Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor, Future
from database import db

class TaskManager:
    """任务管理器"""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.tasks: Dict[str, Future] = {}

    def create_task(self, task_func, *args, **kwargs) -> str:
        """创建任务"""
        task_id = str(uuid.uuid4())

        # 存储任务到数据库
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (id, status) VALUES (?, ?)",
                (task_id, 'pending')
            )

        # 提交任务到线程池
        future = self.executor.submit(self._wrap_task, task_id, task_func, *args, **kwargs)
        self.tasks[task_id] = future

        return task_id

    def _wrap_task(self, task_id: str, task_func, *args, **kwargs):
        """包装任务执行"""
        try:
            self.update_task_status(task_id, 'running', 0, 0)

            # 定义进度回调
            def progress_callback(current: int, total: int, *args):
                try:
                    self.update_task_status(task_id, 'running', current, total)
                except Exception as e:
                    logging.error(f"进度更新失败: {e}")

            def log_callback(msg: str):
                try:
                    logging.info(f"任务 {task_id}: {msg}")
                except:
                    pass

            # 执行任务 - 捕获所有异常
            result = None
            error_msg = None
            try:
                result = task_func(*args, **kwargs, progress_callback=progress_callback, log_callback=log_callback)
            except Exception as e:
                error_msg = f"任务执行失败: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)

            # 根据执行结果更新状态
            if error_msg:
                self.update_task_status(
                    task_id, 'failed', 0, 0,
                    error=error_msg
                )
                return None
            else:
                self.update_task_status(
                    task_id, 'completed', 100, 100,
                    result=json.dumps(result, ensure_ascii=False)
                )
                return result

        except Exception as e:
            # 捕获所有意外的异常，确保任务不会假死
            error_msg = f"任务包装器异常: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)
            try:
                self.update_task_status(
                    task_id, 'failed', 0, 0,
                    error=error_msg
                )
            except:
                pass
            return None

    def update_task_status(self, task_id: str, status: str, progress: int = 0, total: int = 0,
                          result: Optional[str] = None, error: Optional[str] = None):
        """更新任务状态"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()

                update_fields = ['status', 'progress', 'total', 'updated_at']
                update_values = [status, progress, total, 'CURRENT_TIMESTAMP']

                if result is not None:
                    update_fields.append('result')
                    update_values.append(result)
                if error is not None:
                    update_fields.append('error')
                    update_values.append(error)

                set_clause = ', '.join([f"{field} = ?" for field in update_fields])
                sql = f"UPDATE tasks SET {set_clause} WHERE id = ?"
                update_values.append(task_id)

                cursor.execute(sql, update_values)
        except Exception as e:
            logging.error(f"更新任务状态失败: {e}")

    def get_task_status(self, task_id: str) -> Dict:
        """获取任务状态"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, status, progress, total, result, error, created_at, updated_at FROM tasks WHERE id = ?",
                    (task_id,)
                )
                row = cursor.fetchone()

            if not row:
                return {'status': 'not_found'}

            task_data = {
                'id': row[0],
                'status': row[1],
                'progress': row[2],
                'total': row[3],
                'result': json.loads(row[4]) if row[4] else None,
                'error': row[5],
                'created_at': row[6],
                'updated_at': row[7]
            }
            return task_data
        except Exception as e:
            logging.error(f"获取任务状态失败: {e}")
            return {'status': 'error', 'error': str(e)}

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.tasks:
            future = self.tasks[task_id]
            if not future.done():
                future.cancel()
                self.update_task_status(task_id, 'cancelled')
                return True
        return False

    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        try:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, status, progress, total, result, error, created_at, updated_at FROM tasks ORDER BY created_at DESC"
                )
                rows = cursor.fetchall()

            tasks = []
            for row in rows:
                task_data = {
                    'id': row[0],
                    'status': row[1],
                    'progress': row[2],
                    'total': row[3],
                    'result': json.loads(row[4]) if row[4] else None,
                    'error': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                }
                tasks.append(task_data)

            return tasks
        except Exception as e:
            logging.error(f"获取所有任务失败: {e}")
            return []

    def close(self):
        """关闭线程池"""
        self.executor.shutdown(wait=True)


# 全局任务管理器实例
task_manager = TaskManager()