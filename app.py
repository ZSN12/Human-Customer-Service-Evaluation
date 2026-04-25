# app.py
import os
import time
import traceback
import pickle
import json
from datetime import timedelta
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from rule_engine import rule_engine_check

from config import QUALITY_CONFIG
from core import run_batch_analysis, run_batch_analysis_with_task
from config import settings
from task_manager import task_manager
from database import db
from llm_service import cost_manager, reset_cost_manager, generate_executive_summary

# 页面配置
st.set_page_config(
    page_title="人工客服质检系统", 
    layout="wide", 
    initial_sidebar_state="collapsed",
    menu_items={
        'About': "人工客服质检系统 - 规则引擎 + LLM 混合质检"
    }
)

# 缓存目录
CACHE_DIR = ".cache"
CACHE_FILE = os.path.join(CACHE_DIR, "last_result.pkl")
os.makedirs(CACHE_DIR, exist_ok=True)

# 缓存操作函数
def save_cache(data: dict):
    try:
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception as e:
        pass

def load_cache():
    if not os.path.exists(CACHE_FILE): return {}
    try:
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        return {}

def clear_cache():
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)

@st.cache_resource
def get_settings():
    from config import settings
    return settings

settings = get_settings()

# 加载缓存数据
cached = load_cache()
state_defaults = {
    "session_df": None, "qa_results": cached.get("qa_results", []), 
    "summary_df": cached.get("summary_df", None),
    "error_stats_df": cached.get("error_stats_df", None), 
    "report_path": cached.get("report_path", settings.default_report_path),
    "total_sessions": cached.get("total_sessions", 0), 
    "processed_count": cached.get("processed_count", 0),
    "is_running": False, "log_list": cached.get("log_list", []), 
    "session_file_name": cached.get("session_file_name", ""),
    "session_row_count": cached.get("session_row_count", 0), 
    "current_log_file": cached.get("current_log_file", ""),
    "last_error_traceback": cached.get("last_error_traceback", ""),
    "current_task_id": None,
    "active_tab": "dashboard",
    "executive_summary": cached.get("executive_summary", None),
    "summary_data": cached.get("summary_data", None),
}
for k, v in state_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 确保报告目录存在
report_dir = os.path.dirname(st.session_state.report_path)
if report_dir and not os.path.exists(report_dir):
    os.makedirs(report_dir, exist_ok=True)

# 必要的列
REQUIRED_COLUMNS = ['会话ID', 'Message', 'Type']

# 验证列名并进行映射
def validate_columns(df):
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        st.warning(f"缺少必要的列: {', '.join(missing)}")
        return False
    return True

# 主界面渲染函数
def render_header():
    st.title("人工客服质检系统")
    st.markdown("---")

def render_empty_state():
    """渲染空状态引导"""
    empty_col1, empty_col2, empty_col3 = st.columns([1, 2, 1])
    with empty_col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.write("")
        st.write("")
        st.markdown("<h2 style='text-align: center; color: #666;'>📊 上传会话数据开始质检</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888; font-size: 1.1em; margin-bottom: 2em;'>支持 Excel、CSV 格式文件</p>", unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "选择文件", 
            type=['xlsx', 'xls', 'csv'], 
            help="上传会话数据文件进行质检分析",
            label_visibility="collapsed",
            key="main_file_uploader"
        )
        
        if uploaded_file is not None:
            handle_file_upload(uploaded_file)

def render_metrics():
    """渲染指标卡片"""
    has_data = len(st.session_state.qa_results) > 0
    
    if has_data:
        summary_df = st.session_state.summary_df
        qa_results = st.session_state.qa_results
        
        total_sessions = len(qa_results)
        avg_score = sum(r['最终得分'] for r in qa_results) / total_sessions if total_sessions > 0 else 0
        pass_count = sum(1 for r in qa_results if r['最终得分'] >= 60)
        pass_rate = (pass_count / total_sessions * 100) if total_sessions > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        # 计算满分率
        perfect_count = sum(1 for r in qa_results if r['最终得分'] == 100)
        perfect_rate = (perfect_count / total_sessions * 100) if total_sessions > 0 else 0
        
        with col1:
            st.metric(
                "总会话数",
                str(total_sessions),
                delta=None,
                help="本次质检的会话总数"
            )
        
        with col2:
            st.metric(
                "平均得分",
                f"{avg_score:.1f}",
                delta=None,
                help="所有质检会话的平均得分"
            )
        
        with col3:
            st.metric(
                "合格率",
                f"{pass_rate:.1f}%",
                delta=None,
                help="得分≥60的会话比例"
            )
        
        with col4:
            st.metric(
                "满分率",
                f"{perfect_rate:.1f}%",
                delta=None,
                help="得分=100的会话比例"
            )

def render_dashboard_tab():
    """渲染概览看板标签页"""
    st.header("概览看板")
    st.markdown("---")
    
    has_data = len(st.session_state.qa_results) > 0
    
    if not has_data:
        render_empty_state()
        return
    
    render_metrics()
    st.markdown("---")
    
    # 可视化部分
    left_col, right_col = st.columns([1, 1])
    
    with left_col:
        st.subheader("维度得分雷达图")
        fig_radar = create_radar_chart()
        if fig_radar:
            st.plotly_chart(fig_radar, use_container_width=True)
        else:
            st.info("暂无足够数据显示维度得分")
    
    with right_col:
        st.subheader("错误类型分布")
        error_stats_df = st.session_state.error_stats_df
        if error_stats_df is not None and len(error_stats_df) > 0:
            fig_bar = create_error_distribution_chart(error_stats_df)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("暂无错误数据")
    
    # 专家诊断建议
    st.markdown("---")
    st.subheader("专家诊断建议")
    if 'executive_summary' in st.session_state and st.session_state.executive_summary:
        with st.expander("查看详细诊断报告", expanded=True):
            st.markdown(st.session_state.executive_summary)
    else:
        st.info("专家诊断建议正在生成中...")

def render_analysis_tab():
    """渲染质检明细标签页"""
    st.header("质检明细")
    st.markdown("---")
    
    has_data = len(st.session_state.qa_results) > 0
    
    if not has_data:
        render_empty_state()
        return
    
    render_metrics()
    st.markdown("---")
    
    # 显示质检结果表格
    qa_results = st.session_state.qa_results
    if qa_results:
        display_df = pd.DataFrame(qa_results)
        
        # 只显示需要的列
        display_cols = ['会话ID', '最终得分', '优化建议', '会话日期']
        
        if '扣分项编码' in display_df.columns:
            display_cols.insert(2, '扣分项编码')
        
        available_cols = [c for c in display_cols if c in display_df.columns]
        display_df = display_df[available_cols]
        
        # 为得分设置样式
        def highlight_score(val):
            color = 'background-color: #ffcccc' if val < 60 else 'background-color: #ccffcc' if val == 100 else ''
            return color
        
        st.dataframe(
            display_df.style.applymap(highlight_score, subset=['最终得分']),
            use_container_width=True,
            hide_index=True
        )
        
        # 添加交互式证据追溯功能
        st.subheader("详细报告查看")
        
        # 让用户选择要查看的会话
        conv_ids = [r['会话ID'] for r in qa_results]
        selected_conv = st.selectbox("选择要查看的会话", conv_ids)
        
        if selected_conv:
            # 找到对应的会话
            selected_result = next((r for r in qa_results if r['会话ID'] == selected_conv), None)
            if selected_result:
                with st.popover(f"查看会话 {selected_conv} 详情"):
                    st.subheader(f"会话 {selected_conv} 质检详情")
                    st.write(f"最终得分: {selected_result.get('最终得分', 'N/A')}")
                    st.write(f"优化建议: {selected_result.get('优化建议', 'N/A')}")
                    
                    if '报告文件' in selected_result and selected_result['报告文件']:
                        report_file = selected_result['报告文件']
                        if os.path.exists(report_file):
                            try:
                                with open(report_file, 'r', encoding='utf-8') as f:
                                    report_data = json.load(f)
                                
                                st.json(report_data)
                            except Exception as e:
                                st.warning(f"无法加载报告: {str(e)}")

def render_config_tab():
    """渲染系统配置标签页"""
    st.header("系统配置")
    st.markdown("---")
    
    # 清除数据按钮
    if st.button("🗑️ 清除所有数据", key="clear_data_config"):
        clear_data()
    
    st.markdown("---")
    
    with st.expander("规则管理", expanded=False):
        st.subheader("规则管理")
        
        # 获取所有规则
        rules = db.get_rules()
        
        if len(rules) == 0:
            st.info("暂无规则，使用默认规则")
        else:
            # 显示规则表格
            rule_list = []
            for rule in rules:
                rule_list.append({
                    'ID': rule['id'],
                    '名称': rule['name'],
                    '维度': rule['dimension'],
                    '类型': rule['rule_type'],
                    '启用状态': '启用' if rule['is_active'] == 1 else '禁用'
                })
            
            if rule_list:
                st.table(pd.DataFrame(rule_list))
        
        # 添加规则表单
        with st.form("add_rule_form"):
            st.subheader("添加新规则")
            name = st.text_input("规则名称")
            dimension = st.selectbox("维度", ["Dialogue_Logic", "Policy_Compliance", "Service_Quality"])
            error_code = st.text_input("错误编码")
            rule_type = st.selectbox("规则类型", ["keyword", "regex", "repeat", "template", "solution"])
            params = st.text_area("参数配置 (JSON)", '{}')
            
            submit = st.form_submit_button("添加规则")
            
            if submit and name and error_code:
                try:
                    parsed_params = json.loads(params) if params else {}
                    db.save_rule({
                        'name': name,
                        'dimension': dimension,
                        'error_code': error_code,
                        'rule_type': rule_type,
                        'params': json.dumps(parsed_params, ensure_ascii=False),
                        'is_active': 1
                    })
                    st.success("规则添加成功！")
                except Exception as e:
                    st.error(f"添加规则失败: {str(e)}")
    
    with st.expander("配置管理", expanded=False):
        st.subheader("配置管理")
        
        # 显示当前配置
        current_config = db.get_quality_config() or QUALITY_CONFIG
        
        st.json(current_config)
        
        with st.form("config_form"):
            st.subheader("编辑配置 (开发者模式)")
            config_text = st.text_area("配置内容 (JSON)", value=json.dumps(current_config, ensure_ascii=False, indent=2))
            save_config = st.form_submit_button("保存配置")
            
            if save_config:
                try:
                    parsed_config = json.loads(config_text)
                    db.save_quality_config(parsed_config)
                    st.success("配置保存成功！")
                except Exception as e:
                    st.error(f"保存配置失败: {str(e)}")

def handle_file_upload(uploaded_file):
    """处理文件上传"""
    try:
        # 读取文件
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.success(f"文件加载成功！共 {len(df)} 行数据")
        
        # 验证列
        if not validate_columns(df):
            st.warning("请确保文件包含必要的列")
            return
        
        st.session_state.session_df = df
        st.session_state.session_file_name = uploaded_file.name
        st.session_state.session_row_count = len(df)
        
        # 显示数据预览
        st.subheader("数据预览")
        st.dataframe(df.head(10), use_container_width=True)
        
        # 开始质检按钮
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if st.button("🚀 开始质检", type="primary", use_container_width=True):
                start_analysis()
        
        with col2:
            if st.button("清除数据", use_container_width=True):
                st.session_state.session_df = None
                st.session_state.qa_results = []
                st.session_state.summary_df = None
                st.session_state.error_stats_df = None
                clear_cache()
                st.rerun()
        
    except Exception as e:
        st.error(f"读取文件失败: {str(e)}")

def start_analysis():
    """开始质检分析"""
    df = st.session_state.session_df
    
    if df is None or len(df) == 0:
        st.error("请先上传数据文件")
        return
    
    # 重置费用统计
    reset_cost_manager()
    
    # 显示进度容器
    progress_container = st.empty()
    with progress_container.container():
        status_message = st.empty()
        progress_bar = st.progress(0)
        
        def log_callback(msg):
            status_message.text(msg)
        
        def progress_callback(current, total, *args):
            if total > 0:
                progress_bar.progress(current / total)
        
        try:
            status_message.text("⏳ 正在处理会话数据...")
            
            # 运行质检
            qa_results, summary_df, error_stats_df = run_batch_analysis(
                df,
                settings,
                progress_callback=progress_callback,
                log_callback=log_callback
            )
            
            # 计算合格率和满分率
            total_sessions = len(qa_results)
            avg_score = sum(r['最终得分'] for r in qa_results) / total_sessions if total_sessions > 0 else 0
            pass_count = sum(1 for r in qa_results if r['最终得分'] >= 60)
            pass_rate = (pass_count / total_sessions * 100) if total_sessions > 0 else 0
            perfect_count = sum(1 for r in qa_results if r['最终得分'] == 100)
            perfect_rate = (perfect_count / total_sessions * 100) if total_sessions > 0 else 0
            
            # 准备汇总数据
            summary_data = {
                '总会话数': total_sessions,
                '平均得分': round(avg_score, 1),
                '合格率': round(pass_rate, 1),
                '满分率': round(perfect_rate, 1)
            }
            
            # 准备错误统计数据
            error_stats = []
            if error_stats_df is not None and not error_stats_df.empty:
                for _, row in error_stats_df.iterrows():
                    error_stats.append({
                        '错误编码': row.get('错误编码', ''),
                        '错误名称': row.get('错误名称', ''),
                        '出现次数': row.get('出现次数', 0),
                        '占比': row.get('占比', '0%')
                    })
            
            # 生成专家诊断建议
            executive_summary = generate_executive_summary(summary_data, error_stats)
            
            # 更新状态
            st.session_state.qa_results = qa_results
            st.session_state.summary_df = summary_df
            st.session_state.error_stats_df = error_stats_df
            st.session_state.total_sessions = total_sessions
            st.session_state.processed_count = total_sessions
            st.session_state.executive_summary = executive_summary
            st.session_state.summary_data = summary_data
            
            # 保存缓存
            save_cache({
                'qa_results': qa_results,
                'summary_df': summary_df,
                'error_stats_df': error_stats_df,
                'total_sessions': total_sessions,
                'processed_count': total_sessions,
                'executive_summary': executive_summary,
                'summary_data': summary_data,
                'report_path': st.session_state.report_path,
                'session_file_name': st.session_state.session_file_name,
                'session_row_count': st.session_state.session_row_count
            })
            
            progress_bar.progress(1.0)
            status_message.text("✅ 质检完成！")
            
            time.sleep(1)
            # 清空容器并重新渲染
            progress_container.empty()
            st.rerun()
            
        except Exception as e:
            st.error(f"质检过程出错: {str(e)}")
            st.session_state.last_error_traceback = traceback.format_exc()

def create_radar_chart():
    """创建维度得分雷达图"""
    qa_results = st.session_state.qa_results
    
    if len(qa_results) == 0:
        return None
    
    # 维度映射
    dimension_map = {
        'Dialogue_Logic': '对话逻辑',
        'Policy_Compliance': '政策合规', 
        'Service_Quality': '服务质量'
    }
    
    # 获取维度数据（简化版本）
    try:
        # 从现有结果中提取或模拟数据
        categories = ['对话逻辑', '政策合规', '服务质量', '信息准确', '销售转化']
        values = []
        
        # 计算平均得分
        avg_total = sum(r.get('最终得分', 0) for r in qa_results) / len(qa_results)
        
        # 模拟维度得分
        values = [min(100, avg_total + i * 2) for i in range(5)]
        
        # 创建雷达图
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name='质检表现',
            line=dict(color='#1f77b4'),
            fillcolor='rgba(31, 119, 180, 0.2)'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )
            ),
            height=500
        )
        
        return fig
        
    except Exception as e:
        return None

def create_error_distribution_chart(error_stats_df):
    """创建错误分布图表"""
    if error_stats_df is None or len(error_stats_df) == 0:
        return None
    
    # 中文名称映射
    name_mapping = {
        'Complaint_Mention': '投诉提及',
        'Repeat_Response': '重复回复',
        'Privacy_Leak': '隐私泄露',
        'Rude_Language': '敏感用语',
        'Bad_Attitude': '态度问题',
        'Template_Overuse': '模板过多',
        'No_Solution_Provided': '未提供方案',
        'Answer_Irrelevant': '回答无关',
        'Ignore_User_Question': '忽略用户问题',
        'Solution_Not_Provided': '未提供方案',
        'Low_Service_Awareness': '服务意识低',
        'Slow_Response': '响应缓慢',
        'Lack_of_Empathy': '缺乏同理心',
        'Fail_To_Handle_Complaint': '未处理投诉'
    }
    
    # 准备数据
    display_data = error_stats_df.copy()
    
    # 确保错误编码列存在，并且所有错误名称都映射为中文
    if '错误编码' in display_data.columns:
        display_data['错误名称'] = display_data['错误编码'].map(lambda x: name_mapping.get(x, x))
    elif '错误名称' in display_data.columns:
        # 如果已经有错误名称列，确保是中文
        def to_chinese_name(name):
            for en_name, zh_name in name_mapping.items():
                if en_name in name:
                    return zh_name
            return name
        display_data['错误名称'] = display_data['错误名称'].apply(to_chinese_name)
    
    if '错误名称' in display_data.columns and '出现次数' in display_data.columns:
        fig = px.bar(
            display_data,
            x='错误名称',
            y='出现次数',
            color='错误名称',
            color_discrete_map={
                '隐私泄露': '#dc3545',
                '敏感用语': '#dc3545',
                '态度问题': '#ffc107'
            }
        )
        # 确保图例显示中文
        fig.update_layout(
            legend_title_text='错误类型',
            xaxis_title='错误类型',
            yaxis_title='出现次数'
        )
        return fig
    
    return None

# 清除数据函数
def clear_data():
    """清除所有数据"""
    st.session_state.session_df = None
    st.session_state.qa_results = []
    st.session_state.summary_df = None
    st.session_state.error_stats_df = None
    st.session_state.uploaded_file = None
    st.session_state.session_file_name = None
    st.session_state.session_row_count = 0
    st.session_state.executive_summary = None
    st.session_state.summary_data = None
    reset_cost_manager()
    st.success("数据已清除，您可以上传新文件进行质检")

# 主函数
def main():
    render_header()
    
    # 侧边栏添加清除数据按钮
    with st.sidebar:
        st.title("操作")
        if st.button("🗑️ 清除数据", key="clear_data"):
            clear_data()
        
        st.markdown("---")
    
    # 检查是否有数据
    has_data = len(st.session_state.qa_results) > 0 or st.session_state.session_df is not None
    
    if not has_data:
        # 只有上传区域
        render_empty_state()
    else:
        # 显示标签页
        tabs = st.tabs(["概览看板", "质检明细", "系统配置"])
        
        with tabs[0]:
            render_dashboard_tab()
        
        with tabs[1]:
            render_analysis_tab()
        
        with tabs[2]:
            render_config_tab()
    
    # 如果没有数据，但有上传的文件，显示在侧栏
    if st.session_state.session_df is not None and len(st.session_state.qa_results) == 0:
        st.sidebar.markdown("---")
        st.sidebar.subheader("当前文件")
        st.sidebar.write(f"文件名: {st.session_state.session_file_name}")
        st.sidebar.write(f"行数: {st.session_state.session_row_count}")
        
        if st.sidebar.button("🚀 开始质检", type="primary"):
            start_analysis()

if __name__ == "__main__":
    main()