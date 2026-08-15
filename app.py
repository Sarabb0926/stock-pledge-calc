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

def normalize_tw_code(code_str: str) -> str:
    """自動修復被 Google Sheets 吞掉開頭 00 的台股/ETF 代號"""
    c = str(code_str).strip().upper()
    if not c:
        return ""
    if c.isdigit():
        if len(c) <= 2:
            return c.zfill(4)   # 50 -> 0050, 56 -> 0056
        elif len(c) == 3:
            return c.zfill(5)   # 878 -> 00878, 919 -> 00919, 929 -> 00929
    return c

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
                    
                    fixed_targets = []
                    for t in targets:
                        fixed_targets.append({
                            "target_code": normalize_tw_code(t.get("target_code", "")),
                            "target_sheets": float(t.get("target_sheets", 1.0)),
                            "target_cost": float(t.get("target_cost", 0)),
                            "dividends_received": float(t.get("dividends_received", 0))
                        })

                    parsed_list.append({
                        "id": int(row.get("id", 1)),
                        "project_name": str(row.get("project_name", "質押專案")),
                        "pledge_code": normalize_tw_code(row.get("pledge_code", "")),
                        "pledge_sheets": float(row.get("pledge_sheets", 1.0)),
                        "pledge_cost": float(row.get("pledge_cost", 0)),
                        "loan_amount": float(row.get("loan_amount", 0)),
                        "interest_rate": float(row.get("interest_rate", 2.3)),
                        "pledge_date": datetime.strptime(str(row.get("pledge_date", "2025-01-01")).split("T")[0], "%Y-%m-%d").date(),
                        "targets": fixed_targets
                    })
                return parsed_list
    except Exception:
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
                "pledge_code": f"'{normalize_tw_code(p['pledge_code'])}",  # 加單引號強制 Google Sheets 視為純文字保留 00
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

# --- 🚀 超穩即時股價 API (Yahoo 原生 JSON + TWSE/TPEX 備援) ---
@st.cache_data(ttl=180)
def get_stock_price(symbol: str) -> float:
    raw_code = normalize_tw_code(symbol)
    if not raw_code:
        return 0.0

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    candidates = []
    if "." in raw_code:
        candidates = [raw_code]
    elif raw_code.isdigit() or any(c.isdigit() for c in raw_code):
        candidates = [f"{raw_code}.TW", f"{raw_code}.TWO"]
    else:
        candidates = [raw_code, f"{raw_code}.TW", f"{raw_code}.TWO"]

    # 1. 管道一：Yahoo Chart API 直接穿透
    for sym in candidates:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
            r = requests.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                res_data = r.json()
                result = res_data.get("chart", {}).get("result", [])
                if result:
                    meta = result[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    if price and float(price) > 0:
                        return round(float(price), 2)
                    
                    closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
                    valid_closes = [c for c in closes if c is not None and c > 0]
                    if valid_closes:
                        return round(float(valid_closes[-1]), 2)
        except Exception:
            pass

    # 2. 管道二：yfinance 套件備援
    for sym in candidates:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            if not hist.empty and "Close" in hist.columns:
                valid = hist["Close"].dropna()
                if not valid.empty and float(valid.iloc[-1]) > 0:
                    return round(float(valid.iloc[-1]), 2)
        except Exception:
            pass

    return 0.0

# --- 初始化 Session State 資料庫 ---
if "pledges" not in st.session_state:
    cloud_data = load_pledges_from_cloud()
    if cloud_data:
        st.session_state.pledges = cloud_data
    else:
        st.session_state.pledges = []

if "dialog_targets" not in st.session_state:
    st.session_state.dialog_targets = []

# --- 彈窗表單對話盒 ---
@st.dialog("📋 質押專案編輯器", width="large")
def project_form_dialog(edit_item=None):
    is_edit = edit_item is not None
    dlg_id = str(edit_item["id"]) if is_edit else "new"
    
    st.markdown(f"#### {'✏️ 修改質押專案：' + edit_item['project_name'] if is_edit else '➕ 建立全新質押專案'}")
    
    p_name = st.text_input("專案名稱", value=edit_item["project_name"] if is_edit else "新質押專案", key=f"f_name_{dlg_id}")
    col1, col2 = st.columns(2)
    with col1:
        p_code = st.text_input("質押標的代號 (如: 00878, 0050)", value=edit_item["pledge_code"] if is_edit else "", key=f"f_code_{dlg_id}")
        p_sheets = st.number_input("質押張數", min_value=0.01, value=float(edit_item["pledge_sheets"]) if is_edit else 1.0, step=0.5, key=f"f_sheets_{dlg_id}")
        p_cost = st.number_input("質押標的原始成本 (元)", min_value=0, value=int(edit_item["pledge_cost"]) if is_edit else 0, key=f"f_cost_{dlg_id}")
    with col2:
        p_loan = st.number_input("借款金額 (元)", min_value=0, value=int(edit_item["loan_amount"]) if is_edit else 0, key=f"f_loan_{dlg_id}")
        p_rate = st.number_input("借款年利率 (%)", min_value=0.0, value=float(edit_item["interest_rate"]) if is_edit else 2.30, step=0.01, key=f"f_rate_{dlg_id}")
        p_date = st.date_input("質押開始日期", value=edit_item["pledge_date"] if is_edit else date.today(), key=f"f_date_{dlg_id}")
    
    st.markdown("---")
    st.markdown("##### 🎯 轉投資標的設定 (可新增多筆)")
    
    updated_targets = []
    for idx, t in enumerate(st.session_state.dialog_targets):
        st.markdown(f"**轉投資標的 #{idx+1}**")
        tc1, tc2, tc3, tc4 = st.columns(4)
        with tc1:
            t_code = st.text_input("標的代號", value=t.get("target_code", ""), key=f"dlg_t_code_{dlg_id}_{idx}")
        with tc2:
            t_sheets = st.number_input("買入張數", min_value=0.01, value=float(t.get("target_sheets", 1.0)), step=0.5, key=f"dlg_t_sheets_{dlg_id}_{idx}")
        with tc3:
            t_cost = st.number_input("買入總成本 (元)", min_value=0, value=int(t.get("target_cost", 0)), key=f"dlg_t_cost_{dlg_id}_{idx}")
        with tc4:
            t_div = st.number_input("已領股息總額 (元)", min_value=0, value=int(t.get("dividends_received", 0)), key=f"dlg_t_div_{dlg_id}_{idx}")
        
        updated_targets.append({
            "target_code": normalize_tw_code(t_code),
            "target_sheets": t_sheets,
            "target_cost": t_cost,
            "dividends_received": t_div
        })

    btn_t1, btn_t2 = st.columns(2)
    with btn_t1:
        if st.button("➕ 新增一筆轉投資標的", use_container_width=True):
            st.session_state.dialog_targets.append({
                "target_code": "", "target_sheets": 1.0, "target_cost": 0, "dividends_received": 0
            })
            st.rerun()
    with btn_t2:
        if len(st.session_state.dialog_targets) > 1:
            if st.button("🗑️ 刪除最後一筆轉投資", use_container_width=True):
                st.session_state.dialog_targets.pop()
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 儲存並同步至 Google Sheets", type="primary", use_container_width=True):
        new_id = edit_item["id"] if is_edit else (max([p["id"] for p in st.session_state.pledges], default=0) + 1)
        valid_targets = [t for t in updated_targets if t["target_code"].strip() != ""]
        
        new_project = {
            "id": new_id,
            "project_name": p_name,
            "pledge_code": normalize_tw_code(p_code),
            "pledge_sheets": p_sheets,
            "pledge_cost": p_cost,
            "loan_amount": p_loan,
            "interest_rate": p_rate,
            "pledge_date": p_date,
            "targets": valid_targets
        }
        
        if is_edit:
            for i, p in enumerate(st.session_state.pledges):
                if p["id"] == edit_item["id"]:
                    st.session_state.pledges[i] = new_project
                    break
        else:
            st.session_state.pledges.append(new_project)
        
        save_pledges_to_cloud(st.session_state.pledges)
        st.success("✅ 專案已儲存並同步至雲端！")
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
    p_code_norm = normalize_tw_code(item["pledge_code"])
    p_price = get_stock_price(p_code_norm)
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
        t_code_norm = normalize_tw_code(t.get("target_code", ""))
        if not t_code_norm:
            continue
        t_price = get_stock_price(t_code_norm)
        c_val = t_price * t.get("target_sheets", 1.0) * 1000
        proj_target_val += c_val
        proj_target_cost += t.get("target_cost", 0)
        proj_dividends += t.get("dividends_received", 0)
        target_summary_list.append(f"{t_code_norm} ({t.get('target_sheets', 1.0)}張 @${t_price})")

    total_target_value += proj_target_val
    total_target_cost += proj_target_cost
    total_dividends += proj_dividends

    target_unrealized_gain = proj_target_val - proj_target_cost
    net_arbitrage = (target_unrealized_gain + proj_dividends) - accrued_interest

    table_rows.append({
        "id": item["id"],
        "name": item["project_name"],
        "pledge": f"{p_code_norm} ({item['pledge_sheets']}張)",
        "cost": f"${item['pledge_cost']:,.0f}",
        "pledge_val": f"${current_collateral_val:,.0f} (@${p_price})",
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
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("🏛️ 整戶總抵押品市值", f"${total_collateral_value:,.0f}")
m2.metric("💳 總借款金額", f"${total_loan_amount:,.0f}")
m3.metric("💸 累計總質借利息", f"${total_interest_paid:,.0f}", delta=f"總配息 ${total_dividends:,.0f}")

if overall_maintenance_ratio < 130:
    ratio_delta = "🚨 低於130% 追繳警告！"
elif overall_maintenance_ratio < 160:
    ratio_delta = "⚠️ 警惕區域 (<160%)"
else:
    ratio_delta = "✅ 安全範圍"

m4.metric("⚡ 整戶總維持率", f"{overall_maintenance_ratio:.2f}%", delta=ratio_delta)
m5.metric("💰 實質淨套利", f"${total_net_arbitrage:,.0f}")

st.divider()

# --- 彙整總表與操作按鈕 ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.subheader("📋 質押專案彙整總表")
with header_col2:
    if st.button("➕ 新增質押專案", type="primary", use_container_width=True):
        st.session_state.dialog_targets = [{
            "target_code": "",
            "target_sheets": 1.0,
            "target_cost": 0,
            "dividends_received": 0
        }]
        project_form_dialog(None)

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
    col_sel, col_act1, col_act2 = st.columns([3, 1, 1])
    
    with col_sel:
        selected_proj_id = st.selectbox(
            "選擇要操作的專案：", 
            options=[p["id"] for p in st.session_state.pledges],
            format_func=lambda x: next((p["project_name"] for p in st.session_state.pledges if p["id"] == x), "")
        )
    
    with col_act1:
        st.write("")
        st.write("")
        if st.button("✏️ 編輯選取專案", use_container_width=True):
            target_p = next((p for p in st.session_state.pledges if p["id"] == selected_proj_id), None)
            if target_p:
                st.session_state.dialog_targets = [dict(t) for t in target_p.get("targets", [])]
                if not st.session_state.dialog_targets:
                    st.session_state.dialog_targets = [{
                        "target_code": "", "target_sheets": 1.0, "target_cost": 0, "dividends_received": 0
                    }]
                project_form_dialog(target_p)

    with col_act2:
        st.write("")
        st.write("")
        if st.button("🗑️ 刪除選取專案", use_container_width=True):
            st.session_state.pledges = [x for x in st.session_state.pledges if x["id"] != selected_proj_id]
            save_pledges_to_cloud(st.session_state.pledges)
            st.success("已成功刪除專案並同步 Google Sheets！")
            st.rerun()
else:
    st.info("目前尚無專案，請點擊右上角「➕ 新增質押專案」按鈕建立第一筆資料！")
