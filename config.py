# config.py
import os
from dataclasses import dataclass

# 延迟导入数据库模块，避免循环导入
try:
    from database import db
except ImportError:
    db = None

# ==============================================
# 会话类型映射与过滤（用于 main.py）
# ==============================================
TYPE_MAPPING = {
    6: "系统提示(客户进入)",
    1: "客户提问",
    2: "AI回复",
    11: "会话结束标记",
    42: "转人工提示系统消息",
    18: "工单固定回复(AI生成)",
    10: "创建工单卡片",
    31: "AI状态变更",
    38: "会话产生工单需分配",
    5: "人工回复"
}

# 质检人工回复时过滤掉AI及系统消息
FILTER_TYPES = [6, 11, 31, 38, 10, 2, 18]

# ==============================================
# 质检维度与扣分项（完整）
# ==============================================
QUALITY_CONFIG = {
    "initial_score": 100,
    "min_score": 0,
    "dimensions": {
        "Dialogue_Logic": {
            "dimension_name": "对话逻辑合规性",
            "base_deduction": -40,
            "deduction_items": [
                {"code": "Answer_Irrelevant", "name": "答非所问", "desc": "客户问材质，客服回答物流，回复与用户问题主题完全不匹配", "severity": 2},
                {"code": "Ignore_User_Question", "name": "忽略客户问题", "desc": "客户问了多件事，客服只回答其中一件，遗漏核心问题", "severity": 2},
                {"code": "Contradict_Previous", "name": "前后矛盾", "desc": "客服前面说纯棉，后面说聚酯，同一会话内回复内容冲突", "severity": 2},
                {"code": "Repeat_Response", "name": "连续重复回复", "desc": "同一句话无意义连续回复3次及以上", "severity": 1},
                {"code": "Wrong_Context", "name": "回复错商品", "desc": "客户问A商品，客服回复B商品的信息", "severity": 2},
                {"code": "Misunderstand_Question", "name": "理解错误", "desc": "错误理解用户问题核心", "severity": 2},
                {"code": "Incomplete_Answer", "name": "回答不完整", "desc": "客户问退货流程，客服只说联系客服，未给出完整指引", "severity": 1},
                {"code": "Premature_Ending", "name": "过早结束对话", "desc": "客户还在提问咨询，客服直接结束对话", "severity": 1},
                {"code": "Complaint_Mention", "name": "用户提及投诉/差评", "desc": "用户在对话中明确提及「投诉」或「差评」关键词", "severity": 3}
            ]
        },
        "Fact_Correct": {
            "dimension_name": "商品/订单信息准确性",
            "base_deduction": -40,
            "deduction_items": [
                {"code": "Wrong_Product_Material", "name": "商品材质错误", "desc": "商品材质描述与实际信息不符", "severity": 2},
                {"code": "Wrong_Product_Size", "name": "尺码描述错误", "desc": "商品尺码/尺寸描述与实际信息不符", "severity": 2},
                {"code": "Wrong_Product_Color", "name": "颜色信息错误", "desc": "商品颜色描述与实际信息不符", "severity": 2},
                {"code": "Wrong_Product_Function", "name": "功能描述错误", "desc": "商品功能描述与实际信息不符", "severity": 2},
                {"code": "Wrong_Product_Spec", "name": "商品规格错误", "desc": "商品规格参数描述与实际信息不符", "severity": 2},
                {"code": "Wrong_Product_Usage", "name": "使用方法错误", "desc": "商品使用方法指导与官方说明不符", "severity": 2},
                {"code": "Wrong_Product_Compatibility", "name": "兼容性描述错误", "desc": "商品兼容性描述与实际信息不符", "severity": 2},
                {"code": "Wrong_Product_Stock", "name": "库存信息错误", "desc": "商品库存/现货信息描述与实际不符", "severity": 2},
                {"code": "Wrong_Product_Price", "name": "价格信息错误", "desc": "商品价格/优惠信息描述与实际不符", "severity": 3},
                {"code": "Wrong_Product_Promotion", "name": "活动信息错误", "desc": "商品促销活动描述与官方规则不符", "severity": 3},
                {"code": "Wrong_Order_Status", "name": "订单状态错误", "desc": "订单状态描述与系统实际状态不符", "severity": 2},
                {"code": "Wrong_Logistics_Status", "name": "物流状态错误", "desc": "物流状态描述与实际物流信息不符", "severity": 2},
                {"code": "Wrong_Delivery_Time", "name": "发货时间错误", "desc": "发货/到货时间承诺与平台规则不符", "severity": 2},
                {"code": "Wrong_Return_Policy", "name": "退货政策错误", "desc": "退货政策描述与平台规则不符", "severity": 3},
                {"code": "Wrong_Exchange_Policy", "name": "换货政策错误", "desc": "换货政策描述与平台规则不符", "severity": 3},
                {"code": "Wrong_Refund_Policy", "name": "退款政策错误", "desc": "退款政策描述与平台规则不符", "severity": 3},
                {"code": "Wrong_AfterSales_Process", "name": "售后流程错误", "desc": "售后流程指导与平台规则不符", "severity": 3}
            ]
        },
        "Policy_Compliance": {
            "dimension_name": "平台政策合规性",
            "base_deduction": -50,
            "deduction_items": [
                {"code": "Policy_Violation", "name": "承诺超出平台政策", "desc": "客服承诺的内容超出平台规则允许范围", "severity": 3},
                {"code": "Guarantee_Claim", "name": "保证类承诺", "desc": "违规做出绝对化保证承诺", "severity": 3},
                {"code": "Privacy_Leak", "name": "泄露地址或隐私", "desc": "泄露门牌号级详细地址、用户手机号等隐私信息", "severity": 3},
                {"code": "Bad_Attitude", "name": "服务态度差", "desc": "服务态度恶劣，敷衍、不耐烦", "severity": 2},
                {"code": "Rude_Language", "name": "不礼貌语言", "desc": "使用辱骂、嘲讽、不文明用语", "severity": 3},
                {"code": "Blame_User", "name": "指责客户", "desc": "将问题责任甩锅、指责客户", "severity": 2},
                {"code": "Encourage_Complaint", "name": "引导投诉", "desc": "主动引导客户向上级平台投诉", "severity": 3},
                {"code": "Sensitive_Content", "name": "敏感话题", "desc": "提及违规敏感话题", "severity": 3},
                {"code": "Unprofessional_Wording", "name": "不专业表达", "desc": "使用平台禁止的不专业/违规话术", "severity": 1}
            ]
        },
        "Service_Quality": {
            "dimension_name": "服务质量",
            "base_deduction": -20,
            "deduction_items": [
                {"code": "No_Solution_Provided", "name": "未提供解决方案", "desc": "用户提出问题，客服未给出任何可落地的解决方案", "severity": 2},
                {"code": "Weak_Explanation", "name": "解释不清", "desc": "问题解释模糊、逻辑混乱", "severity": 1},
                {"code": "Low_Service_Awareness", "name": "服务意识弱", "desc": "无主动服务意识，被动敷衍", "severity": 1},
                {"code": "Slow_Response", "name": "回复迟缓", "desc": "超长时间未回复用户消息", "severity": 1},
                {"code": "Template_Overuse", "name": "模板话术过多", "desc": "全程使用无意义模板话术", "severity": 1},
                {"code": "Lack_of_Empathy", "name": "缺乏同理心", "desc": "用户有负面情绪，无安抚共情", "severity": 1},
                {"code": "Fail_To_Handle_Complaint", "name": "投诉处理差", "desc": "用户投诉后未妥善跟进", "severity": 3},
                {"code": "Incomplete_Process_Guidance", "name": "流程指导不完整", "desc": "操作流程指导不完整", "severity": 1},
                {"code": "Self_Contradiction", "name": "客服前后表述矛盾", "desc": "客服在同一会话中对同一事实的表述前后不一致", "severity": 2},
                {"code": "Blind_Response_Without_Verification", "name": "未核实信息盲目回应", "desc": "客服未核实商品真实信息，仅凭猜测回应", "severity": 2},
                {"code": "Product_Description_Mismatch", "name": "商品描述与实际不符", "desc": "商品页面描述与实际商品不符，客服未及时纠正", "severity": 2},
                {"code": "Low_Verification_Efficiency", "name": "信息核实效率低", "desc": "用户反复质疑后，客服才核实真实信息", "severity": 1},
                {"code": "Insufficient_Fallback_Solution", "name": "运营失误兜底方案不足", "desc": "证实是运营端错误后，客服仅承认错误，未主动提出解决方案", "severity": 2},
                {"code": "Avoid_Responsibility", "name": "回避核心责任", "desc": "面对平台错误，客服未正面承认，反复推诿", "severity": 3},
                {"code": "No_Proactive_Correction", "name": "未主动纠正错误信息", "desc": "发现描述错误后，客服未主动告知用户并纠正", "severity": 1}
            ]
        },
        "Sales_Ability": {
            "dimension_name": "销售转化能力",
            "base_deduction": -10,
            "deduction_items": [
                {"code": "Missed_Sales_Opportunity", "name": "错失销售机会", "desc": "用户有明确购买意向，未跟进转化", "severity": 2},
                {"code": "No_Product_Recommendation", "name": "未推荐商品", "desc": "用户咨询商品，未主动推荐对应商品", "severity": 1},
                {"code": "Weak_Product_Explanation", "name": "商品介绍弱", "desc": "商品核心卖点介绍不清晰", "severity": 1},
                {"code": "No_Promotion_Introduction", "name": "未介绍活动", "desc": "未主动告知用户商品促销活动", "severity": 1},
                {"code": "No_Cross_Sell", "name": "未推荐搭配商品", "desc": "未主动推荐适配的搭配商品", "severity": 1},
                {"code": "No_Upsell", "name": "未推荐更高价商品", "desc": "未主动推荐性价比更高的升级款商品", "severity": 1},
                {"code": "Weak_Purchase_Guidance", "name": "未引导购买", "desc": "用户有意向，未引导下单", "severity": 1},
                {"code": "Premature_End_Sales", "name": "过早结束销售", "desc": "用户仍在咨询，提前结束销售对话", "severity": 2}
            ]
        }
    }
}

# ==============================================
# 程序运行配置
# ==============================================
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "./output")

@dataclass
class Settings:
    max_row_limit: int = 200000
    max_row_warning: int = 50000
    chunk_size: int = 50000
    max_workers: int = int(os.getenv("MAX_WORKERS", 5))
    default_report_path: str = "质检报告.xlsx"
    prompt_version: str = "v2.0 (人工客服质检)"

# 脱敏配置
DESENSITIZATION_CONFIG = {
    "enabled": True,
    "rules": {
        "phone": {
            "pattern": r'1[3-9]\d{9}',
            "replacement": "[PHONE]"
        },
        "id_card": {
            "pattern": r'[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]',
            "replacement": "[ID_CARD]"
        },
        "order_id": {
            "pattern": r'(订单号|order|Order)[:：]?\s*[A-Za-z0-9-]{8,20}',
            "replacement": "[ORDER_ID]"
        },
        "address": {
            "pattern": r'[省市县区]\s*[\u4e00-\u9fa50-9]+路\s*[\u4e00-\u9fa50-9]+号',
            "replacement": "[ADDRESS]"
        },
        "bank_card": {
            "pattern": r'\d{16,19}',
            "replacement": "[BANK_CARD]"
        }
    }
}

settings = Settings()

# 从数据库加载质检配置
def load_quality_config():
    """从数据库加载质检配置"""
    global QUALITY_CONFIG
    if db:
        try:
            db_config = db.get_quality_config()
            if db_config:
                QUALITY_CONFIG = db_config
                print("已从数据库加载质检配置")
        except Exception as e:
            print(f"从数据库加载质检配置失败: {e}")

# 保存质检配置到数据库
def save_quality_config():
    """保存质检配置到数据库"""
    if db:
        try:
            db.save_quality_config(QUALITY_CONFIG)
            print("已保存质检配置到数据库")
        except Exception as e:
            print(f"保存质检配置到数据库失败: {e}")

# 初始化时加载配置
load_quality_config()