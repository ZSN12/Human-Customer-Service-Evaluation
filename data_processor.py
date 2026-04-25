# data_processor.py
import re
from typing import List, Dict
from config import TYPE_MAPPING, FILTER_TYPES, DESENSITIZATION_CONFIG


def desensitize_content(content: str) -> str:
    """脱敏处理敏感信息"""
    # 检查脱敏是否启用
    if not DESENSITIZATION_CONFIG.get("enabled", False):
        return content
    
    # 应用所有脱敏规则
    for rule_name, rule_config in DESENSITIZATION_CONFIG.get("rules", {}).items():
        pattern = rule_config.get("pattern")
        replacement = rule_config.get("replacement", "[SENSITIVE]")
        if pattern:
            content = re.sub(pattern, replacement, content)
    
    return content


def format_chat_for_llm(conversation_data: List[Dict]) -> str:
    """格式化聊天数据为LLM输入"""
    formatted_lines = []
    for msg in conversation_data:
        msg_type = msg.get('type', 0)
        type_desc = TYPE_MAPPING.get(msg_type, f"未知类型({msg_type})")
        content = msg.get('content', '').strip()
        # 脱敏处理
        content = desensitize_content(content)
        formatted_lines.append(f"[{type_desc}]: {content}")
    return "\n".join(formatted_lines)


def filter_conversation_data_for_llm(conversation_data: List[Dict]) -> List[Dict]:
    """智能过滤和截断消息，保留重要信息，减少Token消耗"""
    filtered = []
    
    # 保留最近的消息和关键消息
    important_msgs = []
    recent_msgs = conversation_data[-10:]  # 保留最近10条消息
    
    # 识别关键消息（包含问题、投诉、重要信息的消息）
    key_patterns = ['投诉', '差评', '问题', '怎么', '如何', '为什么', '怎么办', '能否', '可以', '是否', '价格', '退款', '退货']
    
    for msg in conversation_data:
        if msg.get('type') not in FILTER_TYPES:
            content = msg.get('content', '').strip()
            if any(pattern in content for pattern in key_patterns):
                important_msgs.append(msg)
    
    # 合并重要消息和最近消息，去重
    combined_msgs = important_msgs + recent_msgs
    seen_contents = set()
    unique_msgs = []
    
    for msg in combined_msgs:
        content = msg.get('content', '').strip()
        if content not in seen_contents:
            seen_contents.add(content)
            unique_msgs.append(msg)
    
    # 处理消息长度
    for msg in unique_msgs:
        if msg.get('type') not in FILTER_TYPES:
            content = msg.get('content', '').strip()
            # 根据消息类型调整截断长度
            if msg.get('type') == 1:  # 用户消息
                max_len = 300
            else:  # 人工回复
                max_len = 250
            
            if len(content) > max_len:
                # 保留开头和结尾的重要信息
                if len(content) > max_len * 2:
                    content = content[:max_len] + "..." + content[-max_len:]
                else:
                    content = content[:max_len] + "..."
            
            filtered.append({"type": msg['type'], "content": content})
    
    return filtered
