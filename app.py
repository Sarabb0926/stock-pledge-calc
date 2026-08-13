import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date

# 頁面配置
st.set_page_config(page_title="股票質押與實質套利計算器", page_icon="📈", layout="wide")

st.title("📈 股票質押與實質套利計算器 (高彈性編輯版)")
st.caption("自動連動實時股價 · 多標的轉投資 · 實時天數利息扣除 · 正套利紅字顯示")

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
        
        # 若上市失敗嘗試上櫃 .TWO
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
            "project_name": "2026/10 0050質押專案",
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

# --- 表單 modal / dialog / 側邊區塊：新增或修改專案 ---
def project_form(edit_data=None):
    is_edit = edit_data is not None
    title = "✏️ 編輯質押專案" if is_edit else "➕ 新增質押專案"
    
    with st.expander(title, expanded=is_edit or len(st.session_state.pledges) == 0):
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
            st.subheader("🎯 經驗投入（轉投資標的 - 支援多標的）")
            
            # 多標的動態編輯處理
            num_targets = st.number_input("轉投資標的數量", min_value=1, max_value=5, value=len(edit_data["targets"]) if is_edit else 1)
            
            targets_input = []
            for i in range(int(num_targets)):
                st.markdown(f"**標的 #{i+1}**")
                tc1, tc2, tc3, tc4 = st.columns(4)
                
                default_t = edit_data["targets"][i] if (is_edit and i < len(edit_data["targets"])) else {}
                
                with tc1:
                    t_code = st.text_input(f"標的代號 #{i+1}", value=default_t.get("target_code", "00919"), key=f"t_code_{i}")
                with tc2:
                    t_sheets = st.number_input(f"買入張數 #{i+1}", min_value=0.01, value=float(default_t.get("target_sheets", 10.0)), step=0.5, key=f"t_sheets_{i}")
                with tc3:
                    t_cost = st.number_input(f"買入總成本 #{i+1}", min_value=0, value=int(default_t.get("target_cost", 230000)), key=f"t_cost_{i}")
                with tc4:
                    t_div = st.number_input(f"已領股息總額 #{i+1}", min_value=0, value=int(default_t.get("dividends_received", 0)), key=f"t_div_{i}")
                
                targets_input.append({
                    "target_code": t_code,
                    "target_sheets": t_sheets,
                    "target_cost": t_cost,
                    "dividends_received": t_div
                })

            submit = st.form_submit_button("保存專案" if is_edit else "確認新增")
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
                    st.success("專案更新成功！")
                else:
                    st.session_state.pledges.append(new_project)
                    st.success("新增專案成功！")
                st.rerun()

# 顯示編輯表單或新增表單
if st.session_state.editing_id is not None:
    edit_item = next((p for p in st.session_state.pledges if p["id"] == st.session_state.editing_id), None)
    if edit_item:
        project_form(edit_item)
else:
    project_form()

# --- 資料彙整與實時計算 ---
total_collateral_value = 0.0  # 總質押市值
total_loan_amount = 0.0       # 總借款金額
total_interest_paid = 0.0     # 總至今利息
total_target_value = 0.0      # 總轉投資市值
total_target_cost = 0.0       # 總轉投資成本
total_dividends = 0.0         # 總獲得股息

processed_projects = []

for item in st.session_state.pledges:
    # 1. 質押標的實時價格與市值
    p_price = get_stock_price(item["pledge_code"])
    current_collateral_val = p_price * item["pledge_sheets"] * 1000
    total_collateral_value += current_collateral_val
    total_loan_amount += item["loan_amount"]

    # 2. 換算至今累計利息 (按實際天數 / 365)
    days_pledged = (date.today() - item["pledge_date"]).days
    days_pledged = max(days_pledged, 1) # 至少計 1 天
    accrued_interest = item["loan_amount"] * (item["interest_rate"] / 100.0) * (days_pledged / 365.0)
    total_interest_paid += accrued_interest

    # 3. 轉投資多標的計算
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

    # 4. 單一專案淨套利 = (買入標的未實現損益 + 已領股息) - 至今累積利息
    target_unrealized_gain = proj_target_val - proj_target_cost
    net_arbitrage = (target_unrealized_gain + proj_dividends) - accrued_interest

    processed_projects.append({
        "id": item["id"],
        "專案名稱": item["project_name"],
        "質押標的": f"{item['pledge_code']} ({item['pledge_sheets']}張)",
        "原始成本": f"${item['pledge_cost']:,.0f}",
        "當前質押市值": f"${current_collateral_val:,.0f} (@{p_price})",
        "借款金額": f"${item['loan_amount']:,.0f}",
        "計息天數": f"{days_pledged} 天",
        "至今累計利息": f"${accrued_interest:,.0f}",
        "轉投資標的": "<br>".join(target_summary_list),
        "轉投資總市值": f"${proj_target_val:,.0f}",
        "已領股息": f"${proj_dividends:,.0f}",
        "專案實質套利": net_arbitrage
    })

# 計算整戶維持率
overall_maintenance_ratio = (total_collateral_value / total_loan_amount * 100) if total_loan_amount > 0 else 0
total_net_arbitrage = (total_target_value - total_target_cost + total_dividends) - total_interest_paid

# --- 核心 UI 儀表板 ---
st.divider()
m1, m2, m3, m4 = st.columns(4)

m1.metric("🏛️ 整戶總抵押品市值", f"${total_collateral_value:,.0f}")
m2.metric("💳 總借款金額", f"${total_loan_amount:,.0f}")

# 維持率顏色提醒
if overall_maintenance_ratio < 130:
    ratio_delta = "🚨 低於130% 追繳警告！"
elif overall_maintenance_ratio < 160:
    ratio_delta = "⚠️ 警惕區域 (<160%)"
else:
    ratio_delta = "✅ 安全範圍"

m3.metric("⚡ 整戶總維持率", f"{overall_maintenance_ratio:.2f}%", delta=ratio_delta)
m4.metric("💰 總實質套利金額 (扣利息後)", f"${total_net_arbitrage:,.0f}", delta=f"總配息 ${total_dividends:,.0f}")

st.divider()

# --- 明細與編輯表格 ---
st.subheader("📋 各質押專案明細與操作")

for p in processed_projects:
    with st.container():
        c1, c2 = st.columns([8, 2])
        
        with c1:
            # 套利以紅字醒目顯示 (台灣股市習慣：紅字表示獲利)
            arb_val = p["專案實質套利"]
            if arb_val > 0:
                arb_text = f"<span style='color:red; font-weight:bold; font-size:1.1em;'>+${arb_val:,.0f} (獲利)</span>"
            elif arb_val < 0:
                arb_text = f"<span style='color:green; font-weight:bold; font-size:1.1em;'>-${abs(arb_val):,.0f} (虧損)</span>"
            else:
                arb_text = f"$0"

            st.markdown(f"### 📌 {p['專案名稱']}")
            st.markdown(f"""
            * **質押標的**：{p['質押標的']} | **原始成本**：{p['原始成本']} | **當前質押市值**：{p['當前質押市值']}
            * **借款金額**：{p['借款金額']} | **質押天數**：{p['計息天數']} | **至今累計利息**：{p['至今累計利息']}
            * **轉投資標的**：{p['轉投資標的']}
            * **轉投資市值**：{p['轉投資總市值']} | **已領股息**：{p['已領股息']}
            * **🔥 專案實質淨套利**：{arb_text}
            """, unsafe_allow_html=True)
        
        with c2:
            st.write("")
            st.write("")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✏️ 編輯", key=f"edit_{p['id']}"):
                    st.session_state.editing_id = p["id"]
                    st.rerun()
            with col_btn2:
                if st.button("🗑️ 刪除", key=f"del_{p['id']}"):
                    st.session_state.pledges = [x for x in st.session_state.pledges if x["id"] != p["id"]]
                    if st.session_state.editing_id == p["id"]:
                        st.session_state.editing_id = None
                    st.success("已刪除專案")
                    st.rerun()
        st.divider()
