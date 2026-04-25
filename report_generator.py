# report_generator.py
import json
import os
from typing import List, Dict
import pandas as pd
from config import QUALITY_CONFIG


def _get_severity_from_config(error_code: str) -> int:
    """从QUALITY_CONFIG中获取错误的严重程度"""
    for dim_key, dim_info in QUALITY_CONFIG["dimensions"].items():
        for item in dim_info["deduction_items"]:
            if item["code"] == error_code:
                return item.get("severity", 1)  # 默认严重程度为1
    return 1


def _get_severity_adjustment(error_code: str) -> int:
    """根据错误代码获取严重程度调整分"""
    severity = _get_severity_from_config(error_code)
    if severity >= 3:
        return 10  # 严重错误额外扣10分
    elif severity == 2:
        return 5   # 中等错误额外扣5分
    else:
        return 2   # 轻微错误额外扣2分


def generate_full_report(conversation_id: str, rule_hit_items: List[Dict], llm_result: Dict) -> Dict:
    """生成完整的质检报告"""
    all_dim_results = llm_result.get("dimension_results", {})
    filtered_dim_results = {}
    fake_keywords = ["未命中", "无错误", "合格", "正常"]
    for dim_key, dim_info in all_dim_results.items():
        if isinstance(dim_info, dict) and dim_info.get("result", "").lower() == "no":
            reason = str(dim_info.get("reason", ""))
            if not any(kw in reason for kw in fake_keywords) and reason:
                filtered_dim_results[dim_key] = dim_info
    
    # 多级评分机制：根据违规严重程度调整扣分
    hit_items = llm_result.get("hit_items", rule_hit_items)
    severity_adjustment = 0
    
    # 去重：确保每个错误只计算一次
    seen_error_codes = set()
    for item in hit_items:
        error_code = item.get('error_code', '')
        if error_code not in seen_error_codes:
            severity_adjustment += _get_severity_adjustment(error_code)
            seen_error_codes.add(error_code)
    
    # 计算最终得分：总扣分 = LLM基础扣分 + 严重等级额外扣分
    base_score = llm_result.get("final_score", 100)
    # 从100分开始计算，先扣除LLM基础扣分，再扣除严重程度调整分
    initial_score = QUALITY_CONFIG["initial_score"]
    base_deduction = initial_score - base_score
    total_deduction = base_deduction + severity_adjustment
    final_score = max(QUALITY_CONFIG["min_score"], initial_score - total_deduction)
    
    report = {
        "conversation_id": conversation_id,
        "质检时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "质检核心结果": {
            "初始满分": QUALITY_CONFIG["initial_score"],
            "最终得分": final_score,
            "总扣分": total_deduction,
            "最低分限制": QUALITY_CONFIG["min_score"],
            "严重程度调整": severity_adjustment
        }
    }
    if filtered_dim_results:
        report["不合格维度判定"] = filtered_dim_results
    if hit_items:
        report["命中扣分项明细"] = hit_items
    opt = llm_result.get("optimization_actions", "").strip()
    if opt and len(opt) > 5:
        report["优化操作"] = opt
    return report


def save_report_to_file(conversation_id: str, report: Dict) -> str:
    """将报告保存到文件"""
    import os
    from config import OUTPUT_FOLDER
    
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    file_path = os.path.join(OUTPUT_FOLDER, f"{conversation_id}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return file_path


def generate_summary_report(results: List[Dict]) -> pd.DataFrame:
    """生成汇总报告"""
    if not results:
        return pd.DataFrame()
    
    total_count = len(results)
    success_count = sum(1 for r in results if r.get('最终得分', 0) > 0)
    perfect_count = sum(1 for r in results if r.get('最终得分', 0) == 100)
    avg_score = sum(r.get('最终得分', 0) for r in results) / total_count if total_count > 0 else 0
    
    summary_data = {
        '总会话数': [total_count],
        '成功处理': [success_count],
        '满分通过': [perfect_count],
        '平均得分': [round(avg_score, 2)]
    }
    return pd.DataFrame(summary_data)


def generate_error_stats_report(results: List[Dict]) -> pd.DataFrame:
    """生成错误统计报告"""
    error_stats = {}
    for result in results:
        hit_codes = result.get('扣分项编码', '').split(';') if result.get('扣分项编码') else []
        for code in hit_codes:
            if code and code != 'PROCESS_ERROR' and code != 'SYSTEM_ERROR':
                if code not in error_stats:
                    error_stats[code] = {"count": 0, "suggestions": set()}
                error_stats[code]["count"] += 1
                if result.get('优化建议'):
                    error_stats[code]["suggestions"].add(result.get('优化建议'))
    
    error_list = []
    for code, data in error_stats.items():
        # 查找错误名称
        error_name = code
        for dim_key, dim_info in QUALITY_CONFIG["dimensions"].items():
            for item in dim_info["deduction_items"]:
                if item["code"] == code:
                    error_name = item["name"]
                    break
        
        suggestions = "；".join(data["suggestions"]) if data["suggestions"] else "无"
        error_list.append({
            '错误编码': code,
            '错误名称': error_name,
            '出现次数': data["count"],
            '占比': f"{data['count'] / len(results) * 100:.1f}%",
            '典型优化建议': suggestions
        })
    
    error_df = pd.DataFrame(error_list)
    if not error_df.empty:
        error_df = error_df.sort_values('出现次数', ascending=False)
    return error_df
