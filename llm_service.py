# llm_service.py
import json
import logging
from typing import Dict, Optional
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, APITimeoutError
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import os

# 费用统计
class CostManager:
    def __init__(self):
        self.total_tokens = 0
        self.total_cost = 0
        # 假设的价格（美元/1000 tokens）
        self.input_price_per_1k = 0.0015
        self.output_price_per_1k = 0.002
    
    def add_usage(self, input_tokens: int, output_tokens: int):
        """添加使用量并计算费用"""
        self.total_tokens += input_tokens + output_tokens
        cost = (input_tokens * self.input_price_per_1k + output_tokens * self.output_price_per_1k) / 1000
        self.total_cost += cost
        return cost
    
    def get_total_cost(self) -> float:
        """获取总费用"""
        return self.total_cost
    
    def get_total_tokens(self) -> int:
        """获取总tokens"""
        return self.total_tokens
    
    def reset(self):
        """重置费用统计"""
        self.total_tokens = 0
        self.total_cost = 0

# 全局费用管理器（用于默认情况）
cost_manager = CostManager()

# 重置费用管理器的函数
def reset_cost_manager():
    """重置费用管理器的计数器"""
    global cost_manager
    cost_manager.reset()
    return cost_manager

# 从会话状态获取或创建费用管理器
def get_cost_manager():
    """从会话状态获取或创建费用管理器"""
    import streamlit as st
    global cost_manager
    if 'cost_manager' not in st.session_state:
        st.session_state.cost_manager = cost_manager
    return st.session_state.cost_manager

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 性能优化：减少重试次数和超时时间
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", 2))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 30))
LLM_RETRY_MIN_WAIT = 1
LLM_RETRY_MAX_WAIT = 4
ENABLE_LLM_VERIFICATION = os.getenv("ENABLE_LLM_VERIFICATION", "true").lower() == "true"

_openai_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """获取OpenAI客户端实例"""
    global _openai_client
    if _openai_client is None:
        if not DEEPSEEK_API_KEY:
            raise ValueError("未配置 DEEPSEEK_API_KEY")
        _openai_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _openai_client


def get_fallback_llm_result(error_msg: str) -> Dict:
    """获取LLM调用失败时的降级结果"""
    return {
        "final_score": 0, "total_deduction": 100,
        "hit_items": [{"dimension": "System", "dimension_name": "系统异常", "error_code": "LLM_Call_Failed", "error_name": "LLM调用失败", "deduction_score": 100, "hit_reason": f"错误: {error_msg[:200]}"}],
        "dimension_results": {"System": {"result": "no", "reason": "LLM服务不可用"}},
        "optimization_actions": "检查API密钥或网络"
    }


@retry(stop=stop_after_attempt(LLM_MAX_RETRIES), 
       wait=wait_exponential(multiplier=1, min=LLM_RETRY_MIN_WAIT, max=LLM_RETRY_MAX_WAIT), 
       retry=retry_if_exception_type((APIConnectionError, RateLimitError, APITimeoutError)), 
       before_sleep=before_sleep_log(logging, logging.WARNING), 
       reraise=True)
def _call_deepseek_api(system_prompt: str, user_input: str) -> Dict:
    """调用DeepSeek API"""
    client = get_openai_client()
    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}],
            response_format={"type": "json_object"},
            temperature=0.1,
            stream=False,
            timeout=LLM_TIMEOUT
        )
        
        # 验证响应格式
        if not response or not response.choices or len(response.choices) == 0:
            raise ValueError("LLM响应格式错误：无有效响应内容")
        
        # 统计费用
        if hasattr(response, 'usage'):
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            # 使用全局费用管理器（在后台任务中也能正常工作）
            global cost_manager
            cost = cost_manager.add_usage(input_tokens, output_tokens)
            logging.info(f"LLM调用费用: ${cost:.4f} (输入: {input_tokens} tokens, 输出: {output_tokens} tokens)")
        
        content = response.choices[0].message.content.strip()
        if not content:
            raise ValueError("LLM响应为空")
        
        # 解析JSON响应
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logging.error(f"LLM响应JSON解析失败: {e}")
            logging.error(f"原始响应: {content[:500]}")
            raise ValueError(f"LLM响应不是有效的JSON格式: {str(e)}")
            
    except Exception as e:
        logging.error(f"LLM API调用异常: {str(e)}")
        raise


def deepseek_chat_completion(system_prompt: str, user_input: str) -> Dict:
    """DeepSeek聊天完成"""
    if not ENABLE_LLM_VERIFICATION:
        logging.info("LLM验证已禁用，返回默认结果")
        return {
            "final_score": 85,
            "total_deduction": 15,
            "hit_items": [],
            "dimension_results": {},
            "optimization_actions": "LLM验证已禁用，使用默认评分"
        }
    
    try:
        logging.info("开始调用DeepSeek API")
        return _call_deepseek_api(system_prompt, user_input)
    except APIConnectionError as e:
        logging.error(f"LLM连接失败: {e}")
        return get_fallback_llm_result(f"网络连接错误: {str(e)}")
    except RateLimitError as e:
        logging.error(f"LLM速率限制: {e}")
        return get_fallback_llm_result(f"API速率限制，请稍后再试")
    except APITimeoutError as e:
        logging.error(f"LLM超时: {e}")
        return get_fallback_llm_result(f"API响应超时")
    except ValueError as e:
        logging.error(f"LLM响应错误: {e}")
        return get_fallback_llm_result(f"响应格式错误: {str(e)}")
    except Exception as e:
        logging.error(f"LLM调用失败: {e}")
        return get_fallback_llm_result(f"系统错误: {str(e)}")


def build_llm_quality_prompt() -> str:
    """构建LLM质检提示词"""
    from config import QUALITY_CONFIG
    
    prompt_parts = [
        "你是专业的电商人工客服质检专家，拥有丰富的客服质量评估经验。",
        "你的任务是严格按照给定的规则和扣分标准，对客服对话进行全维度质检。",
        "\n【核心原则】：",
        "1. 初始满分100分，按命中扣分项扣分，最低0分。",
        "2. 每个维度命中任意错误项，扣除该维度基础分，同一维度不重复扣分。",
        "3. 仅针对人工客服（type=5）的回复进行质检，忽略其他类型的消息。",
        "4. 必须保留规则引擎已命中的违规项，并补充其他未命中的违规项。",
        "5. 分析时要结合上下文，理解对话的完整语境。",
        "6. 评分要客观公正，扣分要有明确的依据。",
        "\n【扣分标准明细】："
    ]
    for dim_key, dim_info in QUALITY_CONFIG["dimensions"].items():
        prompt_parts.append(f"\n维度：{dim_info['dimension_name']}（编码：{dim_key}，基础扣分：{dim_info['base_deduction']}分）")
        for item in dim_info["deduction_items"]:
            prompt_parts.append(f"- 编码：{item['code']}，名称：{item['name']}，说明：{item['desc']}")
    prompt_parts.append("\n【分析步骤】：")
    prompt_parts.append("1. 仔细阅读对话内容，理解用户问题和客服回复。")
    prompt_parts.append("2. 检查规则引擎已命中的违规项，确保保留这些项。")
    prompt_parts.append("3. 分析客服回复是否符合各维度的要求。")
    prompt_parts.append("4. 识别所有违规行为，计算总扣分和最终得分。")
    prompt_parts.append("5. 生成详细的优化建议，帮助客服改进服务质量。")
    prompt_parts.append("\n【输出要求】：严格输出JSON格式，确保格式正确无误。")
    prompt_parts.append("""
{
    "final_score": "最终得分，整数",
    "total_deduction": "总扣分，整数",
    "hit_items": [{"dimension": "维度编码", "dimension_name": "维度名称", "error_code": "错误编码", "error_name": "错误名称", "deduction_score": "扣分数", "hit_reason": "命中原因", "evidence_quote": "导致扣分的具体句子"}],
    "dimension_results": {"维度编码": {"result": "no", "reason": "不合格原因"}},
    "optimization_actions": "详细的优化建议，至少3条具体措施"
}
    """)
    return "\n".join(prompt_parts)


def generate_executive_summary(summary_data: dict, error_stats: list) -> str:
    """生成专家诊断建议（Executive Summary）"""
    if not ENABLE_LLM_VERIFICATION:
        logging.info("LLM验证已禁用，返回默认诊断报告")
        return "【核心问题诊断】\n- 系统分析已禁用，无法提供详细诊断\n\n【团队风险预警】\n- 缺少AI分析，风险评估受限\n\n【管理优化建议】\n- 启用LLM验证以获得更深入的分析"    
    
    # 构建系统提示词
    system_prompt = """
你是一位资深的客服质量管理专家，拥有10年以上的客服团队管理和质量优化经验。你的任务是基于批量质检的统计数据，生成一份面向管理层的专业诊断报告。

报告要求：
1. 语言专业、简洁，具备管理深度
2. 字数控制在300字左右
3. 结构清晰，包含以下三个部分：
   - 核心问题诊断：基于统计数据，识别客服团队的主要问题
   - 团队风险预警：分析潜在的业务风险和管理隐患
   - 管理优化建议：提供具体、可执行的改进措施

请结合数据，给出有洞察力的分析和建议。
"""
    
    # 准备用户输入数据
    user_input = f"""
【质检统计数据】
- 总会话数：{summary_data.get('总会话数', 0)}
- 平均得分：{summary_data.get('平均得分', 0)}
- 合格率：{summary_data.get('合格率', 0)}%
- 满分率：{summary_data.get('满分率', 0)}%

【Top 3 高频错误】
"""
    
    # 添加Top 3错误
    for i, error in enumerate(error_stats[:3], 1):
        error_name = error.get('错误名称', error.get('错误编码', '未知错误'))
        count = error.get('出现次数', 0)
        percentage = error.get('占比', '0%')
        user_input += f"{i}. {error_name}：{count}次（{percentage}）\n"
    
    try:
        logging.info("开始生成专家诊断建议")
        
        # 调用LLM
        client = get_openai_client()
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.2,
            stream=False,
            timeout=LLM_TIMEOUT
        )
        
        # 统计费用
        if hasattr(response, 'usage'):
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            global cost_manager
            cost = cost_manager.add_usage(input_tokens, output_tokens)
            logging.info(f"专家诊断建议生成费用: ${cost:.4f}")
        
        content = response.choices[0].message.content.strip()
        return content
        
    except Exception as e:
        logging.error(f"生成专家诊断建议失败: {e}")
        # 返回默认诊断报告
        return """
【核心问题诊断】
- 数据分析系统暂时不可用
- 基于现有数据，客服团队整体表现需要进一步评估

【团队风险预警】
- 缺少详细的问题分析，无法准确识别风险点
- 管理决策可能缺乏数据支持

【管理优化建议】
- 检查系统连接和API配置
- 确保数据收集的完整性和准确性
- 建立定期的质量分析机制
"""

