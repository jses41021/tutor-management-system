import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import urllib.parse
import requests
import json
import re
import calendar

# ==============================================================================
# 🎯 系統核心設定（請將您的 Google 試算表與 GAS 網址直接填寫於此）
# ==============================================================================
# 1. 您的 Google 試算表網址
GS_URL = "https://docs.google.com/spreadsheets/d/1GLwY651HJBEDzUXDWmDONPp1j4Sj2J9Lw_ZNe8lqSEQ/edit?gid=447799608#gid=447799608"

# 2. 您的 Google Apps Script 部署網址
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxrHWClyYOu2RstCAWWA5CRIkR8_Wlqr7yWSwNo5fBnOibdDEo6lnEvf3U0dntysUVc/exec"

# 3. 定義學期常數與智慧型學期日期區間對應表 (依據 2024 年 8 月入學之高一學生推估)
SEMESTERS = ["高一上學期", "高一下學期", "高二上學期", "高二下學期", "高三上學期", "高三下學期"]
SEMESTER_MAPPING = {
    "高一上學期": "一上", "高一下學期": "一下",
    "高二上學期": "二上", "高二下學期": "二下",
    "高三上學期": "三上", "高三下學期": "三下"
}

SEMESTER_RANGES = {
    "高一上學期": (datetime(2024, 8, 1), datetime(2025, 1, 31)),
    "高一下學期": (datetime(2025, 2, 1), datetime(2025, 7, 31)),
    "高二上學期": (datetime(2025, 8, 1), datetime(2026, 1, 31)),
    "高二下學期": (datetime(2026, 2, 1), datetime(2026, 7, 31)),
    "高三上學期": (datetime(2026, 8, 1), datetime(2027, 1, 31)),
    "高三下學期": (datetime(2027, 2, 1), datetime(2027, 7, 31)),
}

# ==============================================================================
# 智慧型日期學期判定核心邏輯
# ==============================================================================
def get_semester_by_date(dt):
    """依據傳入的 datetime 或是 date 物件，自動判定所屬學期"""
    if pd.isna(dt):
        return "高二下學期"
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt.replace("-", "/").split(" ")[0], "%Y/%m/%d")
        except:
            return "高二下學期"  # 預設相容
    elif hasattr(dt, "to_pydatetime"):
        dt = dt.to_pydatetime()
    elif isinstance(dt, datetime):
        pass
    else:
        try:
            dt = datetime(dt.year, dt.month, dt.day)
        except:
            return "高二下學期"

    for sem, (start_dt, end_dt) in SEMESTER_RANGES.items():
        if start_dt <= dt <= end_dt:
            return sem
    return "高二下學期"  # 若超出邊界則預設

def is_date_in_semester(date_str, semester_name):
    """檢查特定的日期字串是否屬於該學期的時間區間"""
    try:
        date_str_clean = str(date_str).replace("-", "/").split(" ")[0]
        dt = datetime.strptime(date_str_clean, "%Y/%m/%d")
        if semester_name in SEMESTER_RANGES:
            start_dt, end_dt = SEMESTER_RANGES[semester_name]
            return start_dt <= dt <= end_dt
    except Exception:
        pass
    return False

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
    .main-title { font-size: 2.2rem; color: #1E3A8A; font-weight: 700; margin-bottom: 20px; border-bottom: 3px solid #3B82F6; padding-bottom: 10px; }
    /* 卡片式設計 */
    .card-container { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
    /* 凍結窗格的表格 CSS 樣式 */
    .frozen-table-container { overflow-x: auto; max-width: 100%; border: 1px solid #E2E8F0; border-radius: 8px; margin-bottom: 20px; }
    table.frozen-table { border-collapse: collapse; width: 100%; background-color: white; }
    table.frozen-table th, table.frozen-table td { border: 1px solid #CBD5E1; padding: 10px 12px; text-align: center; white-space: nowrap; }
    table.frozen-table th { background-color: #3B82F6; color: white; font-weight: bold; position: sticky; top: 0; z-index: 10; }
    /* 動態凍結欄位 */
    table.frozen-table td.sticky-col, table.frozen-table th.sticky-col { position: sticky; z-index: 5; font-weight: bold; }
    table.frozen-table th.sticky-col { z-index: 15; background-color: #1D4ED8; color: white; }
    /* 斑馬紋 */
    table.frozen-table tr:nth-child(even) td { background-color: #F8FAFC; }
    /* 月曆 CSS */
    .cal-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin-bottom: 20px;}
    .cal-table th { background-color: #1E3A8A; color: white; padding: 8px; text-align: center; border: 1px solid #CBD5E1; }
    .cal-table td { border: 1px solid #CBD5E1; height: 110px; vertical-align: top; padding: 6px; background-color: white; }
    .cal-table td.other-month { background-color: #F8FAFC; }
    .cal-date { font-weight: bold; margin-bottom: 6px; display: block; color: #333; font-size: 1.1rem; }
    .cal-other-date { color: #94A3B8; }
    .cal-event { font-size: 0.85rem; color: #DC2626; background-color: #FEE2E2; padding: 3px 6px; border-radius: 4px; margin-bottom: 4px; display: block; line-height: 1.3; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# Google Sheet 免 API 讀寫核心邏輯 (支援智慧型課表解析與空白標題防禦)
# ==============================================================================
def get_spreadsheet_id(url_or_id):
    if "docs.google.com/spreadsheets" in url_or_id:
        try:
            parts = url_or_id.split("/d/")
            if len(parts) > 1: return parts[1].split("/")[0]
        except Exception: pass
    return url_or_id.strip()

def parse_raw_timetable(raw_df):
    cleaned_rows = []
    current_semester = None
    for idx, row in raw_df.iterrows():
        val_a = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        if val_a in ["二下", "三上", "三下", "二上", "一下", "一上", "高一上學期", "高一下學期", "高二上學期", "高二下學期", "高三上學期", "高三下學期"]:
            current_semester = val_a
            continue
        val_b = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
        if current_semester and val_b and val_b != "nan" and val_b != "":
            day_courses = [str(row.iloc[col_idx]).strip() if len(row) > col_idx and pd.notna(row.iloc[col_idx]) else "" for col_idx in range(2, 7)]
            cleaned_rows.append({"學期": current_semester, "節次": val_b, "星期一": day_courses[0], "星期二": day_courses[1], "星期三": day_courses[2], "星期四": day_courses[3], "星期五": day_courses[4]})
    if cleaned_rows: return pd.DataFrame(cleaned_rows)
    return None

def load_sheet_csv(spreadsheet_id, sheet_name, fallback_df):
    if not spreadsheet_id: return fallback_df
    try:
        encoded_name = urllib.parse.quote(sheet_name)
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
        raw_df = pd.read_csv(url, header=None if sheet_name == "課表" else 'infer', keep_default_na=False)
        
        if sheet_name == "課表":
            parsed_df = parse_raw_timetable(raw_df)
            return parsed_df if parsed_df is not None else fallback_df
            
        # =================【位置標題安全機制】=================
        if sheet_name == "班級貢獻度歷史紀錄":
            while len(raw_df.columns) < 6:
                raw_df[f"Col_{len(raw_df.columns)}"] = ""
            new_cols = list(raw_df.columns)
            new_cols[0] = "日期"
            new_cols[1] = "座號"
            new_cols[2] = "姓名"
            new_cols[3] = "事由"
            new_cols[4] = "加扣分點數"
            new_cols[5] = "學期"
            raw_df.columns = new_cols
            return raw_df
            
        if sheet_name == "出缺席紀錄":
            while len(raw_df.columns) < 4:
                raw_df[f"Col_{len(raw_df.columns)}"] = ""
            new_cols = list(raw_df.columns)
            new_cols[0] = "日期"
            new_cols[1] = "座號"
            new_cols[2] = "姓名"
            new_cols[3] = "出席狀態"
            raw_df.columns = new_cols
            return raw_df

        raw_df = raw_df.loc[:, ~raw_df.columns.str.contains('^Unnamed')]
        return raw_df
    except Exception: return fallback_df

def write_data_via_apps_script(web_app_url, payload):
    if not web_app_url or "placeholder" in web_app_url:
        st.warning("⚠️ 尚未設定真實的 Apps Script URL，資料目前僅保留於網頁記憶體中。")
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
                    else: st.error(f"❌ 寫入失敗，Google Apps Script 錯誤：{result.get('message')}")
                except Exception:
                    st.success("🎉 資料已送出，Google Apps Script 已處理回應。")
                    return True
            else: st.error(f"❌ 無法連線至 Google Apps Script (狀態碼: {response.status_code})")
    except Exception as e: st.error(f"❌ 傳輸發生異常：{e}")
    return False

# ==============================================================================
# 本機預設備份資料庫
# ==============================================================================
if "db_students" not in st.session_state:
    st.session_state["db_students"] = pd.DataFrame({"座號": list(range(1, 36)), "姓名": ["王威竣", "呂宥均", "沈明峰", "林志宇", "林鈺恩", "莊英杰", "莊鎮安", "陳成威", "陳秉杰", "陳俊利", "彭宇祥", "黃奕翔", "黃建敦", "蔡守軒", "鄭丞祐", "魏辰宇", "吳婉菲", "邱凡軒", "範雅琪", "唐烯亮", "張芝溱", "曹妤潔", "陳佳玟", "傅琦茵", "彭榆喬", "曾品璇", "楊宜庭", "溫子瑜", "葉芊妤", "劉佳汶", "鄭云瑄", "賴品孝", "謝欣儒", "謝金秀", "鍾佳怡"]})
if "db_timetable" not in st.session_state:
    st.session_state["db_timetable"] = pd.DataFrame([{"學期": "高二下學期", "節次": "第一節", "星期一": "數學", "星期二": "體育", "星期三": "國防", "星期四": "數學", "星期五": "社會探究"}])
if "db_attendance" not in st.session_state:
    st.session_state["db_attendance"] = pd.DataFrame(columns=["日期", "座號", "姓名", "出席狀態"])
if "db_scores" not in st.session_state:
    exams = ["高二上第一次段考", "高二上第二次段考", "高二上第三次段考"]
    score_data = []
    np.random.seed(42)
    students = st.session_state["db_students"]
    for ex in exams:
        for idx, row in students.iterrows():
            score_data.append({
                "考試類別": ex, "座號": int(row["座號"]), "姓名": row["姓名"],
                "國文": np.round(np.random.normal(65, 10), 1), "英文": np.round(np.random.normal(60, 12), 1),
                "數學": np.round(np.random.normal(55, 15), 1), "歷史": np.round(np.random.normal(70, 8), 1),
                "地理": np.round(np.random.normal(68, 10), 1), "公民": np.round(np.random.normal(72, 9), 1)
            })
    st.session_state["db_scores"] = pd.DataFrame(score_data)
if "db_contribution_history" not in st.session_state:
    st.session_state["db_contribution_history"] = pd.DataFrame(columns=["日期", "座號", "姓名", "事由", "加扣分點數", "學期"])
if "db_contribution_stats" not in st.session_state:
    df_stats = pd.DataFrame()
    df_stats["學期"] = "高二下學期"
    df_stats["座號"] = st.session_state["db_students"]["座號"]
    df_stats["姓名"] = st.session_state["db_students"]["姓名"]
    df_stats["加扣分總計"] = 0.0
    st.session_state["db_contribution_stats"] = df_stats

# ==============================================================================
# 側邊欄與資料自動同步邏輯
# ==============================================================================
spreadsheet_id = get_spreadsheet_id(GS_URL) if GS_URL and "placeholder" not in GS_URL else ""

if spreadsheet_id and "db_loaded" not in st.session_state:
    st.session_state["db_students"] = load_sheet_csv(spreadsheet_id, "導班學生名單", st.session_state["db_students"])
    st.session_state["db_timetable"] = load_sheet_csv(spreadsheet_id, "課表", st.session_state["db_timetable"])
    st.session_state["db_attendance"] = load_sheet_csv(spreadsheet_id, "出缺席紀錄", st.session_state["db_attendance"])
    st.session_state["db_scores"] = load_sheet_csv(spreadsheet_id, "各次段考成績", st.session_state["db_scores"])
    st.session_state["db_contribution_history"] = load_sheet_csv(spreadsheet_id, "班級貢獻度歷史紀錄", st.session_state["db_contribution_history"])
    st.session_state["db_contribution_stats"] = load_sheet_csv(spreadsheet_id, "班級貢獻度統計", st.session_state["db_contribution_stats"])
    st.session_state["db_loaded"] = True

# 【防禦機制】：確保載入後的資料結構完整性，避免因為 Sheet 欄位缺失導致 KeyError
if "db_contribution_history" in st.session_state:
    history_required_cols = ["日期", "座號", "姓名", "事由", "加扣分點數", "學期"]
    for col in history_required_cols:
        if col not in st.session_state["db_contribution_history"].columns:
            st.session_state["db_contribution_history"][col] = 0.0 if col == "加扣分點數" else ""

if "db_contribution_stats" in st.session_state:
    stats_required_cols = ["學期", "座號", "姓名", "加扣分總計"]
    for col in stats_required_cols:
        if col not in st.session_state["db_contribution_stats"].columns:
            st.session_state["db_contribution_stats"][col] = 0.0 if col in ["座號", "加扣分總計"] else ""

for df_key in ["db_students", "db_contribution_history", "db_contribution_stats"]:
    if df_key in st.session_state and "座號" in st.session_state[df_key].columns:
        st.session_state[df_key]["座號"] = pd.to_numeric(st.session_state[df_key]["座號"], errors='coerce').fillna(0).astype(int)

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/google-sheets.png", width=55)
    st.title("🎓 導師班級經營系統")
    if spreadsheet_id: st.success("⚡ 雲端資料已同步成功！")
    
    st.markdown("---")
    # 全局學期選擇器 (預設為高二下學期)
    global_selected_semester = st.selectbox("🎯 全局設定：選擇目前學期", SEMESTERS, index=3)
    
    st.markdown("---")
    menu = st.radio("功能導覽", ["📅 課表與出缺席即時管理", "📊 段考成績分析與趨勢", "🌟 班級貢獻度登記與統計"])

# ==============================================================================
# 功能 1：課表與出缺席即時管理 (全面升級版)
# ==============================================================================
if menu == "📅 課表與出缺席即時管理":
    st.markdown(f'<div class="main-title">📅 課表與出缺席即時管理 <span style="font-size:1.2rem; color:gray;">({global_selected_semester})</span></div>', unsafe_allow_html=True)
    
    today_date = st.date_input("點名日期", datetime.today())
        
    timetable_df = st.session_state["db_timetable"]
    sem_timetable = pd.DataFrame()
    if not timetable_df.empty and "學期" in timetable_df.columns:
        short_sem = SEMESTER_MAPPING.get(global_selected_semester, global_selected_semester)
        sem_timetable = timetable_df[timetable_df["學期"].astype(str).isin([global_selected_semester, short_sem])]

    if sem_timetable.empty:
        st.info(f"💡 目前尚未在「課表」分頁中找到【{global_selected_semester}】的資料。請確認 Google Sheet 中課表的學期標記是否正確。")

    # =================每日點名登記介面 (增量新增模式)=================
    st.markdown("---")
    st.subheader(f"📝 {today_date.strftime('%Y/%m/%d')} 每日缺席登記")
    st.caption("💡 採用「增量紀錄模式」：下方會顯示今日已登記請假的名單，您只需在下方選單**新增**後來請假的同學即可，歷史紀錄完全不會被覆蓋！")
    
    students_df = st.session_state["db_students"]
    student_options = [f"座號 {int(row['座號'])} - {row['姓名']}" for _, row in students_df.iterrows()]
    
    today_str = today_date.strftime("%Y/%m/%d")
    today_records = pd.DataFrame()
    
    # 顯示今日已經儲存過的缺席紀錄
    if "db_attendance" in st.session_state and not st.session_state["db_attendance"].empty:
        today_attn = st.session_state["db_attendance"].copy()
        today_attn["日期_norm"] = today_attn["日期"].astype(str).str.replace("-", "/")
        today_records = today_attn[today_attn["日期_norm"] == today_str]
        
        # 排除掉舊版殘留的「出席」紀錄，只顯示真正有缺席的紀錄
        today_absents = today_records[(today_records["出席狀態"].str.strip() != "出席") & (today_records["出席狀態"].str.strip() != "")]
        
        if not today_absents.empty:
            st.markdown("##### 📌 今日已登記之缺席/請假紀錄")
            st.dataframe(today_absents[["座號", "姓名", "出席狀態"]], hide_index=True)
        else:
            st.info("今日目前尚無任何缺席紀錄。")

    st.markdown("##### ➕ 新增缺席/請假學生")
    absent_selections = st.multiselect(
        "請選擇要「新增」缺席或請假的學生 (已在上方列表的同學無需重複選取)", 
        student_options
    )
    
    student_absent_details = {}
    days_of_week = ["星期一", "星期二", "星期三", "星期四", "星期五"]
    
    if absent_selections:
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.markdown("##### ⚙️ 設定缺席細節 (若未勾選節次，系統預設為全日缺席)")
        
        weekday_num = today_date.weekday()
        available_periods = []
        if weekday_num < 5:
            weekday_name = days_of_week[weekday_num]
            if not sem_timetable.empty and weekday_name in sem_timetable.columns:
                today_timetable = sem_timetable[sem_timetable[weekday_name].str.strip() != ""]
                available_periods = today_timetable["節次"].tolist()
        
        cols_abs = st.columns(3)
        for idx, sel in enumerate(absent_selections):
            with cols_abs[idx % 3]:
                stu_name = sel.split(" - ")[1]
                
                if available_periods:
                    period_sel = st.multiselect(
                        f"【{stu_name}】缺席節次", 
                        available_periods, 
                        key=f"abs_{sel}"
                    )
                    if period_sel:
                        student_absent_details[sel] = "缺席節次:" + ",".join(period_sel)
                    else:
                        student_absent_details[sel] = "全日缺席"
                else:
                    student_absent_details[sel] = "全日缺席"
                    st.caption(f"{stu_name} (今日無課表，記為全日缺席)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button("💾 儲存新增的出缺席紀錄"):
        if not absent_selections:
            st.warning("⚠️ 請先選擇要新增的缺席學生再儲存。")
        else:
            new_records = []
            
            for sel in absent_selections:
                stu_seat = int(sel.split(" ")[1])
                stu_name = sel.split(" - ")[1]
                status = student_absent_details.get(sel, "全日缺席")
                
                new_records.append({
                    "日期": today_date.strftime("%Y/%m/%d"), 
                    "座號": stu_seat, 
                    "姓名": stu_name, 
                    "出席狀態": status
                })
            
            new_df = pd.DataFrame(new_records)
            
            # 將新紀錄附加到現有的總紀錄中 (純新增，不刪除舊紀錄)
            st.session_state["db_attendance"] = pd.concat([st.session_state["db_attendance"], new_df], ignore_index=True)
            
            # 傳送給 GAS 時，把今日「所有的紀錄」傳過去以防 GAS 取代整天機制
            updated_today_records = st.session_state["db_attendance"][
                st.session_state["db_attendance"]["日期"].astype(str).str.replace("-", "/") == today_str
            ]
            gas_records = updated_today_records[["日期", "座號", "姓名", "出席狀態"]].values.tolist()
            
            payload = {"action": "save_attendance", "date": today_str, "records": gas_records}
            if write_data_via_apps_script(GAS_WEB_APP_URL, payload):
                st.rerun()

    # =================缺席月曆視圖=================
    st.markdown("---")
    st.subheader("📅 缺席狀況月曆")
    
    attn_df = st.session_state["db_attendance"]
    daily_absent_dict = {}
    if not attn_df.empty:
        for _, row in attn_df.iterrows():
            date_str = str(row["日期"]).replace("-", "/")
            status = str(row["出席狀態"]).strip()
            if status != "出席":
                if date_str not in daily_absent_dict: daily_absent_dict[date_str] = []
                detail_str = ""
                if status.startswith("缺席節次:"): detail_str = f" ({status.split(':')[1]})"
                elif status == "缺席" or status == "全日缺席": detail_str = " (全日)"
                daily_absent_dict[date_str].append(row["姓名"] + detail_str)

    col_cal1, col_cal2 = st.columns([1, 3])
    with col_cal1:
        cal_year = st.selectbox("📅 選擇年份", [datetime.today().year, datetime.today().year - 1, datetime.today().year - 2])
        cal_month = st.selectbox("📆 選擇月份", list(range(1, 13)), index=datetime.today().month - 1)
    
    cal = calendar.Calendar(firstweekday=6) # 0=星期一, 6=星期日
    month_days = cal.monthdatescalendar(cal_year, cal_month)
    
    html_cal = """<table class="cal-table"><tr><th>星期日</th><th>星期一</th><th>星期二</th><th>星期三</th><th>星期四</th><th>星期五</th><th>星期六</th></tr>"""
    for week in month_days:
        html_cal += "<tr>"
        for day in week:
            is_other_month = day.month != cal_month
            td_class = "other-month" if is_other_month else ""
            date_class = "cal-other-date" if is_other_month else ""
            date_str = day.strftime("%Y/%m/%d")
            
            absent_list = daily_absent_dict.get(date_str, [])
            absent_html = "".join([f"<span class='cal-event'>{p}</span>" for p in absent_list])
            
            html_cal += f"<td class='{td_class}'><span class='cal-date {date_class}'>{day.day}</span>{absent_html if not is_other_month else ''}</td>"
        html_cal += "</tr>"
    html_cal += "</table>"
    
    st.markdown(html_cal, unsafe_allow_html=True)

    # =================各科目「缺席次數」與「累積缺席節數」統計表=================
    st.markdown("---")
    st.subheader(f"📊 每位學生各科目「實際缺席次數」與「累積缺席節數」累計表 ({global_selected_semester})")
    st.caption("💡 系統自動根據請假狀態（全日/特定節次）與課表比對，並**依據日期智慧判定學期區間**，精準計算缺席的節數。")
    
    all_subjects = set()
    for day in days_of_week:
        if not sem_timetable.empty and day in sem_timetable.columns:
            subjects_list = sem_timetable[day].replace('', np.nan).dropna().tolist()
            for sub in subjects_list:
                sub_clean = str(sub).strip()
                if sub_clean and sub_clean != "nan" and sub_clean != "朝會" and "自主學習" not in sub_clean and "彈性學習" not in sub_clean:
                    all_subjects.add(sub_clean)
                
    sorted_subjects = sorted(list(all_subjects))
    
    attendance_stats = pd.DataFrame(0, index=students_df["座號"], columns=["累積缺席節數"] + sorted_subjects)
    attendance_stats.insert(0, "姓名", students_df["姓名"].values)
    attendance_stats.insert(0, "座號", students_df["座號"].values)
    
    if not attn_df.empty:
        for _, row in attn_df.iterrows():
            date_str = str(row["日期"])
            
            # 【重要智慧機制】：僅運算符合當前全局所選學期日期區間的出缺席紀錄！
            if not is_date_in_semester(date_str, global_selected_semester):
                continue
                
            status = str(row["出席狀態"]).strip()
            seat = int(row["座號"])
            
            if status == "出席" or seat not in attendance_stats["座號"].values:
                continue
            try:
                dt = datetime.strptime(date_str.replace("-", "/"), "%Y/%m/%d")
                weekday_num = dt.weekday()
                if weekday_num >= 5: continue
                weekday_name = days_of_week[weekday_num]
                
                if not sem_timetable.empty and weekday_name in sem_timetable.columns:
                    day_timetable = sem_timetable[["節次", weekday_name]].replace('', np.nan).dropna(subset=[weekday_name])
                    
                    absent_periods = []
                    if status == "缺席" or status == "全日缺席":
                        absent_periods = day_timetable["節次"].tolist()
                    elif status.startswith("缺席節次:"):
                        absent_periods = status.split(":")[1].split(",")
                        
                    for period in absent_periods:
                        subj_row = day_timetable[day_timetable["節次"] == period]
                        if not subj_row.empty:
                            subj = str(subj_row.iloc[0][weekday_name]).strip()
                            # 缺席一節課，累積缺席節數 + 1
                            attendance_stats.loc[attendance_stats["座號"] == seat, "累積缺席節數"] += 1
                            # 對應科目缺席次數 + 1
                            if subj in attendance_stats.columns:
                                attendance_stats.loc[attendance_stats["座號"] == seat, subj] += 1
            except Exception:
                continue
                
    if not attendance_stats.empty and len(attendance_stats.columns) > 3:
        html_builder = ['<div class="frozen-table-container"><table class="frozen-table"><thead><tr>']
        col_widths = [60, 100, 140]
        left_pos = [0, 60, 160]
        
        for i, col in enumerate(attendance_stats.columns):
            if i < 3:
                html_builder.append(f'<th class="sticky-col" style="left: {left_pos[i]}px; min-width:{col_widths[i]}px; {"background-color: #D97706;" if i==2 else ""}">{col}</th>')
            else:
                html_builder.append(f'<th>{col}</th>')
        html_builder.append('</tr></thead><tbody>')
        for _, row in attendance_stats.iterrows():
            html_builder.append('<tr>')
            for i, val in enumerate(row):
                if i < 3:
                    bg_color = "#FEF3C7" if i == 2 else "#F1F5F9"
                    html_builder.append(f'<td class="sticky-col" style="left: {left_pos[i]}px; background-color: {bg_color};">{val}</td>')
                else:
                    html_builder.append(f'<td>{val}</td>')
            html_builder.append('</tr>')
        html_builder.append('</tbody></table></div>')
        
        st.markdown("".join(html_builder), unsafe_allow_html=True)

# ==============================================================================
# 功能 2：段考成績分析與趨勢 (已完整復原「段考進步最優異金榜與趨勢曲線」)
# ==============================================================================
elif menu == "📊 段考成績分析與趨勢":
    st.markdown('<div class="main-title">📊 段考成績分析與趨勢</div>', unsafe_allow_html=True)
    scores_df = st.session_state["db_scores"]
    if scores_df.empty:
        st.warning("目前尚無成績資料。請檢查您的 Google 試算表「各次段考成績」分頁。")
    else:
        subjects = ["國文", "英文", "數學", "歷史", "地理", "公民"]
        for sub in subjects:
            if sub in scores_df.columns: scores_df[sub] = pd.to_numeric(scores_df[sub], errors='coerce')
        
        exam_categories = scores_df["考試類別"].unique()
        if len(exam_categories) > 0:
            selected_exam = st.selectbox("🎯 選擇分析的段考階段", exam_categories)
            exam_filtered = scores_df[scores_df["考試類別"] == selected_exam]
            
            st.markdown("---")
            st.subheader(f"🏆 {selected_exam} 各科排名前 5 名")
            cols_leaderboard = st.columns(3)
            for idx, sub in enumerate(subjects):
                if sub in exam_filtered.columns:
                    with cols_leaderboard[idx % 3]:
                        st.markdown(f'<div class="card-container"><h4 style="color: #1E3A8A; margin-top:0;">📚 {sub}</h4>', unsafe_allow_html=True)
                        sub_scores = exam_filtered.dropna(subset=[sub])
                        top5 = sub_scores.sort_values(by=sub, ascending=False).head(5)
                        rank_list = [f"**第{rank}名**: 座號{int(r['座號'])} {r['姓名']} ({r[sub]}分)" for rank, (_, r) in enumerate(top5.iterrows(), 1)]
                        st.markdown("<br>".join(rank_list) if rank_list else "<span style='color:gray;'>無成績</span>", unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                        
            # ================= 進步最多前 5 名功能區塊 =================
            st.markdown("---")
            st.subheader("📈 段考進步最多前 5 名 (總分進步幅度)")
            
            try:
                exam_list = list(exam_categories)
                current_idx = exam_list.index(selected_exam)
                if current_idx == 0:
                    st.info("💡 目前選取的是該學期第一次段考，尚無更早的成績可供比較「進步名次」。若要查看進步榜，請選取第二次或第三次段考。")
                else:
                    prev_exam = exam_list[current_idx - 1]
                    prev_filtered = scores_df[scores_df["考試類別"] == prev_exam]
                    
                    exam_filtered_with_total = exam_filtered.copy()
                    exam_filtered_with_total["總分"] = exam_filtered_with_total[subjects].sum(axis=1, min_count=1)
                    
                    prev_filtered_with_total = prev_filtered.copy()
                    prev_filtered_with_total["總分"] = prev_filtered_with_total[subjects].sum(axis=1, min_count=1)
                    
                    progress_df = pd.merge(
                        exam_filtered_with_total[["座號", "姓名", "總分"]],
                        prev_filtered_with_total[["座號", "總分"]],
                        on="座號",
                        suffixes=("_本次", "_上次")
                    )
                    progress_df["總分進步"] = progress_df["總分_本次"] - progress_df["總分_上次"]
                    
                    valid_progress = progress_df.dropna(subset=["總分進步"])
                    top_progress = valid_progress.sort_values(by="總分進步", ascending=False).head(5)
                    
                    if top_progress.empty:
                        st.warning("無足夠的前後段考資料比對進步情況。")
                    else:
                        col_p1, col_p2 = st.columns([1, 2])
                        with col_p1:
                            st.markdown("##### 🏆 總分進步優異金榜")
                            for rank, (_, r) in enumerate(top_progress.iterrows(), 1):
                                st.markdown(f"**第 {rank} 名**：座號 {int(r['座號'])} **{r['姓名']}** (總分進步 +{round(r['總分進步'], 1)} 分)")
                        with col_p2:
                            fig_progress = px.bar(
                                top_progress, x="姓名", y="總分進步", 
                                text_auto='.1f', title=f"相比於「{prev_exam}」，總分進步幅度圖",
                                color="總分進步", color_continuous_scale="Viridis"
                            )
                            fig_progress.update_layout(yaxis_title="進步分數", xaxis_title="姓名")
                            st.plotly_chart(fig_progress, use_container_width=True)
            except Exception as e:
                st.error(f"計算進步排名時發生預期外錯誤: {e}")

            # ================= 個人趨勢分析圖 =================
            st.markdown("---")
            st.subheader("📈 個人各科成績趨勢曲線圖")
            student_sel = st.selectbox("選擇要分析趨勢的學生", [f"座號 {int(row['座號'])} - {row['姓名']}" for _, row in st.session_state["db_students"].iterrows()])
            sel_id = int(student_sel.split(" ")[1])
            student_scores = scores_df[scores_df["座號"].astype(int) == sel_id]
            if not student_scores.empty:
                melted_scores = student_scores.melt(id_vars=["考試類別"], value_vars=[s for s in subjects if s in student_scores.columns], var_name="科目", value_name="分數").dropna()
                fig_trend = px.line(melted_scores, x="考試類別", y="分數", color="科目", markers=True, title=f"{student_sel.split(' - ')[1]} 的成績變化", category_orders={"考試類別": list(exam_categories)})
                fig_trend.update_layout(yaxis_range=[0, 100])
                st.plotly_chart(fig_trend, use_container_width=True)

# ==============================================================================
# 功能 3：班級貢獻度登記與統計 (新增學期日期判定與標題容錯)
# ==============================================================================
elif menu == "🌟 班級貢獻度登記與統計":
    st.markdown(f'<div class="main-title">🌟 班級貢獻度登記與統計 <span style="font-size:1.2rem; color:gray;">({global_selected_semester})</span></div>', unsafe_allow_html=True)
    
    st.subheader("📥 批次學生加扣分登記")
    tab_click, tab_text, tab_daily = st.tabs(["✨ 圖形化選單登記", "✍️ 快速文字貼上登記", "⚡ 每日固定事項快速扣分"])
    
    students_df = st.session_state["db_students"]
    student_list_for_sel = [f"座號 {int(row['座號'])} - {row['姓名']}" for _, row in students_df.iterrows()]
    pending_records = []
    
    with tab_click:
        col_input1, col_input2 = st.columns(2)
        with col_input1:
            contri_date = st.date_input("加扣分日期", datetime.today(), key="contri_date_click")
            contri_event = st.text_input("事由描述", placeholder="例如：整潔工作認真...", key="contri_event_click")
        with col_input2:
            contri_type = st.radio("加分或扣分", ["加分 (+1)", "扣分 (-1)"], horizontal=True, key="contri_type_click")
            selected_students_contri = st.multiselect("選擇加扣分的學生名單", student_list_for_sel, key="selected_click")
            
        if st.button("🚀 送出選單登記", key="btn_click"):
            if not contri_event: st.error("請填寫事由描述！")
            elif not selected_students_contri: st.error("請至少選擇一位同學！")
            else:
                pts = 1 if "加分" in contri_type else -1
                for sel in selected_students_contri:
                    seat = int(sel.split(" ")[1])
                    sname = students_df[students_df["座號"] == seat].iloc[0]["姓名"]
                    inferred_sem = get_semester_by_date(contri_date)
                    pending_records.append({"學期": inferred_sem, "日期": contri_date.strftime("%Y/%m/%d"), "座號": seat, "姓名": sname, "事由": contri_event, "加扣分點數": pts})

    with tab_text:
        paste_area = st.text_area("請在此貼上幹部紀錄文字：", value="日期:2026/6/22\n事由:朝會缺席\n加扣分:-1\n名單:1、2、3", height=150)
        parsed_data = {match.group(1).strip(): match.group(2).strip() for line in paste_area.strip().split('\n') if (match := re.match(r'^([^:：]+)[:：](.*)$', line.strip()))}
        if st.button("🚀 送出文字貼上登記", key="btn_text"):
            p_event = parsed_data.get("事由", "")
            p_seats = [int(part) for part in re.split(r'[、，,\s;；]+', parsed_data.get("名單", "")) if part.strip().isdigit()]
            if not p_event or not p_seats: st.error("❌ 解析失敗！請確保格式正確。")
            else:
                pts = -1 if "-" in parsed_data.get("加扣分", "") or "扣" in parsed_data.get("加扣分", "") else 1
                record_date_str = parsed_data.get("日期", datetime.today().strftime("%Y/%m/%d"))
                inferred_sem = get_semester_by_date(record_date_str)
                for seat in p_seats:
                    st_row = students_df[students_df["座號"] == seat]
                    if not st_row.empty: pending_records.append({"學期": inferred_sem, "日期": record_date_str, "座號": seat, "姓名": st_row.iloc[0]["姓名"], "事由": p_event, "加扣分點數": pts})

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
            inferred_sem = get_semester_by_date(datetime.today())
            def append_daily(stu_list, ev_name):
                for sel in stu_list:
                    seat = int(sel.split(" ")[1])
                    sname = students_df[students_df["座號"] == seat].iloc[0]["姓名"]
                    pending_records.append({"學期": inferred_sem, "日期": d_str, "座號": seat, "姓名": sname, "事由": ev_name, "加扣分點數": -1})
            append_daily(late_students, "每日遲到")
            append_daily(noisy_students, "每日吵鬧")
            append_daily(no_form_students, "每日回條不交")
            append_daily(bad_clean_students, "每日打掃不確實")
            if not pending_records: st.warning("⚠️ 請至少選擇一位學生再送出！")

    # ================= 統一執行儲存與即時更新 GS 邏輯 =================
    if pending_records:
        new_hist_df = pd.DataFrame(pending_records)
        st.session_state["db_contribution_history"] = pd.concat([st.session_state["db_contribution_history"], new_hist_df], ignore_index=True)
        # 歷史細目送出 (包含智慧解析之學期)
        gas_history_records = [[r["日期"], r["座號"], r["姓名"], r["事由"], r["加扣分點數"], r.get("學期", global_selected_semester)] for r in pending_records]
        
        stats_df = st.session_state["db_contribution_stats"].copy()
        
        if "學期" not in stats_df.columns:
            stats_df.insert(0, "學期", global_selected_semester)
            
        for r in pending_records:
            sem, sid, event, pts = r.get("學期", global_selected_semester), r["座號"], r["事由"], r["加扣分點數"]
            
            col_name = event
            for c in stats_df.columns:
                if event in str(c): col_name = c; break
                
            if col_name not in stats_df.columns: 
                stats_df[col_name] = 0.0
            
            stats_df[col_name] = pd.to_numeric(stats_df[col_name], errors='coerce').fillna(0.0)
            if "加扣分總計" not in stats_df.columns:
                stats_df["加扣分總計"] = 0.0
            stats_df["加扣分總計"] = pd.to_numeric(stats_df["加扣分總計"], errors='coerce').fillna(0.0)
            
            # 定位 (學期, 座號)
            mask = (stats_df["座號"] == sid) & (stats_df["學期"].astype(str) == str(sem))
            if not mask.any():
                new_row = {"學期": sem, "座號": sid, "姓名": r["姓名"], "加扣分總計": 0.0}
                stats_df = pd.concat([stats_df, pd.DataFrame([new_row])], ignore_index=True)
                stats_df.fillna(0.0, inplace=True)
                mask = (stats_df["座號"] == sid) & (stats_df["學期"].astype(str) == str(sem))
                
            idx = stats_df.index[mask].tolist()[0]
            
            stats_df.at[idx, col_name] = float(stats_df.at[idx, col_name]) + float(pts)
            stats_df.at[idx, "加扣分總計"] = float(stats_df.at[idx, "加扣分總計"]) + float(pts)
                    
        st.session_state["db_contribution_stats"] = stats_df
        stats_matrix = [stats_df.columns.tolist()] + stats_df.fillna("").values.tolist()
        
        payload = {"action": "save_contribution", "records": gas_history_records, "statsMatrix": stats_matrix}
        if write_data_via_apps_script(GAS_WEB_APP_URL, payload): st.rerun()

    # ================= 班級貢獻度累計統計表 (依據學期篩選) =================
    st.markdown("---")
    st.subheader(f"📊 班級貢獻度累計統計表 ({global_selected_semester})")
    
    current_stats = st.session_state["db_contribution_stats"].copy()
    
    if not current_stats.empty:
        if "學期" in current_stats.columns:
            display_stats = current_stats[current_stats["學期"].astype(str) == global_selected_semester]
        else:
            display_stats = current_stats
            
        if display_stats.empty:
            st.info(f"💡 目前【{global_selected_semester}】尚未有加扣分統計紀錄。")
        else:
            sticky_cols_count = 3 if "學期" in display_stats.columns else 2
            html_builder_contri = ['<div class="frozen-table-container"><table class="frozen-table"><thead><tr>']
            for i, col in enumerate(display_stats.columns):
                style_class = ' class="sticky-col"' if i < sticky_cols_count else ''
                style_prop = f' style="left: {i*80}px;"' if i < sticky_cols_count else ''
                html_builder_contri.append(f'<th{style_class}{style_prop}>{col}</th>')
            html_builder_contri.append('</tr></thead><tbody>')
            
            for _, row in display_stats.iterrows():
                html_builder_contri.append('<tr>')
                for i, val in enumerate(row):
                    style_class = ' class="sticky-col"' if i < sticky_cols_count else ''
                    style_prop = f' style="left: {i*80}px; background-color: #F1F5F9;"' if i < sticky_cols_count else ''
                    
                    try:
                        num_val = float(val)
                        is_num = not pd.isna(num_val) and str(val).replace('.', '', 1).replace('-', '', 1).isdigit()
                    except:
                        is_num = False

                    if is_num and i >= sticky_cols_count:
                        if num_val > 0: html_builder_contri.append(f'<td{style_class} style="color: green; font-weight: bold;">+{int(num_val)}</td>')
                        elif num_val < 0: html_builder_contri.append(f'<td{style_class} style="color: red; font-weight: bold;">{int(num_val)}</td>')
                        else: html_builder_contri.append(f'<td{style_class}>{int(num_val)}</td>')
                    else:
                        html_builder_contri.append(f'<td{style_class}{style_prop}>{val if pd.notna(val) else ""}</td>')
                html_builder_contri.append('</tr>')
            html_builder_contri.append('</tbody></table></div>')
            st.markdown("".join(html_builder_contri), unsafe_allow_html=True)

    # ================= 各月份熱心服務與待改進榜單 (智慧型學期日期過濾與完美同分排名) =================
    st.markdown("---")
    st.markdown("### 📅 歷史各月份熱心服務與待改進榜單")
    st.caption(f"💡 這裡僅顯示屬於【{global_selected_semester}】月份區間的排行榜（依照加扣分數嚴謹排名，同分者一併列出）。")
    
    history_df = st.session_state["db_contribution_history"].copy()
    if not history_df.empty:
        # 【重要安全修復】：補上缺失的加扣分點數欄位之數值轉換，若欄位缺失則默認轉為0
        if "加扣分點數" in history_df.columns:
            history_df["加扣分點數"] = pd.to_numeric(history_df["加扣分點數"], errors='coerce').fillna(0)
        else:
            history_df["加扣分點數"] = 0
            
        history_df["日期"] = pd.to_datetime(history_df["日期"], errors='coerce')
        # 排除日期無效或空白的行（這會自動剔除雲端上您預填的名單範本列）
        history_df = history_df.dropna(subset=["日期"])
        
        # 【智慧過濾】：僅撈取屬於當前全局選定學期區間內日期的歷史紀錄！
        history_df["學期_判定"] = history_df["日期"].apply(get_semester_by_date)
        sem_filtered_history = history_df[history_df["學期_判定"] == global_selected_semester]
        
        if sem_filtered_history.empty:
            st.info(f"💡 目前【{global_selected_semester}】歷史紀錄中無任何月份加扣分明細。")
        else:
            sem_filtered_history["月份"] = sem_filtered_history["日期"].dt.strftime("%Y 年 %m 月")
            months = sorted(sem_filtered_history["月份"].unique(), reverse=True)
            
            for month in months:
                with st.expander(f"📌 {month} 統計榜單", expanded=(month == months[0])):
                    month_data = sem_filtered_history[sem_filtered_history["月份"] == month]
                    student_sums = month_data.groupby(["座號", "姓名"])["加扣分點數"].sum().reset_index()
                    
                    col_good, col_bad = st.columns(2)
                    
                    with col_good:
                        st.markdown("**🌟 熱心班務卓越榜 (加分最多)**")
                        good_st = student_sums[student_sums["加扣分點數"] > 0].copy()
                        if not good_st.empty:
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
                            bad_st["名次"] = bad_st["加扣分點數"].rank(method='min', ascending=True)
                            top_bad = bad_st[bad_st["名次"] <= 5].sort_values("名次")
                            if not top_bad.empty:
                                for rank in sorted(top_bad["名次"].unique()):
                                    group = top_bad[top_bad["名次"] == rank]
                                    names = " Mus、".join([f"{int(r['座號'])}{r['姓名']}" for _, r in group.iterrows()])
                                    names = names.replace(" Mus", "")  # 清除乾淨
                                    pts = group.iloc[0]["加扣分點數"]
                                    st.markdown(f"🚨 **第 {int(rank)} 名**: {names} (共 {int(pts)} 分)")
                            else:
                                st.write("本月無符合前五名扣分紀錄")
                        else:
                            st.write("本月無扣分紀錄")
