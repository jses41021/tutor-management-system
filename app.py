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
# Google Sheet 免 API 讀寫核心邏輯 (支援智慧型課表解析)
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
        if val_a in ["二下", "三上", "三下", "二上", "一下", "一上"]:
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
    st.session_state["db_timetable"] = pd.DataFrame([{"學期": "二下", "節次": "第一節", "星期一": "數學", "星期二": "體育", "星期三": "國防", "星期四": "數學", "星期五": "社會探究"}])
if "db_attendance" not in st.session_state:
    st.session_state["db_attendance"] = pd.DataFrame(columns=["日期", "座號", "姓名", "出席狀態"])
if "db_scores" not in st.session_state:
    st.session_state["db_scores"] = pd.DataFrame(columns=["考試類別", "座號", "姓名", "國文", "英文", "數學", "歷史", "地理", "公民"])
if "db_contribution_history" not in st.session_state:
    st.session_state["db_contribution_history"] = pd.DataFrame(columns=["日期", "座號", "姓名", "事由", "加扣分點數"])
if "db_contribution_stats" not in st.session_state:
    df_stats = pd.DataFrame()
    df_stats["座號"] = st.session_state["db_students"]["座號"]
    df_stats["姓名"] = st.session_state["db_students"]["姓名"]
    df_stats["加扣分總計"] = 0
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

for df_key in ["db_students", "db_contribution_history", "db_contribution_stats"]:
    if df_key in st.session_state and "座號" in st.session_state[df_key].columns:
        st.session_state[df_key]["座號"] = pd.to_numeric(st.session_state[df_key]["座號"], errors='coerce').fillna(0).astype(int)

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/google-sheets.png", width=55)
    st.title("🎓 導師班級經營系統")
    if spreadsheet_id: st.success("⚡ 雲端資料已同步成功！")
        
    menu = st.radio("功能導覽", ["📅 課表與出缺席即時管理", "📊 段考成績分析與趨勢", "🌟 班級貢獻度登記與統計"])

# ==============================================================================
# 功能 1：課表與出缺席即時管理 (全面升級版)
# ==============================================================================
if menu == "📅 課表與出缺席即時管理":
    st.markdown('<div class="main-title">📅 課表與出缺席即時管理</div>', unsafe_allow_html=True)
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        available_semesters = ["二下", "三上"]
        if not st.session_state["db_timetable"].empty and "學期" in st.session_state["db_timetable"].columns:
            available_semesters = st.session_state["db_timetable"]["學期"].astype(str).unique().tolist()
        selected_semester = st.selectbox("選擇學期課表", available_semesters)
    with col_sel2:
        today_date = st.date_input("點名日期", datetime.today())
        
    timetable_df = st.session_state["db_timetable"]
    sem_timetable = pd.DataFrame()
    if not timetable_df.empty and "學期" in timetable_df.columns:
        sem_timetable = timetable_df[timetable_df["學期"].astype(str) == selected_semester]

    # =================每日點名登記介面 (支援部分節次缺席)=================
    st.markdown("---")
    st.subheader(f"📝 {today_date.strftime('%Y/%m/%d')} 每日缺席登記")
    st.caption("💡 可在此勾選今日缺席的學生。若為部分節次請假，請在下方展開處勾選特定節次。")
    
    students_df = st.session_state["db_students"]
    student_options = [f"座號 {int(row['座號'])} - {row['姓名']}" for _, row in students_df.iterrows()]
    absent_selections = st.multiselect("請選擇今日有「缺席或請假」的學生", student_options)
    
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
                    period_sel = st.multiselect(f"【{stu_name}】缺席節次", available_periods, key=f"abs_{sel}")
                    if period_sel:
                        student_absent_details[sel] = "缺席節次:" + ",".join(period_sel)
                    else:
                        student_absent_details[sel] = "全日缺席"
                else:
                    student_absent_details[sel] = "全日缺席"
                    st.caption(f"{stu_name} (今日無課表，記為全日缺席)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button("💾 儲存今日出缺席紀錄"):
        absent_ids = [int(sel.split(" ")[1]) for sel in absent_selections]
        new_records, gas_records = [], []
        
        for _, row in students_df.iterrows():
            stu_str = f"座號 {int(row['座號'])} - {row['姓名']}"
            if int(row["座號"]) in absent_ids:
                status = student_absent_details.get(stu_str, "全日缺席")
            else:
                status = "出席"
                
            new_records.append({"日期": today_date.strftime("%Y/%m/%d"), "座號": int(row["座號"]), "姓名": row["姓名"], "出席狀態": status})
            gas_records.append([today_date.strftime("%Y/%m/%d"), int(row["座號"]), row["姓名"], status])
        
        new_df = pd.DataFrame(new_records)
        orig_attendance = st.session_state["db_attendance"]
        if not orig_attendance.empty:
            orig_attendance = orig_attendance[orig_attendance["日期"].astype(str) != today_date.strftime("%Y/%m/%d")]
        
        st.session_state["db_attendance"] = pd.concat([orig_attendance, new_df], ignore_index=True)
        payload = {"action": "save_attendance", "date": today_date.strftime("%Y/%m/%d"), "records": gas_records}
        write_data_via_apps_script(GAS_WEB_APP_URL, payload)

    # =================新增：缺席月曆視圖=================
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
    st.subheader("📊 每位學生各科目「實際缺席次數」與「累積缺席節數」累計表")
    st.caption("💡 系統自動根據請假狀態（全日/特定節次）與課表比對，精準計算缺席的節數。")
    
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
        # 凍結前三欄：座號、姓名、累積缺席節數
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
# 功能 2：段考成績分析與趨勢 (維持原樣)
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
# 功能 3：班級貢獻度登記與統計 (修復 TypeError)
# ==============================================================================
elif menu == "🌟 班級貢獻度登記與統計":
    st.markdown('<div class="main-title">🌟 班級貢獻度登記與統計</div>', unsafe_allow_html=True)
    
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
                    pending_records.append({"日期": contri_date.strftime("%Y/%m/%d"), "座號": seat, "姓名": sname, "事由": contri_event, "加扣分點數": pts})

    with tab_text:
        paste_area = st.text_area("請在此貼上幹部紀錄文字：", value="日期:2026/6/22\n事由:朝會缺席\n加扣分:-1\n名單:1、2、3", height=150)
        parsed_data = {match.group(1).strip(): match.group(2).strip() for line in paste_area.strip().split('\n') if (match := re.match(r'^([^:：]+)[:：](.*)$', line.strip()))}
        if st.button("🚀 送出文字貼上登記", key="btn_text"):
            p_event = parsed_data.get("事由", "")
            p_seats = [int(part) for part in re.split(r'[、，,\s;；]+', parsed_data.get("名單", "")) if part.strip().isdigit()]
            if not p_event or not p_seats: st.error("❌ 解析失敗！請確保格式正確。")
            else:
                pts = -1 if "-" in parsed_data.get("加扣分", "") or "扣" in parsed_data.get("加扣分", "") else 1
                for seat in p_seats:
                    st_row = students_df[students_df["座號"] == seat]
                    if not st_row.empty: pending_records.append({"日期": parsed_data.get("日期", datetime.today().strftime("%Y/%m/%d")), "座號": seat, "姓名": st_row.iloc[0]["姓名"], "事由": p_event, "加扣分點數": pts})

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
            if not pending_records: st.warning("⚠️ 請至少選擇一位學生再送出！")

    # ================= 統一執行儲存與即時更新 GS 邏輯 (包含防呆轉型機制) =================
    if pending_records:
        new_hist_df = pd.DataFrame(pending_records)
        st.session_state["db_contribution_history"] = pd.concat([st.session_state["db_contribution_history"], new_hist_df], ignore_index=True)
        gas_history_records = [[r["日期"], r["座號"], r["姓名"], r["事由"], r["加扣分點數"]] for r in pending_records]
        
        stats_df = st.session_state["db_contribution_stats"].copy()
        
        for r in pending_records:
            sid, event, pts = r["座號"], r["事由"], r["加扣分點數"]
            
            col_name = event
            for c in stats_df.columns:
                if event in str(c): col_name = c; break
            if col_name not in stats_df.columns: stats_df[col_name] = 0
                
            idx = stats_df.index[stats_df["座號"] == sid].tolist()
            if idx:
                i = idx[0]
                
                # 【修復處】安全地將資料讀取為 float，避免 Mixed Type 或是 NaN 造成的 TypeError
                try:
                    current_val = float(stats_df.loc[i, col_name])
                    if pd.isna(current_val): current_val = 0.0
                except (ValueError, TypeError, KeyError):
                    current_val = 0.0
                    
                stats_df.loc[i, col_name] = current_val + float(pts)
                
                # 同步更新總計
                if "加扣分總計" in stats_df.columns:
                    try:
                        tot = float(stats_df.loc[i, "加扣分總計"])
                        if pd.isna(tot): tot = 0.0
                    except (ValueError, TypeError, KeyError):
                        tot = 0.0
                    stats_df.loc[i, "加扣分總計"] = tot + float(pts)
                else:
                    stats_df.loc[i, "加扣分總計"] = float(pts)
                    
        st.session_state["db_contribution_stats"] = stats_df
        stats_matrix = [stats_df.columns.tolist()] + stats_df.fillna("").values.tolist()
        
        payload = {"action": "save_contribution", "records": gas_history_records, "statsMatrix": stats_matrix}
        if write_data_via_apps_script(GAS_WEB_APP_URL, payload): st.rerun()

    # =================班級貢獻度累計統計表=================
    st.markdown("---")
    st.subheader("📊 班級貢獻度累計統計表")
    current_stats = st.session_state["db_contribution_stats"]
    
    if not current_stats.empty:
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
                style_prop = f' style="left: {i*80}px; background-color: #F1F5F9;"' if i < sticky_cols_count else ''
                
                # 安全地檢查是否為數字以進行變色處理
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
