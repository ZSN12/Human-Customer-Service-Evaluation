# rule_engine.py
import re
import json
from typing import List, Dict, Tuple, Callable
from config import QUALITY_CONFIG
from database import db


class RuleEngine:
    """规则引擎"""
    
    def __init__(self):
        self.rules = []
        self._load_rules()
    
    def _load_rules(self):
        """从数据库加载规则"""
        # 从数据库获取激活的规则
        db_rules = db.get_rules(is_active=True)
        
        if db_rules:
            # 使用数据库规则
            for rule_data in db_rules:
                rule = {
                    'id': rule_data['id'],
                    'name': rule_data['name'],
                    'dimension': rule_data['dimension'],
                    'error_code': rule_data['error_code'],
                    'rule_type': rule_data['rule_type'],
                    'params': json.loads(rule_data['params']) if rule_data['params'] else {},
                    'check_func': self._get_rule_check_func(rule_data['rule_type'])
                }
                self.rules.append(rule)
        else:
            # 使用默认规则
            self._register_default_rules()
    
    def _register_default_rules(self):
        """注册默认规则"""
        default_rules = [
            {
                'name': '投诉/差评检测',
                'dimension': 'Dialogue_Logic',
                'error_code': 'Complaint_Mention',
                'rule_type': 'keyword',
                'params': {'keywords': ['投诉', '差评'], 'message_type': 'user'}
            },
            {
                'name': '隐私信息泄露检测',
                'dimension': 'Policy_Compliance',
                'error_code': 'Privacy_Leak',
                'rule_type': 'regex',
                'params': {'pattern': r'\d+[号弄单元室栋座楼层]|\d+巷\d+|\d+路\d+号', 'message_type': 'human'}
            },
            {
                'name': '连续重复回复检测',
                'dimension': 'Dialogue_Logic',
                'error_code': 'Repeat_Response',
                'rule_type': 'repeat',
                'params': {'min_repeats': 3}
            },
            {
                'name': '敏感词检测',
                'dimension': 'Policy_Compliance',
                'error_code': 'Rude_Language',
                'rule_type': 'keyword',
                'params': {'keywords': ['傻逼', '滚', '垃圾', '妈的', '操你', '混蛋', '白痴', '蠢货'], 'message_type': 'human'}
            },
            {
                'name': '服务态度检测',
                'dimension': 'Policy_Compliance',
                'error_code': 'Bad_Attitude',
                'rule_type': 'keyword',
                'params': {'keywords': ['不行', '办不到', '没办法', '不关我的事', '你自己看', '随便你'], 'message_type': 'human'}
            },
            {
                'name': '模板话术过多检测',
                'dimension': 'Service_Quality',
                'error_code': 'Template_Overuse',
                'rule_type': 'template',
                'params': {'templates': ['您好', '请问', '感谢您的咨询', '祝您生活愉快', '有什么可以帮助您的'], 'min_count': 3, 'max_messages': 5}
            },
            {
                'name': '未提供解决方案检测',
                'dimension': 'Service_Quality',
                'error_code': 'No_Solution_Provided',
                'rule_type': 'solution',
                'params': {
                    'question_patterns': ['怎么', '如何', '为什么', '怎么办', '能否', '可以', '是否'],
                    'solution_patterns': ['建议', '可以', '您可以', '请', '按照', '步骤', '方法', '流程']
                }
            }
        ]
        
        for rule_data in default_rules:
            rule = {
                'name': rule_data['name'],
                'dimension': rule_data['dimension'],
                'error_code': rule_data['error_code'],
                'rule_type': rule_data['rule_type'],
                'params': rule_data['params'],
                'check_func': self._get_rule_check_func(rule_data['rule_type'])
            }
            self.rules.append(rule)
    
    def _get_rule_check_func(self, rule_type: str) -> Callable:
        """获取规则检查函数"""
        rule_functions = {
            'keyword': self._check_keyword,
            'regex': self._check_regex,
            'repeat': self._check_repeat,
            'template': self._check_template,
            'solution': self._check_solution
        }
        return rule_functions.get(rule_type, self._check_default)
    
    def _check_keyword(self, full_conversation: List[Dict], human_only_conversation: List[Dict], params: Dict) -> Tuple[bool, str]:
        """关键词检测"""
        keywords = params.get('keywords', [])
        message_type = params.get('message_type', 'human')
        
        if message_type == 'user':
            messages = [msg for msg in full_conversation if msg.get('type') == 1]
        else:
            messages = [msg for msg in full_conversation if msg.get('type') == 5]
        
        all_content = "\n".join([str(msg.get('content', '')) for msg in messages])
        
        for keyword in keywords:
            if keyword in all_content:
                return True, f"检测到关键词: {keyword} - {all_content[:100]}"
        return False, ""
    
    def _check_regex(self, full_conversation: List[Dict], human_only_conversation: List[Dict], params: Dict) -> Tuple[bool, str]:
        """正则表达式检测"""
        pattern = params.get('pattern', '')
        message_type = params.get('message_type', 'human')
        
        if message_type == 'user':
            messages = [msg for msg in full_conversation if msg.get('type') == 1]
        else:
            messages = [msg for msg in full_conversation if msg.get('type') == 5]
        
        all_content = "\n".join([str(msg.get('content', '')) for msg in messages])
        
        if re.search(pattern, all_content):
            return True, f"正则表达式匹配: {pattern}"
        return False, ""
    
    def _check_repeat(self, full_conversation: List[Dict], human_only_conversation: List[Dict], params: Dict) -> Tuple[bool, str]:
        """连续重复回复检测（基于会话全局分析）"""
        min_repeats = params.get('min_repeats', 3)
        
        human_messages = [msg for msg in full_conversation if msg.get('type') == 5]
        reply_contents = [str(msg.get('content', '')).strip() for msg in human_messages]
        
        # 滑动窗口检测连续重复
        for i in range(len(reply_contents) - min_repeats + 1):
            window = reply_contents[i:i+min_repeats]
            if len(set(window)) == 1 and window[0] != "":
                return True, f"连续重复回复: {window[0][:100]}"
        return False, ""
    
    def _check_template(self, full_conversation: List[Dict], human_only_conversation: List[Dict], params: Dict) -> Tuple[bool, str]:
        """模板话术过多检测"""
        templates = params.get('templates', [])
        min_count = params.get('min_count', 3)
        max_messages = params.get('max_messages', 5)
        
        human_messages = [msg for msg in full_conversation if msg.get('type') == 5]
        all_content = "\n".join([str(msg.get('content', '')) for msg in human_messages])
        
        template_count = sum(1 for template in templates if template in all_content)
        if template_count >= min_count and len(human_messages) <= max_messages:
            return True, "模板话术过多，缺乏实质内容"
        return False, ""
    
    def _check_solution(self, full_conversation: List[Dict], human_only_conversation: List[Dict], params: Dict) -> Tuple[bool, str]:
        """未提供解决方案检测（基于会话全局分析）"""
        question_patterns = params.get('question_patterns', [])
        solution_patterns = params.get('solution_patterns', [])
        
        # 按时间顺序分析所有消息
        for i, msg in enumerate(full_conversation):
            msg_type = msg.get('type')
            content = msg.get('content', '')
            
            # 检查是否是用户问题
            if msg_type == 1 and any(pattern in content for pattern in question_patterns):
                # 查找该问题之后的客服回复
                has_solution = False
                for j in range(i + 1, len(full_conversation)):
                    next_msg = full_conversation[j]
                    next_msg_type = next_msg.get('type')
                    next_content = next_msg.get('content', '')
                    
                    # 只检查客服回复
                    if next_msg_type == 5:
                        # 检查客服回复是否包含解决方案
                        if any(pattern in next_content for pattern in solution_patterns):
                            has_solution = True
                            break
                        # 如果遇到新的用户问题，停止查找
                    elif next_msg_type == 1:
                        break
                
                if not has_solution:
                    return True, f"未提供具体解决方案，用户问题：{content[:100]}"
        return False, ""
    
    def _check_default(self, full_conversation: List[Dict], human_only_conversation: List[Dict], params: Dict) -> Tuple[bool, str]:
        """默认检查函数"""
        return False, ""
    
    def check(self, full_conversation: List[Dict], human_only_conversation: List[Dict]) -> Tuple[List[Dict], int]:
        """执行规则检查"""
        hit_items = []
        total_deduction = 0
        
        # 用于记录已扣除基础分的维度
        deducted_dimensions = set()
        
        for rule in self.rules:
            # 获取规则配置
            dimension = rule['dimension']
            error_code = rule['error_code']
            check_func = rule['check_func']
            params = rule.get('params', {})
            
            # 执行检查
            is_hit, hit_reason = check_func(full_conversation, human_only_conversation, params)
            if is_hit:
                # 查找错误项配置
                dim_config = QUALITY_CONFIG["dimensions"].get(dimension, {})
                deduction_items = dim_config.get("deduction_items", [])
                item = next((x for x in deduction_items if x["code"] == error_code), None)
                
                if item:
                    hit_items.append({**item, "dimension": dimension, "hit_reason": hit_reason})
                    # 只对每个维度扣除一次基础分
                    if dimension not in deducted_dimensions:
                        total_deduction += dim_config.get("base_deduction", 0)
                        deducted_dimensions.add(dimension)
        
        return hit_items, total_deduction


# 全局规则引擎实例
rule_engine = RuleEngine()


def rule_engine_check(full_conversation: List[Dict], human_only_conversation: List[Dict]) -> Tuple[List[Dict], int]:
    """规则引擎检查"""
    return rule_engine.check(full_conversation, human_only_conversation)


def reload_rules():
    """重新加载规则"""
    global rule_engine
    rule_engine = RuleEngine()
    return True
