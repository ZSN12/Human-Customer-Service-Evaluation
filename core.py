# core.py
import time
import json
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Callable

from main import process_single_conversation
from config import settings, QUALITY_CONFIG
from report_generator import generate_summary_report, generate_error_stats_report
from task_manager import task_manager

def run_batch_analysis(
    session_df: pd.DataFrame,
    config,
    progress_callback: Optional[Callable] = None,
    log_callback: Optional[Callable] = None
) -> Tuple[List[Dict], pd.DataFrame, pd.DataFrame]:
    df = session_df.copy()
    if '日期' in df.columns and '时间' in df.columns:
        df['日期'] = df['日期'].astype(str)
        df['时间'] = df['时间'].astype(str)
        df['full_time'] = pd.to_datetime(df['日期'] + ' ' + df['时间'], errors='coerce')
        df = df.sort_values('full_time')
    elif 'full_time' in df.columns:
        df['full_time'] = pd.to_datetime(df['full_time'], errors='coerce')
        df = df.sort_values('full_time')

    conversation_groups = df.groupby('会话ID')
    total_sessions = len(conversation_groups)

    if log_callback:
        log_callback(f"共识别 {total_sessions} 个独立会话，开始并发处理...")

    conversation_list = []
    total_groups = len(conversation_groups)
    logging.info(f"开始构建会话列表，共 {total_groups} 个会话组")

    for i, (conv_id, group) in enumerate(conversation_groups):
        if i % 100 == 0:
            logging.info(f"处理会话组 {i}/{total_groups}")

        messages = []
        session_started = False

        for _, row in group.iterrows():
            try:
                msg_type = int(row['Type'])
                content = str(row['Message']).strip()
                messages.append({"type": msg_type, "content": content})
                session_started = True
            except Exception as e:
                logging.debug(f"跳过无效数据行: {e}")
                continue

        if messages and session_started:
            conversation_list.append((str(conv_id), messages, None))

    logging.info(f"会话列表构建完成，共 {len(conversation_list)} 个会话")

    results = []
    success_count = 0
    fail_count = 0
    perfect_count = 0
    total_score_sum = 0
    start_time = time.time()
    error_stats_dict = {}

    import psutil
    cpu_count = psutil.cpu_count()
    available_memory = psutil.virtual_memory().available / (1024 * 1024 * 1024)

    base_workers = min(cpu_count, config.max_workers)
    memory_factor = min(1.0, available_memory / 8.0)
    session_factor = min(1.0, len(conversation_list) / 100)

    optimal_workers = max(1, min(int(base_workers * memory_factor * (1 + session_factor)), config.max_workers))

    if log_callback:
        log_callback(f"动态调整并发数：{optimal_workers} (基于CPU: {cpu_count}, 内存: {available_memory:.1f}GB, 会话数: {len(conversation_list)})")

    max_workers = min(optimal_workers, 5)
    logging.info(f"启动线程池，并发数: {max_workers}")

    llm_failure_count = 0
    max_llm_failures = 10

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_conv = {executor.submit(process_single_conversation, cid, msgs, session_date): (cid, session_date) for cid, msgs, session_date in conversation_list}
        logging.info(f"提交了 {len(future_to_conv)} 个任务到线程池")

        for i, future in enumerate(as_completed(future_to_conv), 1):
            conv_id, session_date = future_to_conv[future]
            try:
                result_tuple = future.result()
                if result_tuple is None:
                    fail_count += 1
                    results.append({'会话ID': conv_id, '最终得分': 0, '扣分项编码': 'SYSTEM_ERROR', '优化建议': '任务返回为空', '报告文件': '', '会话日期': session_date})
                    llm_failure_count += 1
                else:
                    success, cid, score_or_error, report_path = result_tuple
                    if success:
                        success_count += 1
                        final_score = score_or_error
                        total_score_sum += final_score
                        
                        # 读取报告，收集错误统计
                        hit_codes = ''
                        optimization = ''
                        if report_path and report_path != '' and report_path:
                            try:
                                with open(report_path, 'r', encoding='utf-8') as f:
                                    report_data = json.load(f)
                                
                                final_score = report_data.get('质检核心结果', {}).get('最终得分', final_score)
                                hit_items = report_data.get('命中扣分项明细', [])
                                
                                # 收集扣分项
                                code_list = []
                                for item in hit_items:
                                    code = item.get('error_code', '')
                                    code_list.append(code)
                                    
                                    # 更新错误统计字典
                                    if code not in error_stats_dict:
                                        error_stats_dict[code] = {
                                            "name": item.get('error_name', code),
                                            "count": 0,
                                            "suggestions": set()
                                        }
                                    error_stats_dict[code]["count"] += 1
                                    sug = report_data.get('优化操作', '')
                                    if sug:
                                        error_stats_dict[code]["suggestions"].add(sug)
                                
                                hit_codes = ';'.join(code_list) if code_list else ''
                                optimization = report_data.get('优化操作', '')
                            except Exception as e:
                                logging.warning(f"读取报告失败: {e}")
                        
                        results.append({
                            '会话ID': conv_id, 
                            '最终得分': final_score, 
                            '扣分项编码': hit_codes, 
                            '优化建议': optimization, 
                            '报告文件': report_path, 
                            '会话日期': session_date
                        })
                        
                        if final_score == 100:
                            perfect_count += 1
                    else:
                        fail_count += 1
                        llm_failure_count += 1
                        results.append({'会话ID': conv_id, '最终得分': 0, '扣分项编码': 'PROCESS_ERROR', '优化建议': f'异常: {score_or_error}', '报告文件': '', '会话日期': session_date})
            except Exception as e:
                fail_count += 1
                llm_failure_count += 1
                results.append({'会话ID': conv_id, '最终得分': 0, '扣分项编码': 'SYSTEM_ERROR', '优化建议': str(e), '报告文件': '', '会话日期': session_date})
                logging.error(f"会话 {conv_id} 处理异常: {e}")

            current_progress = i
            elapsed = time.time() - start_time
            avg_time = elapsed / current_progress if current_progress else 0
            remaining = avg_time * (len(conversation_list) - current_progress)

            if progress_callback:
                try:
                    progress_callback(current_progress, len(conversation_list), elapsed, remaining)
                except Exception as e:
                    logging.error(f"进度回调失败: {e}")

            if llm_failure_count >= max_llm_failures:
                logging.error(f"LLM调用失败次数达到上限 ({max_llm_failures})，自动中断任务")
                if log_callback:
                    log_callback(f"⚠️ LLM调用失败次数过多，自动中断任务以保护账户")
                break

    avg_score = round(total_score_sum / success_count, 2) if success_count else 0
    min_score = min([r['最终得分'] for r in results], default=100)
    max_score = max([r['最终得分'] for r in results], default=100)
    summary_df = pd.DataFrame([{'总会话数': total_sessions, '成功处理': success_count, '满分通过': perfect_count, '有扣分项': success_count - perfect_count, '处理失败': fail_count, '平均得分': avg_score, '最低分': min_score, '最高分': max_score}])

    error_stats = []
    for code, data in error_stats_dict.items():
        sug_list = list(data["suggestions"])
        sug_text = "；".join(sug_list[:3]) if sug_list else "暂无统一建议"
        error_stats.append({"错误编码": code, "错误名称": data["name"], "出现次数": data["count"], "占比": f"{data['count'] / (success_count - perfect_count) * 100:.1f}%" if (success_count - perfect_count) > 0 else "0%", "典型优化建议": sug_text})
    if error_stats:
        error_stats_df = pd.DataFrame(error_stats).sort_values("出现次数", ascending=False)
    else:
        error_stats_df = pd.DataFrame(columns=["错误编码", "错误名称", "出现次数", "占比", "典型优化建议"])

    if log_callback:
        log_callback(f"处理完成：成功 {success_count}（满分 {perfect_count}），失败 {fail_count}，平均分 {avg_score}")
    return results, summary_df, error_stats_df


def run_batch_analysis_with_task(
    session_df: pd.DataFrame,
    config,
    progress_callback: Optional[Callable] = None,
    log_callback: Optional[Callable] = None
) -> str:
    """使用任务管理器运行批量分析"""
    def task_func(progress_callback=None, log_callback=None):
        def wrapped_progress_callback(completed, total, *args):
            if progress_callback:
                try:
                    progress_callback(completed, total)
                except Exception as e:
                    logging.error(f"进度回调失败: {e}")

        return run_batch_analysis(session_df, config, wrapped_progress_callback, log_callback)

    task_id = task_manager.create_task(task_func)
    return task_id
