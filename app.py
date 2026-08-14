import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date
import json
import requests

# 頁面配置
st.set_page_config(page_title="股票質押與實質套利筆記本", page_icon="📈", layout="wide")

st.title("📈 股票質押與實質套利筆記本 (Google Sheets 雲端連線版)")
st.caption("自動連動實時股價 · Google 雲端自動存檔 · 跨裝置即時同步 · 整戶維持率監控")

# ==============================================================================
# 🔗 請將下方引號內的網址換成你的 Google Apps Script 網址
# ==============================================================================
GSHEET_API_URL = "https://script.google.com/macros/s/AKfycby-8R2n7t_l7oX26KjQa1go6PlgzdAZ975prldxzsav4QVHhvdaoDWr5dn5sWBrEDW1ww/exec"
# ==============================================================================

def load_pledges_from_cloud():
    """從 Google Sheets 讀取專案資料"""
    if "AKfycb" not in GSHEET_API_URL:
        return None
    try:
        res = requests.get(GSHEET_API_URL, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                parsed_list = []
                for row in data:
                    t_json = row.get("targets_json", "[]")
                    targets = json.loads(t_json) if isinstance(t_json, str) else t_json
                    parsed_list.append({
                        "id": int(row["id"]),
                        "project_name": str(row["project_name"]),
                        "pledge_code": str(row["pledge_code"]),
                        "pledge_sheets": float(row["pledge_sheets"]),
                        "pledge_cost": float(row["pledge_cost"]),
                        "loan_amount": float(row["loan_amount"]),
                        "interest_rate": float(row["interest_rate"]),
                        "pledge_date": datetime.strptime(str(row["pledge_date"]).split("T")[0], "%Y-%m-%d").date(),
                        "targets": targets
                    })
                return parsed_list
    except Exception as e:
        pass
    return None

def save_pledges_to_cloud(pledges_list):
    """將專案資料即時寫入 Google Sheets"""
    if "AKfycb" not in GSHEET_API_URL:
        return False, "尚未設定 Google Sheets API 網址"
    try:
        flat_data = []
        for p in pledges_list:
            flat_data.append({
                "id": p["id"],
                "project_name": p["project_name"],
                "pledge_code": p["pledge_code"],
                "pledge_sheets": p["pledge_sheets"],
                "pledge_cost": p["pledge_cost"],
                "loan_amount": p["loan_amount"],
                "interest_rate": p["interest_rate"],
                "pledge_date": p["pledge_date"].strftime("%Y-%m-%d"),
                "targets_json": json.dumps(p["targets"], ensure_ascii=False)
            })
        
        res = requests.post(GSHEET_API_URL, json=flat_data, timeout=8)
        if res.status_code == 200:
            return True, "雲端同步成功"
        return False, f"HTTP 狀態碼: {res.status_code}"
    except Exception as e:
        return False, str(e)

# --- 股價抓取工具函數 ---
@st.cache_data(ttl=300)
def get_stock_price(symbol: str) -> float:
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
    cloud_data = load_pledges_from_cloud()
    if cloud_data:
        st.session_state.pledges = cloud_data
    else:
        st.session_state.pledges = [
            {
                "id": 1,
                "project_name": "2025質押套利計畫",
                "pledge_code": "00878",
                "pledge_sheets": 10.0,
                "pledge_cost": 111181,
                "loan_amount": 100000,
                "interest_rate": 2.28,
                "pledge_date": date(2025, 9, 5),
                "targets": [
                    {
                        "target_code": "00919",
                        "target_sheets": 1.0,
                        "target_cost": 30410,
                        "dividends_received": 2340
                    }
                ]
            }
        ]

if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

if "form_targets" not in st.session_state:
    st.session_state.form_targets = []

# --- 表單處理邏輯 ---
def open_edit_form(edit_data=None):
    if edit_data:
        st.session_state.editing_id = edit_data["id"]
        st.session_state.form_targets = [dict(t) for t in edit_data["targets"]]
    else:
        st.session_state.editing_id = "NEW"
        st.session_state.form_targets = [{
            "target_code": "00919",
            "target_sheets": 1.0,
            "target_cost": 30000,
            "dividends_received": 0
        }]

is_editing = st.session_state.editing_id is not None
edit_item = None
if is_editing and st.session_state.editing_id != "NEW":
    edit_item = next((p for p in st.session_state.pledges if p["id"] == st.session_state.editing_id), None)

form_title = "✏️ 編輯專案" if (is_editing and st.session_state.editing_id != "NEW") else "➕ 新增質押專案"

with st.expander(form_title, expanded=is_editing):
    with st.form(key="pledge_main_form"):
        p_name = st.text_input("專案名稱", value=edit_item["project_name"] if edit_item else "新質押專案")
        col1, col2 = st.columns(2)
        with col1:
            p_code = st.text_input("質押標的代號", value=edit_item["pledge_code"] if edit_item else "0050")
            p_sheets = st.number_input("質押張數", min_value=0.01, value=float(edit_item["pledge_sheets"]) if edit_item else 5.0, step=0.5)
            p_cost = st.number_input("質押標的原始成本 (元)", min_value=0, value=int(edit_item["pledge_cost"]) if edit_item else 100000)
        with col2:
            p_loan = st.number_input("借款金額 (元)", min_value=0, value=int(edit_item["loan_amount"]) if edit_item else 500000)
            p_rate = st.number_input("借款年利率 (%)", min_value=0.0, value=float(edit_item["interest_rate"]) if edit_item else 3.8, step=0.01)
            p_date = st.date_input("質押開始日期", value=edit_item["pledge_date"] if edit_item else date.today())
        
        st.markdown("---")
        st.subheader("🎯 轉投資標的設定")
        
        updated_targets = []
        for idx, t in enumerate(st.session_state.form_targets):
            st.markdown(f"**轉投資標的 #{idx+1}**")
            tc1, tc2, tc3, tc4 = st.columns(4)
            with tc1:
                t_code = st.text_input("標的代號", value=t.get("target_code", ""), key=f"t_code_{idx}")
            with tc2:
                t_sheets = st.number_input("買入張數", min_value=0.01, value=float(t.get("target_sheets", 1.0)), step=0.5, key=f"t_sheets_{idx}")
            with tc3:
                t_cost = st.number_input("買入總成本 (元)", min_value=0, value=int(t.get("target_cost", 0)), key=f"t_cost_{idx}")
            with tc4:
                t_div = st.number_input("已領股息總額 (元)", min_value=0, value=int(t.get("dividends_received", 0)), key=f"t_div_{idx}")
            
            updated_targets.append({
                "target_code": t_code,
                "target_sheets": t_sheets,
                "target_cost": t_cost,
                "dividends_received": t_div
            })

        submit_btn = st.form_submit_button("💾 儲存並即時同步 Google Sheets")

        if submit_btn:
            new_id = edit_item["id"] if edit_item else (max([p["id"] for p in st.session_state.pledges], default=0) + 1)
            new_project = {
                "id": new_id,
                "project_name": p_name,
                "pledge_code": p_code,
                "pledge_sheets": p_sheets,
                "pledge_cost": p_cost,
                "loan_amount": p_loan,
                "interest_rate": p_rate,
                "pledge_date": p_date,
                "targets": updated_targets
            }
            
            if edit_item:
                for i, p in enumerate(st.session_state.pledges):
                    if p["id"] == edit_item["id"]:
                        st.session_state.pledges[i] = new_project
                        break
            else:
                st.session_state.pledges.append(new_project)
            
            success, msg = save_pledges_to_cloud(st.session_state.pledges)
            st.session_state.editing_id = None
            if success:
                st.success("✅ 專案已儲存，並已成功同步至 Google Sheets！")
            else:
                st.warning(f"⚠️ 本地已儲存，但雲端同步失敗：{msg}")
            st.rerun()

    b_col1, b_col2 = st.columns([1, 4])
    with b_col1:
        if st.button("➕ 新增轉投資標的"):
            st.session_state.form_targets.append({
                "target_code": "", "target_sheets": 1.0, "target_cost": 0, "dividends_received": 0
            })
            st.rerun()
    with b_col2:
        if len(st.session_state.form_targets) > 1:
            if st.button("🗑️ 刪除最後一個標的"):
                st.session_state.form_targets.pop()
                st.rerun()

# --- 資料計算與彙整 ---
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
        if not t["target_code"]:
            continue
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

    table_rows.append({
        "id": item["id"],
        "name": item["project_name"],
        "pledge": f"{item['pledge_code']} ({item['pledge_sheets']}張)",
        "cost": f"${item['pledge_cost']:,.0f}",
        "pledge_val": f"${current_collateral_val:,.0f} (@{p_price})",
        "loan": f"${item['loan_amount']:,.0f}",
        "days_rate": f"{days_pledged}天 / {item['interest_rate']}%",
        "interest": f"${accrued_interest:,.0f}",
        "targets": "<br>".join(target_summary_list) if target_summary_list else "無",
        "target_val": f"${proj_target_val:,.0f}",
        "dividends": f"${proj_dividends:,.0f}",
        "arbitrage": net_arbitrage
    })

overall_maintenance_ratio = (total_collateral_value / total_loan_amount * 100) if total_loan_amount > 0 else 0
total_net_arbitrage = (total_target_value - total_target_cost + total_dividends) - total_interest_paid

# --- 頂部儀表板 ---
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

# --- 彙整總表 ---
st.subheader("📋 質押專案彙整總表")

if table_rows:
    table_body = ""
    for r in table_rows:
        arb_val = r["arbitrage"]
        if arb_val > 0:
            arb_html = f"<b style='color:#ff4d4f;'>+${arb_val:,.0f}</b>"
        elif arb_val < 0:
            arb_html = f"<b style='color:#52c41a;'>-${abs(arb_val):,.0f}</b>"
        else:
            arb_html = "$0"

        table_body += f"""<tr>
<td><b>{r['name']}</b></td>
<td>{r['pledge']}</td>
<td>{r['cost']}</td>
<td>{r['pledge_val']}</td>
<td>{r['loan']}</td>
<td>{r['days_rate']}</td>
<td>{r['interest']}</td>
<td>{r['targets']}</td>
<td>{r['target_val']}</td>
<td>{r['dividends']}</td>
<td>{arb_html}</td>
</tr>"""

    full_html = f"""
    <div style="overflow-x: auto;">
        <table style="width:100%; border-collapse:collapse; text-align:center; font-size:14px; background-color:#ffffff; color:#333333; border-radius:8px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <thead>
                <tr style="background-color:#1e88e5; color:#ffffff; font-weight:bold;">
                    <th style="padding:12px 8px;">專案名稱</th>
                    <th style="padding:12px 8px;">質押標的</th>
                    <th style="padding:12px 8px;">原始成本</th>
                    <th style="padding:12px 8px;">當前質押市值</th>
                    <th style="padding:12px 8px;">借款金額</th>
                    <th style="padding:12px 8px;">天數/利率</th>
                    <th style="padding:12px 8px;">至今利息</th>
                    <th style="padding:12px 8px;">轉投資標的</th>
                    <th style="padding:12px 8px;">轉投資市值</th>
                    <th style="padding:12px 8px;">已領股息</th>
                    <th style="padding:12px 8px;">🔥 實質淨套利</th>
                </tr>
            </thead>
            <tbody>
                {table_body}
            </tbody>
        </table>
    </div>
    """
    st.markdown(full_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("⚙️ 專案管理操作")
    col_sel, col_act1, col_act2, col_act3 = st.columns([3, 1, 1, 1])
    
    with col_sel:
        selected_proj_id = st.selectbox(
            "選擇專案：", 
            options=[p["id"] for p in st.session_state.pledges],
            format_func=lambda x: next((p["project_name"] for p in st.session_state.pledges if p["id"] == x), "")
        )
    
    with col_act1:
        st.write("")
        st.write("")
        if st.button("✏️ 編輯專案", use_container_width=True):
            target_p = next((p for p in st.session_state.pledges if p["id"] == selected_proj_id), None)
            if target_p:
                open_edit_form(target_p)
                st.rerun()

    with col_act2:
        st.write("")
        st.write("")
        if st.button("➕ 新建專案", use_container_width=True):
            open_edit_form(None)
            st.rerun()

    with col_act3:
        st.write("")
        st.write("")
        if st.button("🗑️ 刪除專案", use_container_width=True):
            st.session_state.pledges = [x for x in st.session_state.pledges if x["id"] != selected_proj_id]
            save_pledges_to_cloud(st.session_state.pledges)
            st.session_state.editing_id = None
            st.success("已成功刪除專案並同步 Google Sheets！")
            st.rerun()
else:
    st.info("目前尚無專案，請點選上方展開區建立你的第一筆套利專案！")
    if st.button("➕ 開始新增專案"):
        open_edit_form(None)
        st.rerun()
