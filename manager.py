import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# ==========================================
# 1. 数据库初始化与平滑升级
# ==========================================
DB_PATH = 'business_ops.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # 创建主表（包含新增的 inquiries 字段）
        cursor.execute('''CREATE TABLE IF NOT EXISTS daily_metrics (date TEXT, product TEXT, exposure INT, views INT, inquiries INT, orders INT, sales REAL)''')
        
        # 核心防爆逻辑：检测旧数据库是否缺少 inquiries(询单量) 字段，如果缺，就自动补上
        cursor.execute("PRAGMA table_info(daily_metrics)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'inquiries' not in columns:
            cursor.execute("ALTER TABLE daily_metrics ADD COLUMN inquiries INT DEFAULT 0")
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS knowledge_base (rule_type TEXT PRIMARY KEY, rule_name TEXT, threshold REAL, advice TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS product_list (product_name TEXT PRIMARY KEY)''')
        
        # 写入默认诊断规则（注意转化率变成了询单转化率，标准提高到了20%）
        cursor.execute('''INSERT OR IGNORE INTO knowledge_base VALUES 
            ('CTR_LOW', '点击率(CTR)偏低预警', 0.05, '【主图/标题优化】点击率低于5%。请立即更换高吸引力主图，或在标题中加入核心关键词。'),
            ('CVR_LOW', '询单转化率(CVR)偏低预警', 0.20, '【客服/话术优化】询单转化率低于20%。客户来问了但没买，请检查客服响应速度、话术专业度，或适当让利促单。')''')
        
        cursor.execute('INSERT OR IGNORE INTO product_list VALUES ("金铲铲-代肝"), ("第五人格代练")')
        conn.commit()

init_db()

# ==========================================
# 2. 核心数据读取函数 (带缓存)
# ==========================================
@st.cache_data
def load_all_data():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql("SELECT * FROM daily_metrics ORDER BY date DESC", conn)

@st.cache_data
def load_knowledge():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql("SELECT * FROM knowledge_base", conn)

@st.cache_data
def load_products():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql("SELECT product_name FROM product_list", conn)['product_name'].tolist()

# ==========================================
# 3. 软件界面与逻辑搭建
# ==========================================
st.set_page_config(page_title="电商数据运营中台", layout="wide")
st.title("🛡️ 智能数据运营与指引决策系统")

tab_dashboard, tab_input, tab_products, tab_knowledge = st.tabs([
    "📊 智能监控看板", "✍️ 批量数据录入", "📦 商品库管理", "🧠 运营知识库"
])

# ------------------------------------------
# 标签页 1：智能监控看板 (全局大盘版)
# ------------------------------------------
with tab_dashboard:
    st.subheader("📊 全局业务大盘与智能诊断")
    all_data = load_all_data()
    rules = load_knowledge()
    
    if all_data.empty:
        st.info("💡 数据库暂无数据，请先前往【批量数据录入】录入你的业务数据。")
    else:
        all_data['date'] = pd.to_datetime(all_data['date'])
        latest_date = all_data['date'].max()
        
        st.markdown("### 📈 近期趋势多维对比图")
        col_metric, col_prods = st.columns([1, 3])
        with col_metric:
            metric_dict = {"销售额 (元)": "sales", "询单量 (次)": "inquiries", "浏览量 (次)": "views", "曝光量 (次)": "exposure"}
            target_metric = st.selectbox("👉 选择对比指标", list(metric_dict.keys()))
            metric_col = metric_dict[target_metric]
            
        with col_prods:
            unique_prods = all_data['product'].unique().tolist()
            selected_prods = st.multiselect("👉 选择要对比的商品", unique_prods, default=unique_prods)
        
        if selected_prods:
            filtered_data = all_data[all_data['product'].isin(selected_prods)]
            # 只有当数据包含超过一天时，画折线图才有意义
            if len(filtered_data['date'].unique()) > 1:
                pivot_data = filtered_data.pivot_table(index='date', columns='product', values=metric_col, aggfunc='sum')
                st.line_chart(pivot_data, height=400)
            else:
                st.info("📌 数据天数不足2天，暂无法绘制趋势折线图，请继续录入明日数据即可激活。")
        else:
            st.warning("请至少在上方选择一个商品进行查看。")
            
        st.markdown("---")
        st.markdown(f"### 🩺 今日表现智能诊断 (数据日期: **{latest_date.strftime('%Y-%m-%d')}**)")
        today_data = all_data[all_data['date'] == latest_date]
        
        for _, row in today_data.iterrows():
            prod_name = row['product']
            exp, view = row['exposure'], row['views']
            inq = row.get('inquiries', 0) # 兼容老数据
            order, sale = row['orders'], row['sales']
            
            # 核心业务逻辑更新！！！
            ctr = view / exp if exp > 0 else 0
            cvr = order / inq if inq > 0 else 0
            
            with st.container():
                st.markdown(f"**📦 {prod_name}**")
                # 调整为 6 列，把各种率和基础数据分开展现
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                col1.metric("曝光量", f"{exp:,}")
                col2.metric("浏览量", f"{view:,}")
                col3.metric("点击率 (浏览/曝光)", f"{ctr:.2%}")
                col4.metric("询单量", f"{inq:,}")
                col5.metric("转化率 (成交/询单)", f"{cvr:.2%}")
                col6.metric("销售额", f"¥{sale:,.2f}")
                
                has_advice = False
                ctr_rule = rules[rules['rule_type'] == 'CTR_LOW'].iloc[0]
                if ctr < ctr_rule['threshold']:
                    st.error(ctr_rule['advice'])
                    has_advice = True
                    
                cvr_rule = rules[rules['rule_type'] == 'CVR_LOW'].iloc[0]
                if cvr < cvr_rule['threshold']:
                    st.warning(cvr_rule['advice'])
                    has_advice = True
                    
                if not has_advice:
                    st.success("✅ 各项转化率指标健康，请继续保持！")
                st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------
# 标签页 2：批量矩阵数据录入
# ------------------------------------------
with tab_input:
    st.subheader("每日批量数据填报")
    input_date = st.date_input("确认录入日期", datetime.now())
    active_products = load_products()
    
    if not active_products:
        st.warning("⚠️ 暂无商品，请先前往【商品库管理】添加商品。")
    else:
        # 表格增加“询单量”
        entry_template = pd.DataFrame({
            "商品名称": active_products,
            "曝光量": [0] * len(active_products),
            "浏览量": [0] * len(active_products),
            "询单量": [0] * len(active_products),
            "成交单数": [0] * len(active_products),
            "销售额(元)": [0.0] * len(active_products)
        })
        
        st.caption("👇 请直接在下方表格内双击数字进行修改：")
        edited_df = st.data_editor(entry_template, hide_index=True, use_container_width=True, disabled=["商品名称"])
        
        if st.button("💾 一键批量保存所有数据", type="primary"):
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                for _, row in edited_df.iterrows():
                    cursor.execute('INSERT INTO daily_metrics (date, product, exposure, views, inquiries, orders, sales) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                                   (input_date.strftime('%Y-%m-%d'), row['商品名称'], row['曝光量'], row['浏览量'], row['询单量'], row['成交单数'], row['销售额(元)']))
                conn.commit()
            st.cache_data.clear()
            st.success(f"✅ 成功！{len(active_products)} 个商品的数据已保存！请去看板查看。")

# ------------------------------------------
# 标签页 3 & 4：商品库管理与知识库
# ------------------------------------------
with tab_products:
    st.subheader("商品白名单配置")
    active_products = load_products()
    for p in active_products: st.markdown(f"- **{p}**")
    col_add, col_del = st.columns(2)
    with col_add:
        new_prod = st.text_input("➕ 添加新商品")
        if st.button("确认添加") and new_prod:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('INSERT OR IGNORE INTO product_list VALUES (?)', (new_prod,))
                conn.commit()
            st.cache_data.clear()
            st.rerun()
    with col_del:
        del_prod = st.selectbox("🗑️ 删除不再监控的商品", ["(请选择)"] + active_products)
        if st.button("确认删除") and del_prod != "(请选择)":
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('DELETE FROM product_list WHERE product_name = ?', (del_prod,))
                conn.commit()
            st.cache_data.clear()
            st.rerun()

with tab_knowledge:
    st.subheader("调整预警阈值与优化话术")
    current_rules = load_knowledge()
    for idx, r in current_rules.iterrows():
        with st.expander(f"⚙️ 设置：{r['rule_name']}"):
            new_threshold = st.slider(f"触发红线的阈值", min_value=0.0, max_value=1.0, value=float(r['threshold']), step=0.01)
            new_advice = st.text_area("触碰红线时的建议：", value=r['advice'])
            if st.button("保存此规则", key=f"btn_{r['rule_type']}"):
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute('UPDATE knowledge_base SET threshold = ?, advice = ? WHERE rule_type = ?', (new_threshold, new_advice, r['rule_type']))
                    conn.commit()
                st.cache_data.clear()
                st.success("规则更新成功！")
