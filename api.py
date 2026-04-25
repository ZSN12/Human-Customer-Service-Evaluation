from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import json
from typing import Dict, List, Optional
from database import db
from task_manager import task_manager
from core import run_batch_analysis_with_task
from config import QUALITY_CONFIG, save_quality_config, load_quality_config
from datetime import datetime
import pandas as pd

app = FastAPI(
    title="人工客服质检系统 API",
    description="提供文件上传、任务管理、配置管理和统计数据等功能",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该设置具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传文件目录
UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """接收上传文件，保存并返回任务 ID"""
    try:
        # 保存上传的文件
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 读取文件并创建任务
        from utils import read_any_file
        df = read_any_file(file_path)
        
        # 检查文件是否有效
        if df.empty:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="文件为空或格式错误")
        
        # 从 config 导入 settings
        from config import settings
        
        # 创建任务
        task_id = run_batch_analysis_with_task(df, settings)
        
        # 返回任务 ID
        return {
            "task_id": task_id,
            "filename": file.filename,
            "status": "created"
        }
    except Exception as e:
        # 打印详细的错误信息
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """返回任务状态、进度和结果"""
    try:
        task_status = task_manager.get_task_status(task_id)
        
        # 如果任务已完成，返回结果
        if task_status.get("status") == "completed":
            result = task_status.get("result")
            if result:
                results, summary_df, error_stats_df = result
                # 转换为字典格式
                results_dict = [
                    {
                        "会话ID": r["会话ID"],
                        "最终得分": r["最终得分"],
                        "扣分项编码": r["扣分项编码"],
                        "优化建议": r["优化建议"],
                        "报告文件": r["报告文件"]
                    }
                    for r in results
                ]
                
                summary_dict = summary_df.to_dict("records") if summary_df is not None else []
                error_stats_dict = error_stats_df.to_dict("records") if error_stats_df is not None else []
                
                return {
                    "task_id": task_id,
                    "status": task_status.get("status"),
                    "progress": task_status.get("progress"),
                    "total": task_status.get("total"),
                    "result": {
                        "results": results_dict,
                        "summary": summary_dict,
                        "error_stats": error_stats_dict
                    },
                    "created_at": task_status.get("created_at"),
                    "updated_at": task_status.get("updated_at")
                }
        
        # 返回任务状态
        return {
            "task_id": task_id,
            "status": task_status.get("status"),
            "progress": task_status.get("progress"),
            "total": task_status.get("total"),
            "error": task_status.get("error"),
            "created_at": task_status.get("created_at"),
            "updated_at": task_status.get("updated_at")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_config():
    """读取质检配置"""
    try:
        return {
            "config": QUALITY_CONFIG
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def update_config(config: Dict):
    """更新质检配置"""
    try:
        # 验证配置格式
        if "dimensions" not in config:
            raise HTTPException(status_code=400, detail="配置格式错误，缺少 dimensions 字段")
        
        # 更新全局配置
        global QUALITY_CONFIG
        QUALITY_CONFIG = config
        
        # 保存到数据库
        save_quality_config()
        
        return {
            "status": "success",
            "message": "配置更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """获取历史统计数据和趋势分析结果"""
    try:
        # 从数据库获取历史质检结果
        conn = db._init_db()
        cursor = conn.cursor()
        
        # 获取所有质检结果
        cursor.execute("SELECT * FROM quality_results ORDER BY session_date DESC")
        rows = cursor.fetchall()
        conn.close()
        
        # 计算统计数据
        total_sessions = len(rows)
        total_score = 0
        pass_count = 0
        
        for row in rows:
            score = row[2]  # final_score
            total_score += score
            if score >= 80:  # 假设 80 分为合格
                pass_count += 1
        
        avg_score = total_score / total_sessions if total_sessions > 0 else 0
        pass_rate = pass_count / total_sessions if total_sessions > 0 else 0
        
        # 按日期统计
        date_stats = {}
        for row in rows:
            session_date = row[8]  # session_date
            if session_date:
                date_str = session_date.strftime("%Y-%m-%d")
                if date_str not in date_stats:
                    date_stats[date_str] = {
                        "count": 0,
                        "total_score": 0,
                        "pass_count": 0
                    }
                date_stats[date_str]["count"] += 1
                date_stats[date_str]["total_score"] += row[2]
                if row[2] >= 80:
                    date_stats[date_str]["pass_count"] += 1
        
        # 转换日期统计为列表
        date_stats_list = []
        for date_str, stats in date_stats.items():
            date_stats_list.append({
                "date": date_str,
                "count": stats["count"],
                "avg_score": stats["total_score"] / stats["count"],
                "pass_rate": stats["pass_count"] / stats["count"]
            })
        
        # 按日期排序
        date_stats_list.sort(key=lambda x: x["date"])
        
        return {
            "total_sessions": total_sessions,
            "avg_score": round(avg_score, 2),
            "pass_rate": round(pass_rate, 2),
            "date_stats": date_stats_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
