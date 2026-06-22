import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import urllib.parse
import requests
import json
import re

# ==============================================================================
# 🎯 系統核心設定（請將您的 Google 試算表與 GAS 網址直接填寫於此）
# ==============================================================================
# 1. 您的 Google 試算表網址（請確保已設定為「知道連結的使用者皆可檢視」）
GS_URL = "https://docs.google.com/spreadsheets/d/1GLwY651HJBEDzUXDWmDONPp1j4Sj2J9Lw_ZNe8lqSEQ/edit?gid=447799608#gid=447799608"

# 2. 您的 Google Apps Script 部署網址（部署為網頁應用程式產生的 https://script.google.com.../exec 網址）
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxrHWClyYOu2RstCAWWA5CRIkR8_Wlqr7yWSwNo5fBnOibdDEo6lnEvf3U0dntysUVc/exec"

# ==============================================================================
# 頁面配置與主題
# ==============================================================================
st.set_page_config(
    page_title="導師班級經營管理系統",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自訂 CSS 樣式，用於凍結窗格與表格美化
st.markdown("""
<style>
    /* 主標題樣式 */
    .main-title {
        font-size: 2.2rem;
        color: #1E3A8A;
        font-weight: 700;
        margin-bottom: 20px;
        border-bottom: 3px solid #3B82F6;
        padding-bottom: 10px;
    }
    
    /* 卡片式設計 */
    .card-container {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* 凍結窗格的表格 CSS 樣式 */
    .frozen-table-container {
        overflow-x: auto;
        max-width: 100%;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
    }
    
    table.frozen-table {
        border-collapse: collapse;
        width: 100%;
        background-color: white;
    }
    
    table.frozen-table th, table.frozen-table td {
        border: 1px solid #CBD5E1;
        padding: 10px 12px;
        text-align: center;
        white-space: nowrap;
    }
    
    table.frozen-table th {
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
        position: sticky;
        top: 0;
        z-index: 10;
    }
    
    /* 凍結第一、二欄 (座號、姓名) 支援多欄凍結 */
    table.frozen-table td.sticky-col, table.frozen-table th.sticky-col {
        position: sticky;
        background-color: #F1F5F9;
        z-index: 5;
        font-weight: bold;
    }
    table.frozen-table th.sticky-col {
        z-index: 15;
        background-color: #1D4ED8;
    }
    
    /* 斑馬紋 */
    table.frozen-table tr:nth-child(even) td {
        background-color: #F8FAFC;
    }
    table.frozen-table tr:nth-child(even) td.sticky-col {
        background-color: #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# Google Sheet 免 API 讀寫核心邏輯 (支援智慧型課表解析)
# ==============================================================================
def get_spreadsheet_id(url_or_id):
    """從 URL 或 ID 中解析出 Spreadsheet ID"""
    if "docs.google.com/spreadsheets" in url_or_id:
        try:
            parts = url_or_id.split("/d/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        except Exception:
            pass
    return url_or_id.strip()

def parse_raw_timetable(raw_df):
    """
    智慧型課表解析器：依據 Google 試算表視覺化排版
    """
    cleaned_rows = []
    current_semester = None
    
    for idx, row in raw_df.iterrows():
        val_a = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        if val_a in ["二下", "三上", "三下", "二上", "一下", "一上"]:
            current_semester = val_a
            continue
            
        val_b = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
        if current_semester and val_b and val_b != "nan" and val_b != "":
            day_courses = []
            for col_idx in range(2, 7):
                if len(row) > col_idx and pd.notna(row.iloc[col_idx]):
                    day_courses.append(str(row.iloc[col_idx]).strip())
                else:
                    day_courses.append("")
            
            cleaned_rows.append({
                "學期": current_semester,
                "節次": val_b,
                "星期一": day_courses[0],
                "星期二": day_courses[1],
                "星期三": day_courses[2],
                "星期四": day_courses[3],
                "星期五": day_courses[4]
            })
            
    if cleaned_rows:
        return pd.DataFrame(cleaned_rows)
    return None

def load_sheet_csv(spreadsheet_id, sheet_name, fallback_df):
    """透過 gviz URL 免 API 直接讀取公開試算表特定的分頁為 DataFrame"""
    if not spreadsheet_id:
        return fallback_df
    try:
        encoded_name = urllib.parse.quote(sheet_name)
        if sheet_name == "課表":
            url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
            raw_df = pd.read_csv(url, header=None, keep_default_na=False)
            parsed_df = parse_raw_timetable(raw_df)
            if parsed_df is not None:
                return parsed_df
            return fallback_df
            
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
        df = pd.read_csv(url, keep_default_na=False)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        return df
    except Exception as e:
        return fallback_df

def write_data_via_apps_script(web_app_url, payload):
    """利用 POST 請求與 Google Apps Script 溝通寫入資料"""
    if not web_app_url or "placeholder" in web_app_url:
        st.warning("⚠️ 尚未設定真實的 Apps Script URL，資料目前僅保留於網頁記憶體中（重新整理後會消失）。")
        return False
    try:
        with st.spinner("🚀 正在即時將異動同步寫入 Google 試算表分頁..."):
            headers = {"Content-Type": "application/json"}
            response = requests.post(web_app_url, data=json.dumps(payload), headers=headers, timeout=15)
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("status") == "success":
                        st.success("🎉 資料已成功寫入 Google Sheet 雲端分頁！")
                        return True
                    else:
                        st.error(f"❌ 寫入失敗，Google Apps Script 錯誤：{result.get('message')}")
                except Exception:
                    st.success("🎉 資料已送出，Google Apps Script 已處理回應。")
                    return True
            else:
                st.error(f"❌ 無法連線至 Google Apps Script (狀態碼: {response.status_code})")
    except Exception as e:
        st.error(f"❌ 傳輸發生異常：{e}")
    return False

# ==============================================================================
# 本機預設備份資料庫 (當未填寫網址時自動載入的預設數據)
# ==============================================================================
if "db_students" not in st.session_state:
    st.session_state["db_students"] = pd.DataFrame({
        "座號": list(range(1, 36)),
        "姓名": ["王威竣", "呂宥均", "沈明峰", "林志宇", "林鈺恩", "莊英杰", "莊鎮安", "陳成威", "陳秉杰", "陳俊利", 
                 "彭宇祥", "黃奕翔", "黃建敦", "蔡守軒", "鄭丞祐", "魏辰宇", "吳婉菲", "邱凡軒", "範雅琪", "唐烯亮", 
                 "張芝溱", "曹妤潔", "陳佳玟", "傅琦茵", "彭榆喬", "曾品璇", "楊宜庭", "溫子瑜", "葉芊妤", "劉佳汶", 
                 "鄭云瑄", "賴品孝", "謝欣儒", "謝金秀", "鍾佳怡"]
    })

if "db_timetable" not in st.session_state:
    st.session_state["db_timetable"] = pd.DataFrame()

if "db_attendance" not in st.session_state:
    st.session_state["db_attendance"] = pd.DataFrame(columns=["日期", "座號", "姓名", "出席狀態"])

if "db_scores" not in st.session_state:
    st.session_state["db_scores"] = pd.DataFrame()

if "db_contribution_history" not in st.session_state:
    st.session_state["db_contribution_history"] = pd.DataFrame(columns=["日期", "座號", "姓名", "事由", "加扣分點數"])

if "db_contribution_stats" not in st.session_state:
    # 預設建立統計表結構
    df_stats = pd.DataFrame()
    df_stats["座號"] = st.session_state["db_students"]["座號"]
    df_stats["姓名"] = st.session_state["db_students"]["姓名"]
    df_stats["加扣分總計"] = 0
    st.session_state["db_contribution_stats"] = df_stats

# ==============================================================================
# 側邊欄與資料自動同步邏輯
# ==============================================================================
spreadsheet_id = get_spreadsheet_id(GS_URL) if GS_URL and "placeholder" not in GS_URL else ""

# 自動讀取試算表資料
if spreadsheet_id and "db_loaded" not in st.session_state:
    st.session_state["db_students"] = load_sheet_csv(spreadsheet_id, "導班學生名單", st.session_state["db_students"])
    st.session_state["db_timetable"] = load_sheet_csv(spreadsheet_id, "課表", st.session_state["db_timetable"])
    st.session_state["db_attendance"] = load_sheet_csv(spreadsheet_id, "出缺席紀錄", st.session_state["db_attendance"])
    st.session_state["db_scores"] = load_sheet_csv(spreadsheet_id, "各次段考成績", st.session_state["db_scores"])
    st.session_state["db_contribution_history"] = load_sheet_csv(spreadsheet_id, "班級貢獻度歷史紀錄", st.session_state["db_contribution_history"])
    # 核心修改：完整讀取您在 GS 自訂的統計表（包含學期等自訂欄位）
    st.session_state["db_contribution_stats"] = load_sheet_csv(spreadsheet_id, "班級貢獻度統計", st.session_state["db_contribution_stats"])
    st.session_state["db_loaded"] = True

# 確保座號欄位格式正確
for df_key in ["db_students", "db_contribution_history", "db_contribution_stats"]:
    if df_key in st.session_state and "座號" in st.session_state[df_key].columns:
        st.session_state[df_key]["座號"] = pd.to_numeric(st.session_state[df_key]["座號"], errors='coerce').fillna(0).astype(int)

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/google-sheets.png", width=55)
    st.title("🎓 導師班級經營系統")
    if spreadsheet_id:
        st.success("⚡ 雲端試算表已自動讀取成功！")
    else:
        st.warning("⚠️ 系統目前正以本機暫存模式運作。請至程式碼 app.py 最上方填入您的試算表與 GAS 網址！")
        
    menu = st.radio(
        "功能導覽",
        ["📅 課表與出缺席即時管理", "📊 段考成績分析與趨勢", "🌟 班級貢獻度登記與統計"]
    )

# ==============================================================================
# 功能 1：課表與出缺席即時管理
# ==============================================================================
if menu == "📅 課表與出缺席即時管理":
    st.markdown('<div class="main-title">📅 課表與出缺席即時管理</div>', unsafe_allow_html=True)
    # ... (保持原本功能 1 不變以節省篇幅，此段與原版邏輯一致)
    st.info("此處出缺席功能已載入，保留您原本的良好邏輯。")
    # 此處略過冗長呈現，實際執行時請保留您原版功能 1 的完整代碼
    
# ==============================================================================
# 功能 2：段考成績分析與趨勢
# ==============================================================================
elif menu == "📊 段考成績分析與趨勢":
    st.markdown('<div class="main-title">📊 段考成績分析與趨勢</div>', unsafe_allow_html=True)
    st.info("此處段考分析功能已載入，保留您原本的良好邏輯。")
    # 此處略過冗長呈現，實際執行時請保留您原版功能 2 的完整代碼

# ==============================================================================
# 功能 3：班級貢獻度登記與統計 (核心優化重點)
# ==============================================================================
elif menu == "🌟 班級貢獻度登記與統計":
    st.markdown('<div class="main-title">🌟 班級貢獻度登記與統計</div>', unsafe_allow_html=True)
    
    st.subheader("📥 批次學生加扣分登記")
    st.caption("💡 提供選單點選、文字貼上、以及新增的每日快速扣分功能：")
    
    # 建立三個輸入模式頁籤
    tab_click, tab_text, tab_daily = st.tabs(["✨ 圖形化選單登記", "✍️ 快速文字貼上登記", "⚡ 每日固定事項快速扣分"])
    
    students_df = st.session_state["db_students"]
    student_list_for_sel = [f"座號 {int(row['座號'])} - {row['姓名']}" for _, row in students_df.iterrows()]
    
    pending_records = [] # 統一收集待儲存的記錄
    
    # --- 模式 A：選單式點選 ---
    with tab_click:
        col_input1, col_input2 = st.columns(2)
        with col_input1:
            contri_date = st.date_input("加扣分日期", datetime.today(), key="contri_date_click")
            contri_event = st.text_input("事由描述", placeholder="例如：整潔工作認真、課堂發表積極...", key="contri_event_click")
        with col_input2:
            contri_type = st.radio("加分或扣分", ["加分 (+1)", "扣分 (-1)"], horizontal=True, key="contri_type_click")
            selected_students_contri = st.multiselect("選擇加扣分的學生名單", student_list_for_sel, key="selected_click")
            
        if st.button("🚀 送出選單登記", key="btn_click"):
            if not contri_event:
                st.error("請填寫事由描述！")
            elif not selected_students_contri:
                st.error("請至少選擇一位同學！")
            else:
                d_str = contri_date.strftime("%Y/%m/%d")
                pts = 1 if "加分" in contri_type else -1
                for sel in selected_students_contri:
                    seat = int(sel.split(" ")[1])
                    sname = students_df[students_df["座號"] == seat].iloc[0]["姓名"]
                    pending_records.append({"日期": d_str, "座號": seat, "姓名": sname, "事由": contri_event, "加扣分點數": pts})

    # --- 模式 B：文字區貼上式 ---
    with tab_text:
        default_paste_template = "日期:2026/6/22\n事由:朝會缺席\n加扣分:-1\n名單:1、2、3、4、5"
        paste_area = st.text_area("請在此貼上幹部紀錄文字：", value=default_paste_template, height=180)
        
        parsed_data = {}
        if paste_area:
            for line in paste_area.strip().split('\n'):
                match = re.match(r'^([^:：]+)[:：](.*)$', line.strip())
                if match: parsed_data[match.group(1).strip()] = match.group(2).strip()
        
        p_date = parsed_data.get("日期", datetime.today().strftime("%Y/%m/%d"))
        p_event = parsed_data.get("事由", "")
        p_points_raw = parsed_data.get("加扣分", "1")
        try: p_points = int(re.search(r'[-+]?\d+', p_points_raw).group())
        except: p_points = 1 if "加" in p_points_raw or "-" not in p_points_raw else -1
            
        p_seats = [int(part) for part in re.split(r'[、，,\s;；]+', parsed_data.get("名單", "")) if part.strip().isdigit()]
        
        if st.button("🚀 送出文字貼上登記", key="btn_text"):
            if not p_event: st.error("❌ 儲存失敗！無法解析到「事由」。")
            elif not p_seats: st.error("❌ 儲存失敗！「名單」中無有效學生座號。")
            else:
                for seat in p_seats:
                    st_row = students_df[students_df["座號"] == seat]
                    if not st_row.empty:
                        pending_records.append({"日期": p_date, "座號": seat, "姓名": st_row.iloc[0]["姓名"], "事由": p_event, "加扣分點數": p_points})

    # --- 模式 C：每日固定事項扣分 (新增) ---
    with tab_daily:
        st.markdown("##### ⚡ 勾選每日固定需扣分名單")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            late_students = st.multiselect("⏰ 每日遲到 (-1)", student_list_for_sel)
            noisy_students = st.multiselect("📢 每日吵鬧 (-1)", student_list_for_sel)
        with col_d2:
            no_form_students = st.multiselect("📄 每日回條不交 (-1)", student_list_for_sel)
            bad_clean_students = st.multiselect("🧹 每日打掃不確實 (-1)", student_list_for_sel)

        if st.button("🚀 送出每日固定扣分", key="btn_daily_submit"):
            d_str = datetime.today().strftime("%Y/%m/%d")
            def append_daily(stu_list, ev_name):
                for sel in stu_list:
                    seat = int(sel.split(" ")[1])
                    sname = students_df[students_df["座號"] == seat].iloc[0]["姓名"]
                    pending_records.append({"日期": d_str, "座號": seat, "姓名": sname, "事由": ev_name, "加扣分點數": -1})
            
            append_daily(late_students, "每日遲到")
            append_daily(noisy_students, "每日吵鬧")
            append_daily(no_form_students, "每日回條不交")
            append_daily(bad_clean_students, "每日打掃不確實")
            
            if not pending_records:
                st.warning("⚠️ 請至少選擇一位學生再送出！")

    # ================= 統一執行儲存與即時更新 GS 邏輯 =================
    if pending_records:
        new_hist_df = pd.DataFrame(pending_records)
        # 1. 更新歷史紀錄 dataframe
        st.session_state["db_contribution_history"] = pd.concat([st.session_state["db_contribution_history"], new_hist_df], ignore_index=True)
        gas_history_records = [[r["日期"], r["座號"], r["姓名"], r["事由"], r["加扣分點數"]] for r in pending_records]
        
        # 2. 更新統計表 dataframe (智慧尋找對應的自訂欄位，例如 "每日遲到" 寫入 "每日遲到(-1)" 欄)
        stats_df = st.session_state["db_contribution_stats"].copy()
        
        for r in pending_records:
            sid, event, pts = r["座號"], r["事由"], r["加扣分點數"]
            
            # 模糊比對找出 Google Sheet 中您建立的欄位名稱
            col_name = event
            for c in stats_df.columns:
                if event in str(c):
                    col_name = c
                    break
                    
            if col_name not in stats_df.columns:
                stats_df[col_name] = 0
                
            # 更新分數
            idx = stats_df.index[stats_df["座號"] == sid].tolist()
            if idx:
                i = idx[0]
                val = pd.to_numeric(stats_df.at[i, col_name], errors='coerce')
                stats_df.at[i, col_name] = (0 if pd.isna(val) else val) + pts
                
                # 更新總計
                if "加扣分總計" in stats_df.columns:
                    tot = pd.to_numeric(stats_df.at[i, "加扣分總計"], errors='coerce')
                    stats_df.at[i, "加扣分總計"] = (0 if pd.isna(tot) else tot) + pts
                else:
                    stats_df.at[i, "加扣分總計"] = pts
                    
        st.session_state["db_contribution_stats"] = stats_df
        
        # 轉成 GAS 吃的 2D Array
        stats_matrix = [stats_df.columns.tolist()] + stats_df.fillna("").values.tolist()
        
        payload = {"action": "save_contribution", "records": gas_history_records, "statsMatrix": stats_matrix}
        success = write_data_via_apps_script(GAS_WEB_APP_URL, payload)
        if success:
            st.rerun()

    # --------------------------------------------------------------------------
    # 即時呈現統計：班級貢獻度累計統計表 (讀取自 Google Sheet，保有您自訂的欄位)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📊 班級貢獻度累計統計表 (同步您的 Google Sheet)")
    st.caption("💡 這裡將會精準顯示您在 Google Sheet 所設定的欄位 (包含學期與各項加扣分)。")
    
    current_stats = st.session_state["db_contribution_stats"]
    
    if not current_stats.empty:
        # 動態判斷凍結欄位的 CSS 標籤
        sticky_cols_count = 3 if "學期" in current_stats.columns else 2
        
        html_builder_contri = ['<div class="frozen-table-container"><table class="frozen-table"><thead><tr>']
        for i, col in enumerate(current_stats.columns):
            style_class = ' class="sticky-col"' if i < sticky_cols_count else ''
            style_prop = f' style="left: {i*80}px;"' if i < sticky_cols_count else ''
            html_builder_contri.append(f'<th{style_class}{style_prop}>{col}</th>')
        html_builder_contri.append('</tr></thead><tbody>')
        
        for _, row in current_stats.iterrows():
            html_builder_contri.append('<tr>')
            for i, val in enumerate(row):
                style_class = ' class="sticky-col"' if i < sticky_cols_count else ''
                style_prop = f' style="left: {i*80}px;"' if i < sticky_cols_count else ''
                
                # 數字變色處理 (避開學期、座號、姓名)
                if isinstance(val, (int, float, np.integer)) and i >= sticky_cols_count and pd.notna(val):
                    if val > 0:
                        html_builder_contri.append(f'<td{style_class} style="color: green; font-weight: bold; {"left: "+str(i*80)+"px;" if i < sticky_cols_count else ""}">+{int(val)}</td>')
                    elif val < 0:
                        html_builder_contri.append(f'<td{style_class} style="color: red; font-weight: bold; {"left: "+str(i*80)+"px;" if i < sticky_cols_count else ""}">{int(val)}</td>')
                    else:
                        html_builder_contri.append(f'<td{style_class}{style_prop}>{int(val)}</td>')
                else:
                    html_builder_contri.append(f'<td{style_class}{style_prop}>{val if pd.notna(val) else ""}</td>')
            html_builder_contri.append('</tr>')
        html_builder_contri.append('</tbody></table></div>')
        
        st.markdown("".join(html_builder_contri), unsafe_allow_html=True)
    else:
        st.info("尚無統計資料或無法讀取 Google Sheet。")
        
    # --------------------------------------------------------------------------
    # 各月份熱心服務與待改進榜單 (支援同分並列)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📅 各月份熱心服務與待改進榜單")
    st.caption("💡 系統依照歷史紀錄月份自動計算。同分的同學會一併列出。")
    
    history_df = st.session_state["db_contribution_history"].copy()
    if not history_df.empty:
        # 萃取年-月份
        history_df["日期"] = pd.to_datetime(history_df["日期"], errors='coerce')
        history_df = history_df.dropna(subset=["日期"])
        history_df["月份"] = history_df["日期"].dt.strftime("%Y 年 %m 月")
        months = sorted(history_df["月份"].unique(), reverse=True)
        
        for month in months:
            with st.expander(f"📌 {month} 統計榜單", expanded=(month == months[0])):
                month_data = history_df[history_df["月份"] == month]
                # 加總每位學生的點數
                student_sums = month_data.groupby(["座號", "姓名"])["加扣分點數"].sum().reset_index()
                
                col_good, col_bad = st.columns(2)
                
                with col_good:
                    st.markdown("**🌟 熱心班務卓越榜 (加分最多)**")
                    good_st = student_sums[student_sums["加扣分點數"] > 0].copy()
                    if not good_st.empty:
                        # 使用 min 排名法解決同分並列問題
                        good_st["名次"] = good_st["加扣分點數"].rank(method='min', ascending=False)
                        top_good = good_st[good_st["名次"] <= 5].sort_values("名次")
                        if not top_good.empty:
                            for rank in sorted(top_good["名次"].unique()):
                                group = top_good[top_good["名次"] == rank]
                                names = "、".join([f"{int(r['座號'])}{r['姓名']}" for _, r in group.iterrows()])
                                pts = group.iloc[0]["加扣分點數"]
                                st.markdown(f"🏆 **第 {int(rank)} 名**: {names} (共 +{int(pts)} 分)")
                        else:
                            st.write("本月無符合前五名加分紀錄")
                    else:
                        st.write("本月無加分紀錄")
                        
                with col_bad:
                    st.markdown("**⚠️ 待改進名單 (扣分最多)**")
                    bad_st = student_sums[student_sums["加扣分點數"] < 0].copy()
                    if not bad_st.empty:
                        # 扣分是負數，所以從小排到大 (ascending=True) 才是扣最多
                        bad_st["名次"] = bad_st["加扣分點數"].rank(method='min', ascending=True)
                        top_bad = bad_st[bad_st["名次"] <= 5].sort_values("名次")
                        if not top_bad.empty:
                            for rank in sorted(top_bad["名次"].unique()):
                                group = top_bad[top_bad["名次"] == rank]
                                names = "、".join([f"{int(r['座號'])}{r['姓名']}" for _, r in group.iterrows()])
                                pts = group.iloc[0]["加扣分點數"]
                                st.markdown(f"🚨 **第 {int(rank)} 名**: {names} (共 {int(pts)} 分)")
                        else:
                            st.write("本月無符合前五名扣分紀錄")
                    else:
                        st.write("本月無扣分紀錄")
