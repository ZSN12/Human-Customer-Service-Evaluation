# main.py
import os
import logging
import pandas as pd
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from logging.handlers import TimedRotatingFileHandler

from config import TYPE_MAPPING, FILTER_TYPES, QUALITY_CONFIG, OUTPUT_FOLDER, settings
from llm_service import deepseek_chat_completion, build_llm_quality_prompt
from rule_engine import rule_engine_check
from report_generator import generate_full_report, save_report_to_file
from data_processor import format_chat_for_llm, filter_conversation_data_for_llm
from database import db

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 5))
CSV_FILE_PATH = os.getenv("CSV_FILE_PATH", "./2.csv")


def setup_logging():
    """设置日志"""
    log_folder = os.path.join(OUTPUT_FOLDER, "logs")
    os.makedirs(log_folder, exist_ok=True)
    log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger()
    logger.setLevel(logging.getLevelName(LOG_LEVEL))
    logger.handlers.clear()
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    file_handler = TimedRotatingFileHandler(filename=os.path.join(log_folder, "quality_check.log"), when="D", interval=1, backupCount=30, encoding="utf-8")
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    logging.info("=" * 60)
    logging.info("电商人工客服质检系统启动")
    logging.info(f"并发数: {MAX_WORKERS}")


def init_output_folder():
    """初始化输出文件夹"""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)


def llm_full_quality_check(conversation_data: List[Dict], rule_hit_items: List[Dict]) -> Dict:
    """LLM质量检查"""
    system_prompt = build_llm_quality_prompt()
    filtered_data = filter_conversation_data_for_llm(conversation_data)
    formatted_chat = format_chat_for_llm(filtered_data)
    user_input = f"\n【对话内容】：\n{formatted_chat}\n\n【规则引擎已命中】：\n{rule_hit_items}"
    return deepseek_chat_completion(system_prompt, user_input)


def process_single_conversation(conversation_id: str, full_conversation: List[Dict], session_date: Optional[str] = None):
    """处理单个会话"""
    try:
        logging.info(f"处理会话: {conversation_id}")
        
        # 验证会话数据
        if not full_conversation or not isinstance(full_conversation, list):
            raise ValueError("无效的会话数据")
        
        # 提取人工回复和用户消息
        human_only = [msg for msg in full_conversation if msg.get('type') in [1, 5]]
        
        if not human_only:
            # 没有人工回复，返回默认结果
            logging.info(f"会话 {conversation_id} 无人工回复，跳过质检")
            full_report = {
                "conversation_id": conversation_id,
                "质检时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "质检核心结果": {
                    "初始满分": QUALITY_CONFIG["initial_score"],
                    "最终得分": 100,
                    "总扣分": 0,
                    "最低分限制": QUALITY_CONFIG["min_score"]
                },
                "优化操作": "无人工回复，无需优化"
            }
            saved_path = save_report_to_file(conversation_id, full_report)
            return True, conversation_id, 100, saved_path
        
        # 规则引擎检查
        try:
            logging.info(f"会话 {conversation_id}：开始规则引擎检查")
            rule_hits, _ = rule_engine_check(full_conversation, human_only)
            logging.info(f"会话 {conversation_id}：规则引擎检查完成，命中 {len(rule_hits)} 个规则")
        except Exception as e:
            logging.warning(f"规则引擎检查失败: {e}")
            rule_hits = []
        
        # LLM质量检查
        try:
            logging.info(f"会话 {conversation_id}：开始LLM质量检查")
            llm_result = llm_full_quality_check(human_only, rule_hits)
            logging.info(f"会话 {conversation_id}：LLM质量检查完成")
        except Exception as e:
            logging.error(f"LLM质量检查失败: {e}")
            # 使用降级方案，基于规则引擎结果和配置的扣分规则生成报告
            total_deduction = 0
            for item in rule_hits:
                error_code = item.get('error_code', '')
                # 查找对应错误的维度和扣分
                for dim_key, dim_info in QUALITY_CONFIG["dimensions"].items():
                    for deduction_item in dim_info["deduction_items"]:
                        if deduction_item.get("code") == error_code:
                            # 使用该维度的基础扣分值
                            total_deduction += abs(dim_info.get("base_deduction", 0))
                            break
                    else:
                        continue
                    break
            
            final_score = max(0, 100 - total_deduction)
            
            llm_result = {
                "final_score": final_score,
                "total_deduction": total_deduction,
                "hit_items": rule_hits,
                "dimension_results": {},
                "optimization_actions": "系统异常，基于规则引擎结果生成报告"
            }
        
        # 生成报告
        try:
            final_score = int(llm_result.get("final_score", 100))
            full_report = generate_full_report(conversation_id, rule_hits, llm_result)
        except Exception as e:
            logging.error(f"报告生成失败: {e}")
            # 生成简化报告
            full_report = {
                "conversation_id": conversation_id,
                "质检时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "质检核心结果": {
                    "初始满分": QUALITY_CONFIG["initial_score"],
                    "最终得分": 0,
                    "总扣分": 100,
                    "最低分限制": QUALITY_CONFIG["min_score"]
                },
                "优化操作": f"报告生成失败: {str(e)}"
            }
            final_score = 0
        
        # 保存报告
        try:
            saved_path = save_report_to_file(conversation_id, full_report)
        except Exception as e:
            logging.error(f"报告保存失败: {e}")
            saved_path = None
        
        # 保存到数据库
        try:
            result = {
                '会话ID': conversation_id,
                '最终得分': final_score,
                '总扣分': full_report['质检核心结果']['总扣分'],
                '扣分项编码': ';'.join([item.get('error_code', '') for item in full_report.get('命中扣分项明细', [])]),
                '优化建议': full_report.get('优化操作', ''),
                '报告文件': saved_path,
                '会话日期': session_date
            }
            db.save_quality_result(result)
        except Exception as e:
            logging.error(f"保存到数据库失败: {e}")
        
        return True, conversation_id, final_score, saved_path
        
    except Exception as e:
        logging.error(f"会话 {conversation_id} 处理失败: {e}")
        # 生成错误报告
        error_report = {
            "conversation_id": conversation_id,
            "质检时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "质检核心结果": {
                "初始满分": QUALITY_CONFIG["initial_score"],
                "最终得分": 0,
                "总扣分": 100,
                "最低分限制": QUALITY_CONFIG["min_score"]
            },
            "优化操作": f"系统异常: {str(e)}"
        }
        try:
            save_report_to_file(conversation_id, error_report)
        except Exception as save_error:
            logging.error(f"无法保存错误报告到文件: {save_error}")
        return False, conversation_id, str(e), None


def batch_process_chatlog_csv(csv_path):
    """批量处理聊天记录CSV文件"""
    try:
        df = pd.read_csv(csv_path)
        conversation_groups = df.groupby('会话ID')
        total_sessions = len(conversation_groups)
        logging.info(f"共识别 {total_sessions} 个独立会话，开始处理...")
        
        results = []
        for conv_id, group in conversation_groups:
            messages = []
            for _, row in group.iterrows():
                try:
                    msg_type = int(row['Type'])
                    content = str(row['Message']).strip()
                    messages.append({"type": msg_type, "content": content})
                except:
                    continue
            if messages:
                success, cid, score, report_path = process_single_conversation(str(conv_id), messages)
                if success:
                    results.append({'会话ID': cid, '最终得分': score, '报告文件': report_path})
        
        logging.info(f"处理完成，成功处理 {len(results)} 个会话")
        return results
    except Exception as e:
        logging.error(f"批量处理失败: {e}")
        return []


if __name__ == "__main__":
    setup_logging()
    init_output_folder()
    # 命令行批量处理（可选）
    # batch_process_chatlog_csv(CSV_FILE_PATH)
