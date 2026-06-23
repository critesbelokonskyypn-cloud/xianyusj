# ------------------------------------------
# 标签页 1：智能监控看板 (升级大盘版)
# ------------------------------------------
with tab_dashboard:
    st.subheader("📊 全局业务大盘与智能诊断")
    all_data = load_all_data()
    rules = load_knowledge()

    if all_data.empty:
        st.info("💡 数据库暂无数据，请先前往【批量数据录入】录入两天以上的历史数据。")
    else:
        # 获取最新录入的日期
        all_data['date'] = pd.to_datetime(all_data['date'])
        latest_date = all_data['date'].max()

        # ==========================================
        # 🌟 核心升级：全局趋势对比大视图
        # ==========================================
        st.markdown("### 📈 近期趋势多维对比图")

        # 1. 顶部控制器：选指标 + 选商品
        col_metric, col_prods = st.columns([1, 3])
        with col_metric:
            metric_dict = {"销售额 (元)": "sales", "浏览量 (次)": "views", "曝光量 (次)": "exposure"}
            target_metric = st.selectbox("👉 选择对比指标", list(metric_dict.keys()))
            metric_col = metric_dict[target_metric]

        with col_prods:
            unique_prods = all_data['product'].unique().tolist()
            # 默认全选，用户可以随时打叉删掉不想看的，或者只留一个单看
            selected_prods = st.multiselect("👉 选择要对比的商品 (支持多选/单选)", unique_prods, default=unique_prods)

        # 2. 绘制多线大图
        if selected_prods:
            # 过滤出选中的商品数据
            filtered_data = all_data[all_data['product'].isin(selected_prods)]
            # 关键：使用 pivot_table 把数据透视成 "日期"为横轴，"商品"为多条折线的格式
            pivot_data = filtered_data.pivot_table(index='date', columns='product', values=metric_col, aggfunc='sum')

            # 直接交给 Streamlit 画图，它自带图例点击隐藏/显示的功能，并且鼠标放上去会同时看多条线的数据！
            st.line_chart(pivot_data, height=400)
        else:
            st.warning("请至少在上方选择一个商品进行查看。")

        st.markdown("---")

        # ==========================================
        # 🎯 保留原有的：今日异常诊断
        # ==========================================
        st.markdown(f"### 🩺 今日表现智能诊断 (数据日期: **{latest_date.strftime('%Y-%m-%d')}**)")
        today_data = all_data[all_data['date'] == latest_date]

        for _, row in today_data.iterrows():
            prod_name = row['product']
            exp, view = row['exposure'], row['views']
            order, sale = row['orders'], row['sales']

            ctr = view / exp if exp > 0 else 0
            cvr = order / view if view > 0 else 0

            with st.container():
                st.markdown(f"**📦 {prod_name}**")
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("曝光", f"{exp:,}")
                col2.metric("浏览", f"{view:,}")
                col3.metric("点击率", f"{ctr:.2%}")
                col4.metric("转化率", f"{cvr:.2%}")
                col5.metric("销售额", f"¥{sale:,.2f}")

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
                    st.success("✅ 数据健康")
                st.markdown("<br>", unsafe_allow_html=True)  # 加点空行更好看