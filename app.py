import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date

# 頁面配置
st.set_page_config(page_title="股票質押與實質套利計算器", page_icon="📈", layout="wide")

st.title("📈 股票質押與實質套利計算器")
st.caption("自動連動實時股價 · 整戶維持率監控 · 股息扣除利息真套利計算")

# --- 股價抓取工具函數 ---
@st.cache_data(ttl=300)  # 快取 5 分鐘，避免頻繁請求
def get_stock_price(symbol: str) -> float:
    """自動處理台股代號（例如：0050 -> 0050.TW）並抓取最新股價"""
    symbol = symbol.strip().upper()
    if not symbol.endswith(".TW") and not symbol.endswith(".TWO"):
        symbol_formatted = f"{symbol}.TW"
    else:
        symbol_formatted = symbol
    
    try:
        ticker = yf.Ticker(symbol_formatted)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
        
        # 若上興櫃或櫃買市場嘗試 .TWO
        if not symbol.endswith(".TWO"):
            ticker_two = yf.Ticker(f"{symbol.split('.')[0]}.TWO")
            hist_two = ticker_two.history(period="1d")
            if not hist_two.empty:
                return round(float(hist_two["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return 0.0

# --- 初始化 Session State 暫存資料庫 ---
if "pledges" not in st.session_state:
    # 預設範例資料（如使用者情境）
    st.session_state.pledges = [
        {
            "id": 1,
            "project_name": "2025/10 0050質押專案",
            "pledge_code": "0050",
            "pledge_shares": 5000, # 5張 = 5000股
            "pledge_cost": 100000,
            "loan_amount": 500000,
            "interest_rate": 3.8,
            "pledge_date": date(2025, 10, 10),
            "target_code": "00919",
            "target_shares": 100000, # 10張 = 10,000股
            "target_cost": 230000,
            "dividends_received": 15000
        }
    ]

# --- 側邊欄：新增質押專案 ---
with st.sidebar:
    st.header("➕ 新增質押專案")
    with st.form("add_pledge_form"):
        p_name = st.text_input("專案名稱", value="新質押專案")
        col1, col2 = st.columns(2)
        with col1:
            p_code = st.text_input("質押標的代號", value="0050")
            p_sheets = st.number_input("質押張數", min_value=0.1, value=5.0, step=0.5)
            p_cost = st.number_input("質押標的總成本 (元)", min_value=0, value=100000)
        with col2:
            p_loan = st.number_input("借款金額 (元)", min_value=0, value=500000)
            p_rate = st.number_input("借款年利率 (%)", min_value=0.0, value=3.8, step=0.1)
            p_date = st.date_input("質押開始日期", value=date.today())
        
        st.subheader("經驗投入（轉投資標的）")
        t_code = st.text_input("買入標的代號", value="00919")
        t_sheets = st.number_input("買入張數", min_value=0.1, value=10.0, step=0.5)
        t_cost = st.number_input("買入總成本 (元)", min_value=0, value=230000)
        t_div = st.number_input("已獲得配息總額 (元)", min_value=0, value=0)

        submit = st.form_submit_button("新增專案")
        if submit:
            new_id = len(st.session_state.pledges) + 1
            st.session_state.pledges.append({
                "id": new_id,
                "project_name": p_name,
                "pledge_code": p_code,
                "pledge_shares": int(p_sheets * 1000),
                "pledge_cost": p_cost,
                "loan_amount": p_loan,
                "interest_rate": p_rate,
                "pledge_date": p_date,
                "target_code": t_code,
                "target_shares": int(t_sheets * 1000),
                "target_cost": t_cost,
                "dividends_received": t_div
            })
            st.success("成功新增專案！")
            st.rerun()

# --- 資料彙整與實時計算 ---
total_collateral_value = 0.0  # 總抵押品當前市值
total_loan_amount = 0.0       # 總借款金額
total_interest_paid = 0.0     # 總已產生利息
total_target_value = 0.0      # 總再投資當前市值
total_target_cost = 0.0       # 總再投資成本
total_dividends = 0.0         # 總獲得股息

processed_projects = []

for item in st.session_state.pledges:
    # 抓取實時股價
    p_price = get_stock_price(item["pledge_code"])
    t_price = get_stock_price(item["target_code"])

    # 1. 抵押品計算
    current_collateral_val = p_price * item["pledge_shares"]
    total_collateral_value += current_collateral_val
    total_loan_amount += item["loan_amount"]

    # 2. 利息計算 (質押天數)
    days_pledged = (date.today() - item["pledge_date"]).days
    days_pledged = max(days_pledged, 1) # 至少計1天
    accrued_interest = item["loan_amount"] * (item["interest_rate"] / 100.0) * (days_pledged / 365.0)
    total_interest_paid += accrued_interest

    # 3. 再投資計算
    current_target_val = t_price * item["target_shares"]
    target_unrealized_gain = current_target_val - item["target_cost"]
    
    total_target_value += current_target_val
    total_target_cost += item["target_cost"]
    total_dividends += item["dividends_received"]

    # 單一專案淨套利 = (買入標的未實現損益 + 已領股息) - 借款利息
    net_arbitrage = (target_unrealized_gain + item["dividends_received"]) - accrued_interest

    processed_projects.append({
        "專案名稱": item["project_name"],
        "質押標的": f"{item['pledge_code']} ({item['pledge_shares']/1000:.1f}張)",
        "當前質押市值": f"${current_collateral_val:,.0f} (@{p_price})",
        "借款金額": f"${item['loan_amount']:,.0f}",
        "計息天數": f"{days_pledged} 天",
        "預估已產生利息": f"${accrued_interest:,.0f}",
        "再投資標的": f"{item['target_code']} ({item['target_shares']/1000:.1f}張)",
        "再投資當前市值": f"${current_target_val:,.0f} (@{t_price})",
        "已領股息": f"${item['dividends_received']:,.0f}",
        "專案實質套利": f"${net_arbitrage:,.0f}"
    })

# 計算整戶維持率
overall_maintenance_ratio = (total_collateral_value / total_loan_amount * 100) if total_loan_amount > 0 else 0
total_net_arbitrage = (total_target_value - total_target_cost + total_dividends) - total_interest_paid

# --- 核心 UI 儀表板 ---
m1, m2, m3, m4 = st.columns(4)

m1.metric("🏛️ 整戶總抵押品市值", f"${total_collateral_value:,.0f}")
m2.metric("💳 總借款金額", f"${total_loan_amount:,.0f}")

# 維持率顏色提醒
ratio_color = "normal"
if overall_maintenance_ratio < 130:
    ratio_delta = "🚨 低於130% 追繳警告！"
elif overall_maintenance_ratio < 160:
    ratio_delta = "⚠️ 警惕區域 (<160%)"
else:
    ratio_delta = "✅ 安全範圍"

m3.metric("⚡ 整戶總維持率", f"{overall_maintenance_ratio:.2f}%", delta=ratio_delta)
m4.metric("💰 總實質套利金額 (扣利息後)", f"${total_net_arbitrage:,.0f}", delta=f"總配息 ${total_dividends:,.0f}")

st.divider()

# --- 明細表格展示 ---
st.subheader("📋 各質押專案明細 (多專案分開，維持率統一計算)")

if processed_projects:
    df = pd.DataFrame(processed_projects)
    st.dataframe(df, use_container_width=True)
    
    # 清除資料按鈕
    if st.button("🗑️ 清空所有專案"):
        st.session_state.pledges = []
        st.rerun()
else:
    st.info("目前沒有任何質押專案，請從左側欄新增！")
