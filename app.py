import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date

# 頁面配置
st.set_page_config(page_title="股票質押與實質套利計算器", page_icon="📈", layout="wide")

st.title("📈 股票質押與實質套利計算器")
st.caption("自動連動實時股價 · 多標的轉投資 · 整戶維持率監控 · 全表格化美化呈現")

# --- 股價抓取工具函數 ---
@st.cache_data(ttl=300)
def get_stock_price(symbol: str) -> float:
    """自動處理台股代號（例如：0050 -> 0050.TW）並抓取最新股價"""
    symbol = symbol.strip().upper()
    if not symbol:
        return 0.0
    if not symbol.endswith(".TW") and not symbol.endswith(".TWO"):
        symbol_formatted = f"{symbol}.TW"
    else:
        symbol_formatted = symbol
    
    try:
        ticker = yf.Ticker(symbol_formatted)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
        
        if not symbol.endswith(".TWO"):
            ticker_two = yf.Ticker(f"{symbol.split('.')[0]}.TWO")
            hist_two = ticker_two.history(period="1d")
            if not hist_two.empty:
                return round(float(hist_two["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return 0.0

# --- 初始化 Session State 資料庫 ---
if "pledges" not in st.session_state:
    st.session_state.pledges = [
        {
            "id": 1,
            "project_name": "2025/10 0050質押專案",
            "pledge_code": "0050",
            "pledge_sheets": 5.0,
            "pledge_cost": 100000,
            "loan_amount": 500000,
            "interest_rate": 3.8,
            "pledge_date": date(2025, 10, 10),
            "targets": [
                {
                    "target_code": "00919",
                    "target_sheets": 10.0,
                    "target_cost": 230000,
                    "dividends_received": 15000
                }
            ]
        }
    ]

if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

# --- 新增 / 編輯專案表單區 ---
def project_form(edit_data=None):
    is_edit = edit_data is not None
    title = "✏️ 編輯專案內容" if is_edit else "➕ 新增質押專案"
    
    with st.expander(title, expanded=is_edit):
        with st.form(key="pledge_form_" + ("edit" if is_edit else "add")):
            p_name = st.text_input("專案名稱", value=edit_data["project_name"] if is_edit else "新質押專案")
            col1, col2 = st.columns(2)
            with col1:
                p_code = st.text_input("質押標的代號", value=edit_data["pledge_code"] if is_edit else "0050")
                p_sheets = st.number_input("質押張數", min_value=0.01, value=float(edit_data["pledge_sheets"]) if is_edit else 5.0, step=0.5)
                p_cost = st.number_input("質押標的原始成本 (元)", min_value=0, value=int(edit_data["pledge_cost"]) if is_edit else 100000)
            with col2:
                p_loan = st.number_input("借款金額 (元)", min_value=0, value=int(edit_data["loan_amount"]) if is_edit else 500000)
                p_rate = st.number_input("借款年利率 (%)", min_value=0.0, value=float(edit_data["interest_rate"]) if is_edit else 3.8, step=0.1)
                p_date = st.date_input("質押開始日期", value=edit_data["pledge_date"] if is_edit else date.today())
            
            st.markdown("---")
            st.subheader("🎯 轉投資標的設定 (可新增多個)")
            num_targets = st.number_input("轉投資標的數量", min_value=1, max_value=5, value=len(edit_data["targets"]) if is_edit else 1)
            
            targets_input = []
            for i in range(int(num_targets)):
                st.markdown(f"**標的 #{i+1}**")
                tc1, tc2, tc3, tc4 = st.columns(4)
                default_t = edit_data["targets"][i] if (is_edit and i < len(edit_data["targets"])) else {}
                
                with tc1:
                    t_code = st.text_input(f"代號 #{i+1}", value=default_t.get("target_code", "00919"), key=f"t_code_{i}")
                with tc2:
                    t_sheets = st.number_input(f"張數 #{i+1}", min_value=0.01, value=float(default_t.get("target_sheets", 10.0)), step=0.5, key=f"t_sheets_{i}")
                with tc3:
                    t_cost = st.number_input(f"總成本 #{i+1}", min_value=0, value=int(default_t.get("target_cost", 230000)), key=f"t_cost_{i}")
                with tc4:
                    t_div = st.number_input(f"已領股息 #{i+1}", min_value=0, value=int(default_t.get("dividends_received", 0)), key=f"t_div_{i}")
                
                targets_input.append({
                    "target_code": t_code,
                    "target_sheets": t_sheets,
                    "target_cost": t_cost,
                    "dividends_received": t_div
                })

            submit = st.form_submit_button("💾 儲存專案" if is_edit else "確認新增")
            if submit:
                new_project = {
                    "id": edit_data["id"] if is_edit else (max([p["id"] for p in st.session_state.pledges], default=0) + 1),
                    "project_name": p_name,
                    "pledge_code": p_code,
                    "pledge_sheets": p_sheets,
                    "pledge_cost": p_cost,
                    "loan_amount": p_loan,
                    "interest_rate": p_rate,
                    "pledge_date": p_date,
                    "targets": targets_input
                }
                
                if is_edit:
                    for idx, p in enumerate(st.session_state.pledges):
                        if p["id"] == edit_data["id"]:
                            st.session_state.pledges[idx] = new_project
                            break
                    st.session_state.editing_id = None
                    st.success("專案已更新！")
                else:
                    st.session_state.pledges.append(new_project)
                    st.success("專案已新增！")
                st.rerun()

# 顯示編輯視窗或新增按鈕
if st.session_state.editing_id is not None:
    edit_item = next((p for p in st.session_state.pledges if p["id"] == st.session_state.editing_id), None)
    if edit_item:
        project_form(edit_item)
else:
    project_form()

# --- 資料計算邏輯 ---
total_collateral_value = 0.0
total_loan_amount = 0.0
total_interest_paid = 0.0
total_target_value = 0.0
total_target_cost = 0.0
total_dividends = 0.0

table_rows = []

for item in st.session_state.pledges:
    p_price = get_stock_price(item["pledge_code"])
    current_collateral_val = p_price * item["pledge_sheets"] * 1000
    total_collateral_value += current_collateral_val
    total_loan_amount += item["loan_amount"]

    days_pledged = (date.today() - item["pledge_date"]).days
    days_pledged = max(days_pledged, 1)
    accrued_interest = item["loan_amount"] * (item["interest_rate"] / 100.0) * (days_pledged / 365.0)
    total_interest_paid += accrued_interest

    proj_target_val = 0.0
    proj_target_cost = 0.0
    proj_dividends = 0.0
    target_summary_list = []

    for t in item["targets"]:
        t_price = get_stock_price(t["target_code"])
        c_val = t_price * t["target_sheets"] * 1000
        proj_target_val += c_val
        proj_target_cost += t["target_cost"]
        proj_dividends += t["dividends_received"]
        target_summary_list.append(f"{t['target_code']} ({t['target_sheets']}張 @{t_price})")

    total_target_value += proj_target_val
    total_target_cost += proj_target_cost
    total_dividends += proj_dividends

    target_unrealized_gain = proj_target_val - proj_target_cost
    net_arbitrage = (target_unrealized_gain + proj_dividends) - accrued_interest

    # 格式化顯示字串
    table_rows.append({
        "ID": item["id"],
        "專案名稱": item["project_name"],
        "質押標的": f"{item['pledge_code']} ({item['pledge_sheets']}張)",
        "原始成本": f"${item['pledge_cost']:,.0f}",
        "質押當前市值": f"${current_collateral_val:,.0f} (@{p_price})",
        "借款金額": f"${item['loan_amount']:,.0f}",
        "天數/利率": f"{days_pledged}天 / {item['interest_rate']}%",
        "至今累計利息": f"${accrued_interest:,.0f}",
        "轉投資標的": ", ".join(target_summary_list),
        "轉投資市值": f"${proj_target_val:,.0f}",
        "已領股息": f"${proj_dividends:,.0f}",
        "實質淨套利": net_arbitrage
    })

# 計算整戶維持率與總套利
overall_maintenance_ratio = (total_collateral_value / total_loan_amount * 100) if total_loan_amount > 0 else 0
total_net_arbitrage = (total_target_value - total_target_cost + total_dividends) - total_interest_paid

# --- 頂部儀表板卡片 ---
st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("🏛️ 整戶總抵押品市值", f"${total_collateral_value:,.0f}")
m2.metric("💳 總借款金額", f"${total_loan_amount:,.0f}")

if overall_maintenance_ratio < 130:
    ratio_delta = "🚨 低於130% 追繳警告！"
elif overall_maintenance_ratio < 160:
    ratio_delta = "⚠️ 警惕區域 (<160%)"
else:
    ratio_delta = "✅ 安全範圍"

m3.metric("⚡ 整戶總維持率", f"{overall_maintenance_ratio:.2f}%", delta=ratio_delta)
m4.metric("💰 總實質套利金額", f"${total_net_arbitrage:,.0f}", delta=f"總配息 ${total_dividends:,.0f}")

st.divider()

# --- 美化表格呈現區 ---
st.subheader("📋 質押專案彙整總表")

if table_rows:
    # 建立 Pandas DataFrame
    df = pd.DataFrame(table_rows)

    # 自訂 HTML 表格 (支援台股獲利紅字顯示)
    html_table = """
    <style>
        .styled-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: center;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.15);
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 20px;
        }
        .styled-table thead tr {
            background-color: #1f77b4;
            color: #ffffff;
            text-align: center;
            font-weight: bold;
        }
        .styled-table th, .styled-table td {
            padding: 12px 10px;
            border-bottom: 1px solid #dddddd;
        }
        .styled-table tbody tr:nth-of-type(even) {
            background-color: rgba(255, 255, 255, 0.05);
        }
        .profit-red { color: #ff4d4f; font-weight: bold; font-size: 1.05em; }
        .loss-green { color: #52c41a; font-weight: bold; font-size: 1.05em; }
    </style>
    <table class="styled-table">
        <thead>
            <tr>
                <th>專案名稱</th>
                <th>質押標的</th>
                <th>原始成本</th>
                <th>當前質押市值</th>
                <th>借款金額</th>
                <th>天數/利率</th>
                <th>至今利息</th>
                <th>轉投資標的</th>
                <th>轉投資市值</th>
                <th>已領股息</th>
                <th>🔥 實質淨套利</th>
            </tr>
        </thead>
        <tbody>
    """

    for r in table_rows:
        arb_val = r["實質淨套利"]
        if arb_val > 0:
            arb_html = f"<span class='profit-red'>+${arb_val:,.0f}</span>"
        elif arb_val < 0:
            arb_html = f"<span class='loss-green'>-${abs(arb_val):,.0f}</span>"
        else:
            arb_html = "$0"

        html_table += f"""
            <tr>
                <td><b>{r['專案名稱']}</b></td>
                <td>{r['質押標的']}</td>
                <td>{r['原始成本']}</td>
                <td>{r['質押當前市值']}</td>
                <td>{r['借款金額']}</td>
                <td>{r['天數/利率']}</td>
                <td>{r['至今累計利息']}</td>
                <td>{r['轉投資標的']}</td>
                <td>{r['轉投資市值']}</td>
                <td>{r['已領股息']}</td>
                <td>{arb_html}</td>
            </tr>
        """
    html_table += "</tbody></table>"
    st.markdown(html_table, unsafe_allow_html=True)

    # 專案操作按鈕區
    st.subheader("⚙️ 專案管理操作")
    col_sel, col_act1, col_act2 = st.columns([4, 1, 1])
    
    with col_sel:
        selected_proj_id = st.selectbox(
            "選擇要管理的專案：", 
            options=[p["id"] for p in st.session_state.pledges],
            format_func=lambda x: next((p["project_name"] for p in st.session_state.pledges if p["id"] == x), "")
        )
    
    with col_act1:
        st.write("")
        st.write("")
        if st.button("✏️ 編輯選擇的專案", use_container_width=True):
            st.session_state.editing_id = selected_proj_id
            st.rerun()

    with col_act2:
        st.write("")
        st.write("")
        if st.button("🗑️ 刪除選擇的專案", use_container_width=True):
            st.session_state.pledges = [x for x in st.session_state.pledges if x["id"] != selected_proj_id]
            if st.session_state.editing_id == selected_proj_id:
                st.session_state.editing_id = None
            st.success("已成功刪除！")
            st.rerun()
else:
    st.info("目前尚無專案，請點選上方「➕ 新增質押專案」建構你的第一筆套利專案！")
