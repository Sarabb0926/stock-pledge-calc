import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date, timedelta
import json
import requests

# 頁面配置
st.set_page_config(page_title="股票質押與實質套利筆記本", page_icon="📈", layout="wide")

# 自定義樣式
st.markdown("""
<style>
/* 新增專案橘白按鈕 */
div.stButton > button.orange-btn {
    background-color: #ff6b22 !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: bold !important;
    font-size: 15px !important;
    padding: 0.45rem 1.2rem !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 6px rgba(255, 107, 34, 0.3) !important;
    transition: all 0.2s ease !important;
}
div.stButton > button.orange-btn:hover {
    background-color: #e55a15 !important;
    color: #ffffff !important;
    box-shadow: 0 4px 10px rgba(255, 107, 34, 0.4) !important;
}

/* 彈窗儲存按鈕：白底藍字風格 */
div[data-testid="stFormSubmitButton"] > button {
    background-color: #ffffff !important;
    color: #1976d2 !important;
    border: 1.5px solid #1976d2 !important;
    font-weight: bold !important;
    font-size: 15px !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 4px rgba(25, 118, 210, 0.1) !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stFormSubmitButton"] > button:hover {
    background-color: #f0f7ff !important;
    color: #1565c0 !important;
    border-color: #1565c0 !important;
    box-shadow: 0 4px 8px rgba(25, 118, 210, 0.2) !important;
}

/* 卡片排版 */
.project-card-grid {
    flex-grow: 1;
    display: grid;
    grid-template-columns: 2.2fr 2fr 2fr 2.5fr 2fr;
    gap: 15px;
    align-items: center;
}

/* 狀態標籤樣式 */
.badge-active {
    background-color: #e8f5e9;
    color: #2e7d32;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid #c8e6c9;
    display: inline-block;
}

.badge-rollover {
    background-color: #fff3e0;
    color: #e65100;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid #ffe0b2;
    display: inline-block;
}

.badge-closed {
    background-color: #eceff1;
    color: #546e7a;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
    border: 1px solid #cfd8dc;
    display: inline-block;
}

@media (max-width: 900px) {
    .project-card-grid {
        grid-template-columns: 1fr;
        gap: 8px;
    }
}
</style>
""", unsafe_allow_html=True)

st.title("📈 股票質押與實質套利筆記本 (個人雲端版)")
st.caption("自動連動實時股價 · Google 雲端自動存檔 · 還款與展延追蹤 · 整戶維持率監控")

# ==============================================================================
# 🔗 自動從 Streamlit Secrets 讀取網址，若無設定則使用備用網址
# ==============================================================================
DEFAULT_API_URL = "https://script.google.com/macros/s/AKfycb...請貼上你的網址.../exec"
GSHEET_API_URL = st.secrets.get("GSHEET_API_URL", DEFAULT_API_URL)
# ==============================================================================

def normalize_tw_code(code_str: str) -> str:
    """自動修復被 Google Sheets 吞掉開頭 00 的台股/ETF 代號，並支援 0 或空白判定為無"""
    c = str(code_str).strip().upper()
    if not c or c in ["0", "NONE", "NULL", "無", "NAN", "''"]:
        return "0"
    c = c.replace("'", "")
    if c.isdigit():
        if len(c) <= 2:
            return c.zfill(4)
        elif len(c) == 3:
            return c.zfill(5)
    return c

def parse_sheet_date(date_val) -> date:
    """精確解析 Google Sheets 日期，自動校正 UTC 時區漂移問題"""
    if not date_val:
        return date.today()
    d_str = str(date_val).strip()
    try:
        if "T" in d_str:
            clean_str = d_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            dt_tw = dt + timedelta(hours=8)
            return dt_tw.date()
        else:
            return datetime.strptime(d_str.split()[0], "%Y-%m-%d").date()
    except Exception:
        try:
            return datetime.strptime(d_str[:10], "%Y-%m-%d").date()
        except Exception:
            return date.today()

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
                        code_norm = normalize_tw_code(t.get("target_code", ""))
                        if code_norm != "0":
                            fixed_targets.append({
                                "target_code": code_norm,
                                "target_sheets": float(t.get("target_sheets", 1.0)),
                                "target_cost": float(t.get("target_cost", 0)),
                                "dividends_received": float(t.get("dividends_received", 0))
                            })

                    p_id = int(row.get("id", 1))
                    raw_name = str(row.get("project_name", "")).strip()
                    
                    if not raw_name:
                        raw_name = f"專案 #{p_id}"
                    elif "T" in raw_name and "Z" in raw_name and len(raw_name) > 20:
                        raw_name = f"質押專案 #{p_id}"

                    parsed_list.append({
                        "id": p_id,
                        "project_name": raw_name,
                        "pledge_code": normalize_tw_code(row.get("pledge_code", "0")),
                        "pledge_sheets": float(row.get("pledge_sheets", 0.0)),
                        "pledge_cost": float(row.get("pledge_cost", 0)),
                        "loan_amount": float(row.get("loan_amount", 0)),
                        "repaid_amount": float(row.get("repaid_amount", 0)),
                        "repaid_interest": float(row.get("repaid_interest", 0)),
                        "rollover_count": int(row.get("rollover_count", 0)),
                        "repaid_date": parse_sheet_date(row.get("repaid_date")) if row.get("repaid_date") else None,
                        "interest_rate": float(row.get("interest_rate", 2.3)),
                        "pledge_date": parse_sheet_date(row.get("pledge_date")),
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
            p_code_norm = normalize_tw_code(p['pledge_code'])
            r_date_str = f"'{p['repaid_date'].strftime('%Y-%m-%d')}" if p.get("repaid_date") else ""
            flat_data.append({
                "id": int(p["id"]),
                "project_name": f"'{str(p['project_name']).strip()}",
                "pledge_code": f"'{p_code_norm}",
                "pledge_sheets": float(p["pledge_sheets"]),
                "pledge_cost": float(p["pledge_cost"]),
                "loan_amount": float(p["loan_amount"]),
                "repaid_amount": float(p.get("repaid_amount", 0)),
                "repaid_interest": float(p.get("repaid_interest", 0)),
                "rollover_count": int(p.get("rollover_count", 0)),
                "repaid_date": r_date_str,
                "interest_rate": float(p["interest_rate"]),
                "pledge_date": f"'{p['pledge_date'].strftime('%Y-%m-%d')}",
                "targets_json": json.dumps(p["targets"], ensure_ascii=False)
            })
        
        res = requests.post(GSHEET_API_URL, json=flat_data, timeout=8)
        if res.status_code == 200:
            return True, "雲端同步成功"
        return False, f"HTTP 狀態碼: {res.status_code}"
    except Exception as e:
        return False, str(e)

# --- 🚀 即時股價 API ---
@st.cache_data(ttl=180)
def get_stock_price(symbol: str) -> float:
    raw_code = normalize_tw_code(symbol)
    if not raw_code or raw_code == "0":
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

# --- 側邊欄：自定義維持率警戒值 ---
with st.sidebar:
    st.header("⚙️ 風險警戒設定")
    custom_warn_ratio = st.slider("⚠️ 警惕維持率警戒線 (%)", min_value=130, max_value=300, value=160, step=5)
    custom_danger_ratio = st.slider("🚨 追繳維持率警戒線 (%)", min_value=120, max_value=160, value=130, step=1)
    st.caption(f"目前設定：低於 {custom_danger_ratio}% 觸發追繳紅字警告，低於 {custom_warn_ratio}% 進入預警區。")

# --- 彈窗表單對話盒 ---
@st.dialog("📋 質押專案編輯器", width="large")
def project_form_dialog(edit_item=None):
    is_edit = edit_item is not None
    dlg_id = str(edit_item["id"]) if is_edit else "new"

    curr_targets = [dict(t) for t in edit_item.get("targets", [])] if is_edit else [{
        "target_code": "", "target_sheets": 1.0, "target_cost": 0, "dividends_received": 0
    }]
    if not curr_targets:
        curr_targets = [{"target_code": "", "target_sheets": 1.0, "target_cost": 0, "dividends_received": 0}]

    if f"cur_dlg_targets_{dlg_id}" not in st.session_state:
        st.session_state[f"cur_dlg_targets_{dlg_id}"] = curr_targets

    init_name = str(edit_item["project_name"]) if is_edit else ""
    if "T" in init_name and "Z" in init_name and len(init_name) > 20:
        init_name = f"專案 #{edit_item['id']}"

    st.markdown(f"#### {'✏️ 修改質押專案：' + init_name if is_edit else '➕ 建立全新質押專案'}")
    
    with st.form(key=f"pledge_modal_form_{dlg_id}"):
        p_name = st.text_input("專案名稱", value=init_name if init_name else "新質押專案", key=f"f_name_{dlg_id}")
        
        col1, col2 = st.columns(2)
        with col1:
            p_code_val = str(edit_item["pledge_code"]) if is_edit else ""
            if p_code_val == "0":
                p_code_val = "0"
            p_code = st.text_input("質押標的代號 (若無新押股票填 0 或留空)", value=p_code_val, key=f"f_code_{dlg_id}")
            p_sheets = st.number_input("質押張數 (無新押填 0)", min_value=0.0, value=float(edit_item["pledge_sheets"]) if is_edit else 0.0, step=0.5, key=f"f_sheets_{dlg_id}")
            p_cost = st.number_input("質押標的原始成本 (元)", min_value=0, value=int(edit_item["pledge_cost"]) if is_edit else 0, key=f"f_cost_{dlg_id}")
            p_rollover = st.selectbox("質押展延次數 (最多展延 2 次)", options=[0, 1, 2], index=int(edit_item.get("rollover_count", 0)) if is_edit else 0, key=f"f_roll_{dlg_id}")
        with col2:
            p_loan = st.number_input("原始借款金額 (元)", min_value=0, value=int(edit_item["loan_amount"]) if is_edit else 0, key=f"f_loan_{dlg_id}")
            p_rate = st.number_input("借款年利率 (%)", min_value=0.0, value=float(edit_item["interest_rate"]) if is_edit else 2.30, step=0.01, key=f"f_rate_{dlg_id}")
            p_date = st.date_input("質押開始日期", value=edit_item["pledge_date"] if is_edit else date.today(), key=f"f_date_{dlg_id}")
        
        st.markdown("---")
        st.markdown("##### 💵 還款與繳息紀錄")
        r_col1, r_col2, r_col3 = st.columns(3)
        with r_col1:
            p_repaid = st.number_input("已償還本金 (元)", min_value=0, value=int(edit_item.get("repaid_amount", 0)) if is_edit else 0, key=f"f_repaid_{dlg_id}")
        with r_col2:
            p_repaid_int = st.number_input("已償還利息 (元)", min_value=0, value=int(edit_item.get("repaid_interest", 0)) if is_edit else 0, key=f"f_repaid_int_{dlg_id}")
        with r_col3:
            default_r_date = edit_item.get("repaid_date") if (is_edit and edit_item.get("repaid_date")) else date.today()
            p_repaid_date = st.date_input("最後還款/結清日期", value=default_r_date, key=f"f_rdate_{dlg_id}")

        st.markdown("---")
        st.markdown("##### 🎯 轉投資標的設定")
        
        updated_targets = []
        target_list = st.session_state[f"cur_dlg_targets_{dlg_id}"]
        for idx, t in enumerate(target_list):
            st.markdown(f"**轉投資標的 #{idx+1}**")
            tc1, tc2, tc3, tc4 = st.columns(4)
            with tc1:
                t_code = st.text_input("標的代號", value=t.get("target_code", ""), key=f"d_tc_{dlg_id}_{idx}")
            with tc2:
                t_sheets = st.number_input("買入張數", min_value=0.01, value=float(t.get("target_sheets", 1.0)), step=0.5, key=f"d_ts_{dlg_id}_{idx}")
            with tc3:
                t_cost = st.number_input("買入總成本 (元)", min_value=0, value=int(t.get("target_cost", 0)), key=f"d_tcost_{dlg_id}_{idx}")
            with tc4:
                t_div = st.number_input("已領股息總額 (元)", min_value=0, value=int(t.get("dividends_received", 0)), key=f"d_tdiv_{dlg_id}_{idx}")
            
            updated_targets.append({
                "target_code": normalize_tw_code(t_code),
                "target_sheets": t_sheets,
                "target_cost": t_cost,
                "dividends_received": t_div
            })

        submit_save = st.form_submit_button("💾 儲存並同步至 Google Sheets", use_container_width=True)

        if submit_save:
            new_id = edit_item["id"] if is_edit else (max([p["id"] for p in st.session_state.pledges], default=0) + 1)
            valid_targets = [t for t in updated_targets if t["target_code"] not in ["0", ""]]
            
            final_name = p_name.strip() if p_name.strip() else f"專案 #{new_id}"
            clean_pledge_code = normalize_tw_code(p_code)
            new_project = {
                "id": new_id,
                "project_name": final_name,
                "pledge_code": clean_pledge_code,
                "pledge_sheets": p_sheets if clean_pledge_code != "0" else 0.0,
                "pledge_cost": p_cost if clean_pledge_code != "0" else 0,
                "loan_amount": p_loan,
                "repaid_amount": p_repaid,
                "repaid_interest": p_repaid_int,
                "rollover_count": p_rollover,
                "repaid_date": p_repaid_date if (p_repaid > 0 or p_repaid_int > 0) else None,
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
            if f"cur_dlg_targets_{dlg_id}" in st.session_state:
                del st.session_state[f"cur_dlg_targets_{dlg_id}"]
            st.success("✅ 專案已儲存並同步至雲端！")
            st.rerun()

    b_col1, b_col2, b_col3 = st.columns([1, 1, 1])
    with b_col1:
        if st.button("➕ 增加轉投資標的", key=f"btn_add_t_{dlg_id}", use_container_width=True):
            st.session_state[f"cur_dlg_targets_{dlg_id}"].append({
                "target_code": "", "target_sheets": 1.0, "target_cost": 0, "dividends_received": 0
            })
            st.rerun()
    with b_col2:
        if len(st.session_state[f"cur_dlg_targets_{dlg_id}"]) > 1:
            if st.button("🗑️ 減少轉投資標的", key=f"btn_rm_t_{dlg_id}", use_container_width=True):
                st.session_state[f"cur_dlg_targets_{dlg_id}"].pop()
                st.rerun()
    with b_col3:
        if is_edit:
            if st.button("❌ 刪除此專案", key=f"btn_del_p_{dlg_id}", use_container_width=True):
                st.session_state.pledges = [x for x in st.session_state.pledges if x["id"] != edit_item["id"]]
                save_pledges_to_cloud(st.session_state.pledges)
                if f"cur_dlg_targets_{dlg_id}" in st.session_state:
                    del st.session_state[f"cur_dlg_targets_{dlg_id}"]
                st.rerun()

# --- 資料計算與彙整 ---
total_collateral_value = 0.0
total_remaining_loan = 0.0
total_orig_loan = 0.0
total_repaid_amount = 0.0
total_repaid_interest = 0.0
total_interest_paid = 0.0
total_target_value = 0.0
total_target_cost = 0.0
total_dividends = 0.0

project_display_data = []

for item in st.session_state.pledges:
    p_code_norm = normalize_tw_code(item["pledge_code"])
    repaid_amt = item.get("repaid_amount", 0.0)
    repaid_int = item.get("repaid_interest", 0.0)
    rollover = int(item.get("rollover_count", 0))
    orig_loan = item["loan_amount"]
    remaining_loan = max(orig_loan - repaid_amt, 0.0)
    is_closed = (remaining_loan == 0 and orig_loan > 0)
    
    if p_code_norm == "0" or item.get("pledge_sheets", 0) == 0:
        current_collateral_val = 0.0
        p_price = 0.0
        pledge_display_str = "無 (動用舊額度)"
        pledge_val_str = "$0"
    else:
        p_price = get_stock_price(p_code_norm)
        current_collateral_val = p_price * item["pledge_sheets"] * 1000
        pledge_display_str = f"{p_code_norm} ({item['pledge_sheets']}張)"
        pledge_val_str = f"${current_collateral_val:,.0f} (@${p_price})"

    total_collateral_value += current_collateral_val
    total_remaining_loan += remaining_loan
    total_orig_loan += orig_loan
    total_repaid_amount += repaid_amt
    total_repaid_interest += repaid_int

    end_calc_date = item["repaid_date"] if (is_closed and item.get("repaid_date")) else date.today()
    days_pledged = max((end_calc_date - item["pledge_date"]).days, 1)
    
    accrued_interest = orig_loan * (item["interest_rate"] / 100.0) * (days_pledged / 365.0)
    unpaid_interest = max(accrued_interest - repaid_int, 0.0)
    total_interest_paid += unpaid_interest

    proj_target_val = 0.0
    proj_target_cost = 0.0
    proj_dividends = 0.0
    target_summary_list = []

    for t in item["targets"]:
        t_code_norm = normalize_tw_code(t.get("target_code", ""))
        if not t_code_norm or t_code_norm == "0":
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

    # 狀態標籤判定
    if is_closed:
        status_html = "<span class='badge-closed'>🟢 已結清</span>"
    elif rollover > 0:
        status_html = f"<span class='badge-rollover'>🔄 展延中#{rollover}</span>"
    else:
        status_html = "<span class='badge-active'>⚡ 進行中</span>"

    project_display_data.append({
        "item_obj": item,
        "id": item["id"],
        "name": str(item["project_name"]),
        "status_html": status_html,
        "is_closed": is_closed,
        "rollover": rollover,
        "pledge": pledge_display_str,
        "cost": f"${item['pledge_cost']:,.0f}" if p_code_norm != "0" else "$0",
        "pledge_val": pledge_val_str,
        "orig_loan": orig_loan,
        "repaid_amt": repaid_amt,
        "repaid_int": repaid_int,
        "remaining_loan": remaining_loan,
        "days_rate": f"{days_pledged}天 / {item['interest_rate']}%",
        "interest": f"${accrued_interest:,.0f}",
        "unpaid_interest": unpaid_interest,
        "targets": "<br>".join(target_summary_list) if target_summary_list else "無",
        "target_val": f"${proj_target_val:,.0f}",
        "dividends": f"${proj_dividends:,.0f}",
        "arbitrage": net_arbitrage
    })

# ⚖️ 券商標準公式：總負債 = 剩餘未償本金 + 累計未結利息
total_liability = total_remaining_loan + total_interest_paid
overall_maintenance_ratio = (total_collateral_value / total_liability * 100) if total_liability > 0 else 0
total_net_arbitrage = (total_target_value - total_target_cost + total_dividends) - (total_interest_paid + total_repaid_interest)

# --- 頂部儀表板 ---
st.divider()
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("🏛️ 整戶總抵押品市值", f"${total_collateral_value:,.0f}")
m2.metric("💳 剩餘未償借款", f"${total_remaining_loan:,.0f}", delta=f"已還本金 ${total_repaid_amount:,.0f}" if total_repaid_amount > 0 else None)

is_danger = overall_maintenance_ratio < custom_danger_ratio
is_warn = overall_maintenance_ratio < custom_warn_ratio

if is_danger:
    ratio_delta_text = f"🚨 低於 {custom_danger_ratio}% 追繳警告！"
elif is_warn:
    ratio_delta_text = f"⚠️ 警惕區域 (<{custom_warn_ratio}%)"
else:
    ratio_delta_text = f"✅ 安全範圍 (>{custom_warn_ratio}%)"

with m3:
    if is_danger or is_warn:
        st.markdown(f"""
        <div style="padding: 2px 0;">
            <div style="font-size: 14px; color: #555;">⚡ 整戶總維持率</div>
            <div style="font-size: 28px; font-weight: bold; color: #d93025; line-height: 1.2;">{overall_maintenance_ratio:.2f}%</div>
            <div style="font-size: 13px; color: #d93025; font-weight: 500; margin-top: 4px;">{ratio_delta_text}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.metric("⚡ 整戶總維持率", f"{overall_maintenance_ratio:.2f}%", delta=ratio_delta_text)

int_delta_str = f"已繳息 ${total_repaid_interest:,.0f}" if total_repaid_interest > 0 else f"總配息 ${total_dividends:,.0f}"
m4.metric("💸 累計未結利息", f"${total_interest_paid:,.0f}", delta=int_delta_str)
m5.metric("💰 實質淨套利", f"${total_net_arbitrage:,.0f}")

st.divider()

# --- 分頁系統 ---
tab_proj, tab_stress = st.tabs(["📋 質押專案彙整與還款追蹤", "🛡️ 質押維持率壓力測試 (情境模擬)"])

with tab_proj:
    header_col1, header_col2 = st.columns([4, 1.2])
    with header_col1:
        st.subheader("📋 專案明細列表")
    with header_col2:
        if st.button("➕ 新增質押專案", key="btn_add_proj", help="點擊建立新的質押套利專案", use_container_width=True):
            if "cur_dlg_targets_new" in st.session_state:
                del st.session_state["cur_dlg_targets_new"]
            project_form_dialog(None)

    if project_display_data:
        for r in project_display_data:
            arb_val = r["arbitrage"]
            if arb_val > 0:
                arb_color = "#ff4d4f"
                arb_sign = "+"
            elif arb_val < 0:
                arb_color = "#52c41a"
                arb_sign = "-"
            else:
                arb_color = "#333"
                arb_sign = ""

            if r["repaid_amt"] > 0:
                loan_display_html = f"<b>未還借款：</b>${r['remaining_loan']:,.0f}<br><span style='font-size:11px; color:#2e7d32;'>已還本金 ${r['repaid_amt']:,.0f}</span>"
            else:
                loan_display_html = f"<b>借款金額：</b>${r['orig_loan']:,.0f}"

            if r["repaid_int"] > 0:
                int_display_html = f"<b>未結利息：</b><span style='color:#d9534f;'>${r['unpaid_interest']:,.0f}</span><br><span style='font-size:11px; color:#1e88e5;'>已繳息 ${r['repaid_int']:,.0f}</span>"
            else:
                int_display_html = f"<b>利息：</b><span style='color:#d9534f;'>{r['interest']}</span>"

            c_card, c_btn = st.columns([11, 1.2])
            with c_card:
                card_html = f"""
                <div class="project-card-grid" style="background-color:#ffffff; border-radius:8px; padding:14px 18px; border:1px solid #e0e0e0; box-shadow:0 2px 5px rgba(0,0,0,0.03);">
                    <div>
                        <div style="margin-bottom: 4px;">{r['status_html']}</div>
                        <div style="font-size: 15px; font-weight: bold; color: #1e88e5; word-break: break-word;">{r['name']}</div>
                        <div style="font-size: 12px; color: #888; margin-top: 2px;">{r['days_rate']}</div>
                    </div>
                    <div>
                        <div style="font-size: 13px;"><b>質押：</b>{r['pledge']}</div>
                        <div style="font-size: 12px; color: #555; margin-top: 3px;"><b>市值：</b>{r['pledge_val']}</div>
                    </div>
                    <div>
                        <div style="font-size: 13px;">{loan_display_html}</div>
                        <div style="font-size: 12px; margin-top: 3px;">{int_display_html}</div>
                    </div>
                    <div>
                        <div style="font-size: 13px;"><b>轉投資：</b>{r['targets']}</div>
                        <div style="font-size: 12px; color: #555; margin-top: 3px;"><b>市值：</b>{r['target_val']}</div>
                    </div>
                    <div>
                        <div style="font-size: 12px; color: #2e7d32;"><b>股息：</b>{r['dividends']}</div>
                        <div style="font-size: 13px; margin-top: 3px;"><b>淨套利：</b><b style="color:{arb_color};">{arb_sign}${abs(arb_val):,.0f}</b></div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
            with c_btn:
                st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
                if st.button("✏️ 編輯", key=f"edit_btn_{r['id']}", use_container_width=True):
                    p_dlg_id = str(r['id'])
                    if f"cur_dlg_targets_{p_dlg_id}" in st.session_state:
                        del st.session_state[f"cur_dlg_targets_{p_dlg_id}"]
                    project_form_dialog(r["item_obj"])
    else:
        st.info("目前尚無專案，請點擊右上角「➕ 新增質押專案」按鈕建立第一筆資料！")

with tab_stress:
    st.subheader("🛡️ 質押維持率跌幅壓力測試")
    st.caption("模擬大盤回檔或質押標的下跌時，整戶擔保維持率的變化與追繳門檻。")
    
    st_c1, st_c2 = st.columns(2)
    with st_c1:
        drop_percent = st.slider("📉 模擬質押品下跌幅度 (%)", min_value=0, max_value=50, value=15, step=1)
    with st_c2:
        target_safe_ratio = st.slider("🎯 目標安全防守維持率 (%)", min_value=140, max_value=200, value=166, step=1)
    
    simulated_collateral_val = total_collateral_value * (1 - (drop_percent / 100.0))
    simulated_maintenance_ratio = (simulated_collateral_val / total_liability * 100) if total_liability > 0 else 0
    
    req_liability = (simulated_collateral_val / (target_safe_ratio / 100.0)) if target_safe_ratio > 0 else 0
    repay_needed = max(total_liability - req_liability, 0.0)

    sm1, sm2, sm3 = st.columns(3)
    sm1.metric("模擬後抵押品市值", f"${simulated_collateral_val:,.0f}", delta=f"-{drop_percent}%")
    
    sim_delta_str = "🚨 跌破追繳線！" if simulated_maintenance_ratio < custom_danger_ratio else ("⚠️ 進入警惕區" if simulated_maintenance_ratio < custom_warn_ratio else "✅ 仍屬安全")
    sm2.metric("模擬後整戶維持率", f"{simulated_maintenance_ratio:.2f}%", delta=sim_delta_str)
    sm3.metric("需補繳/還款金額 (回到目標線)", f"${repay_needed:,.0f}", help=f"讓維持率回到 {target_safe_ratio}% 所需償還的本金或補入現金。")
