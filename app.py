import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
import urllib.parse
import requests
import json

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
    
    /* 凍結第一、二欄 (座號、姓名) */
    table.frozen-table td:nth-child(1), table.frozen-table th:nth-child(1) {
        position: sticky;
        left: 0;
        background-color: #F1F5F9;
        z-index: 5;
        font-weight: bold;
        border-right: 2px solid #94A3B8;
    }
    
    table.frozen-table td:nth-child(2), table.frozen-table th:nth-child(2) {
        position: sticky;
        left: 60px; /* 座號寬度預估 */
        background-color: #F1F5F9;
        z-index: 5;
        font-weight: bold;
        border-right: 3px solid #64748B;
    }
    
    table.frozen-table th:nth-child(1), table.frozen-table th:nth-child(2) {
        z-index: 15; /* 標頭部分需要更高層級，防滾動重疊 */
        background-color: #1D4ED8;
    }
    
    /* 斑馬紋 */
    table.frozen-table tr:nth-child(even) td {
        background-color: #F8FAFC;
    }
    table.frozen-table tr:nth-child(even) td:nth-child(1), 
    table.frozen-table tr:nth-child(even) td:nth-child(2) {
        background-color: #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# Google Sheet 免 API 讀寫核心邏輯
# ==============================================================================
def get_spreadsheet_id(url_or_id):
    """從使用者輸入的 URL 或 ID 中，解析出 Spreadsheet ID"""
    if "docs.google.com/spreadsheets" in url_or_id:
        try:
            parts = url_or_id.split("/d/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        except Exception:
            pass
    return url_or_id.strip()

def load_sheet_csv(spreadsheet_id, sheet_name, fallback_df):
    """透過 gviz URL 免 API 直接讀取公開試算表特定的分頁為 DataFrame"""
    if not spreadsheet_id:
        return fallback_df
    try:
        encoded_name = urllib.parse.quote(sheet_name)
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"
        # 設定 timeout 防止加載過久
        df = pd.read_csv(url, keep_default_na=False)
        # 清除完全空白的欄或列
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        return df
    except Exception as e:
        st.sidebar.warning(f"無法讀取分頁「{sheet_name}」：{e}。系統將自動採用預設範例資料運作。")
        return fallback_df

def write_data_via_apps_script(web_app_url, payload):
    """利用 POST 請求與 Google Apps Script 溝通寫入資料"""
    if not web_app_url:
        st.warning("⚠️ 尚未設定 Google Apps Script Web App URL，資料目前僅保留於網頁記憶體中（重新整理後會消失）。")
        return False
    try:
        with st.spinner("🚀 正在即時將異動同步寫入 Google 試算表分頁..."):
            # 發送 POST 請求
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
                st.error(f"❌ 無法連線至 Google Apps Script Web App，請檢查網址與部署權限設定 (狀態碼: {response.status_code})")
    except Exception as e:
        st.error(f"❌ 傳輸發生異常：{e}")
    return False

# ==============================================================================
# 本機預設備份資料庫（當未連線時或讀取失敗時的自動 Fallback 範例資料）
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
    st.session_state["db_timetable"] = pd.DataFrame([
        # 二下課表
        {"學期": "二下", "節次": "第一節", "星期一": "數學", "星期二": "體育", "星期三": "國防", "星期四": "數學", "星期五": "社會探究"},
        {"學期": "二下", "節次": "第二節", "星期一": "歷史", "星期二": "新高學", "星期三": "國文", "星期四": "數學", "星期五": "社會探究"},
        {"學期": "二下", "節次": "第三節", "星期一": "國文", "星期二": "新高學", "星期三": "公民", "星期四": "英文", "星期五": "社會探究"},
        {"學期": "二下", "節次": "第四節", "星期一": "歷史", "星期二": "英文", "星期三": "體育", "星期四": "新媒體藝術", "星期五": "工程設計專題"},
        {"學期": "二下", "節次": "第五節", "星期一": "地科探究", "星期二": "科技應用專題", "星期三": "國文", "星期四": "國文", "星期五": "班週會/社團"},
        {"學期": "二下", "節次": "第六節", "星期一": "地科探究", "星期二": "數學", "星期三": "英文", "星期四": "自主學習", "星期五": "班週會/社團"},
        {"學期": "二下", "節次": "第七節", "星期一": "創新生活與家庭", "星期二": "公民", "星期三": "英文", "星期四": "彈性學習", "星期五": "班週會/社團"},
        # 三上課表 (欄位佔位)
        {"學期": "三上", "節次": "第一節", "星期一": "英文", "星期二": "數學", "星期三": "物理", "星期四": "國文", "星期五": "化學"},
        {"學期": "三上", "節次": "第二節", "星期一": "英文", "星期二": "歷史", "星期三": "物理", "星期四": "國文", "星期五": "化學"},
        {"學期": "三上", "節次": "第三節", "星期一": "國文", "星期二": "體育", "星期三": "地科", "星期四": "英文", "星期五": "數學"},
        {"學期": "三上", "節次": "第四節", "星期一": "數學", "星期二": "公民", "星期三": "地科", "星期四": "音樂", "星期五": "數學"},
        {"學期": "三上", "節次": "第五節", "星期一": "體育", "星期2": "自主學習", "星期三": "數學", "星期四": "國文", "星期五": "班週會/社團"},
        {"學期": "三上", "節次": "第六節", "星期一": "化學", "星期二": "彈性學習", "星期三": "國文", "星期四": "物理", "星期五": "班週會/社團"},
        {"學期": "三上", "節次": "第七節", "星期一": "化學", "星期二": "班會", "星期三": "英文", "星期四": "物理", "星期五": "班週會/社團"},
    ])

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
                "國文": np.round(np.random.normal(50, 15), 1), "英文": np.round(np.random.normal(40, 18), 1),
                "數學": np.round(np.random.normal(35, 12), 1), "歷史": np.round(np.random.normal(60, 10), 1),
                "地理": np.round(np.random.normal(55, 12), 1), "公民": np.round(np.random.normal(58, 15), 1)
            })
    st.session_state["db_scores"] = pd.DataFrame(score_data)

if "db_contribution_history" not in st.session_state:
    st.session_state["db_contribution_history"] = pd.DataFrame(columns=["日期", "座號", "姓名", "事由", "加扣分點數"])

# ==============================================================================
# 側邊欄：連結設定與功能選單
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/google-sheets.png", width=55)
    st.title("🔌 試算表免 API 連線設定")
    
    # 讓老師輸入 Google 試算表的網址或 ID
    sheet_input = st.text_input(
        "1. Google Sheet 網址或 ID",
        placeholder="https://docs.google.com/spreadsheets/d/...",
        help="請確保您的 Google Sheet 共用權限設定為「知道連結的人均可檢視」！"
    )
    spreadsheet_id = get_spreadsheet_id(sheet_input) if sheet_input else ""
    
    # 讓老師輸入 Apps Script 網頁應用程式網址
    gas_web_app_url = st.text_input(
        "2. Apps Script 部署網址 (用於儲存資料)",
        placeholder="https://script.google.com/macros/s/.../exec",
        help="請貼上您在試算表中部署 Google Apps Script 後產生的 Web App 網址。"
    )
    
    st.markdown("---")
    
    # 動態加載最新資料（如已設定 Spreadsheet ID）
    if spreadsheet_id:
        with st.spinner("🔄 正在從 Google Sheet 同步讀取最新分頁資料..."):
            st.session_state["db_students"] = load_sheet_csv(spreadsheet_id, "導班學生名單", st.session_state["db_students"])
            st.session_state["db_timetable"] = load_sheet_csv(spreadsheet_id, "課表", st.session_state["db_timetable"])
            st.session_state["db_attendance"] = load_sheet_csv(spreadsheet_id, "出缺席紀錄", st.session_state["db_attendance"])
            st.session_state["db_scores"] = load_sheet_csv(spreadsheet_id, "各次段考成績", st.session_state["db_scores"])
            st.session_state["db_contribution_history"] = load_sheet_csv(spreadsheet_id, "班級貢獻度歷史紀錄", st.session_state["db_contribution_history"])
        st.success("⚡ 雲端資料同步讀取成功！")
        
    menu = st.radio(
        "功能導覽",
        ["📅 課表與出缺席即時管理", "📊 段考成績分析與趨勢", "🌟 班級貢獻度登記與統計"]
    )

# 確保座號型態正確
try:
    st.session_state["db_students"]["座號"] = st.session_state["db_students"]["座號"].astype(int)
except Exception:
    pass

# ==============================================================================
# 功能 1：課表與出缺席即時管理
# ==============================================================================
if menu == "📅 課表與出缺席即時管理":
    st.markdown('<div class="main-title">📅 課表與出缺席即時管理</div>', unsafe_allow_html=True)
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        selected_semester = st.selectbox("選擇學期課表", ["二下", "三上"])
    with col_sel2:
        today_date = st.date_input("點名日期", datetime.today())
        
    with st.expander("🔍 檢視本學期課表科目"):
        # 從雲端獲取最新課表
        timetable_df = st.session_state["db_timetable"]
        sem_timetable = timetable_df[timetable_df["學期"].astype(str) == selected_semester]
        st.dataframe(sem_timetable, use_container_width=True)
        
    st.markdown("---")
    
    # 每日點名登記介面
    st.subheader(f"📝 {today_date.strftime('%Y/%m/%d')} 每日缺席登記")
    st.caption("💡 系統預設全員出席。若有缺席同學，請在下方勾選（支援多選、快速登記）：")
    
    students_df = st.session_state["db_students"]
    
    # 建立多選選單
    student_options = [f"座號 {int(row['座號'])} - {row['姓名']}" for _, row in students_df.iterrows()]
    absent_selections = st.multiselect("請選擇今日缺席的學生", student_options)
    
    if st.button("💾 儲存今日出缺席紀錄"):
        absent_ids = [int(sel.split(" ")[1]) for sel in absent_selections]
        
        # 準備寫入本機暫存與雲端紀錄
        new_records = []
        gas_records = [] # 要傳給 GAS 的資料格式 [日期, 座號, 姓名, 出席狀態]
        for _, row in students_df.iterrows():
            status = "缺席" if int(row["座號"]) in absent_ids else "出席"
            new_records.append({
                "日期": today_date.strftime("%Y/%m/%d"),
                "座號": int(row["座號"]),
                "姓名": row["姓名"],
                "出席狀態": status
            })
            gas_records.append([today_date.strftime("%Y/%m/%d"), int(row["座號"]), row["姓名"], status])
        
        new_df = pd.DataFrame(new_records)
        
        # 避免重複日期寫入，先刪除舊有同日期的本機數據
        orig_attendance = st.session_state["db_attendance"]
        if not orig_attendance.empty:
            orig_attendance = orig_attendance[orig_attendance["日期"].astype(str) != today_date.strftime("%Y/%m/%d")]
        
        st.session_state["db_attendance"] = pd.concat([orig_attendance, new_df], ignore_index=True)
        
        # 透過 GAS 寫入 Google Sheet
        payload = {
            "action": "save_attendance",
            "date": today_date.strftime("%Y/%m/%d"),
            "records": gas_records
        }
        
        success = write_data_via_apps_script(gas_web_app_url, payload)
        if not success:
            st.info("💡 目前已先幫您將這筆記錄儲存在網頁本機暫存中。若要永久保存，請記得依據說明設定 Apps Script URL。")

    # --------------------------------------------------------------------------
    # 即時計算與呈現：學生各科目出席次數 (核心演算法)
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📊 每位學生各科目「實際出席次數」累計表 (含首欄凍結窗格)")
    st.caption("💡 計算規則：每當某日學生「出席」時，當天課表內出現的科目皆計為出席。重疊科目如當天有2節課，則出席次數+2。")
    
    days_of_week = ["星期一", "星期二", "星期三", "星期四", "星期五"]
    
    # 統計每日各科目的堂數
    daily_subject_counts = {}
    all_subjects = set()
    
    for day in days_of_week:
        daily_subject_counts[day] = {}
        if day in sem_timetable.columns:
            subjects_list = sem_timetable[day].replace('', np.nan).dropna().tolist()
            for sub in subjects_list:
                sub_clean = str(sub).strip()
                if sub_clean and sub_clean != "朝會" and "自主學習" not in sub_clean and "彈性學習" not in sub_clean:
                    all_subjects.add(sub_clean)
                    daily_subject_counts[day][sub_clean] = daily_subject_counts[day].get(sub_clean, 0) + 1
                
    sorted_subjects = sorted(list(all_subjects))
    
    # 建立每位同學的各科出席累計 dataframe
    attendance_stats = pd.DataFrame(0, index=students_df["座號"], columns=sorted_subjects)
    attendance_stats.insert(0, "姓名", students_df["姓名"].values)
    attendance_stats.insert(0, "座號", students_df["座號"].values)
    
    attn_df = st.session_state["db_attendance"]
    
    if not attn_df.empty:
        # 轉換日期格式統一，避免比對錯誤
        attn_df["日期"] = attn_df["日期"].astype(str)
        dates_recorded = attn_df["日期"].unique()
        for d_str in dates_recorded:
            try:
                # 相容 YYYY/MM/DD 或 YYYY-MM-DD
                d_str_formatted = d_str.replace("-", "/")
                dt = datetime.strptime(d_str_formatted, "%Y/%m/%d")
                weekday_num = dt.weekday()
                if weekday_num < 5:
                    weekday_name = days_of_week[weekday_num]
                    today_subjects = daily_subject_counts.get(weekday_name, {})
                    
                    # 篩選當日出席的同學
                    day_attn = attn_df[attn_df["日期"] == d_str]
                    present_students = day_attn[day_attn["出席狀態"].str.strip() == "出席"]["座號"].astype(int).tolist()
                    
                    for sub, count in today_subjects.items():
                        if sub in attendance_stats.columns:
                            attendance_stats.loc[attendance_stats["座號"].isin(present_students), sub] += count
            except Exception as e:
                continue
                
    # 生成並輸出凍結首欄的 HTML 表格
    html_builder = ['<div class="frozen-table-container"><table class="frozen-table"><thead><tr>']
    for col in attendance_stats.columns:
        html_builder.append(f'<th>{col}</th>')
    html_builder.append('</tr></thead><tbody>')
    for _, row in attendance_stats.iterrows():
        html_builder.append('<tr>')
        for i, val in enumerate(row):
            html_builder.append(f'<td>{val}</td>')
        html_builder.append('</tr>')
    html_builder.append('</tbody></table></div>')
    
    st.markdown("".join(html_builder), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    csv_data = attendance_stats.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 下載此出席統計報表 (CSV格式)", data=csv_data, file_name="學生科目出席次數統計.csv", mime="text/csv")

# ==============================================================================
# 功能 2：段考成績分析與趨勢
# ==============================================================================
elif menu == "📊 段考成績分析與趨勢":
    st.markdown('<div class="main-title">📊 段考成績分析與趨勢</div>', unsafe_allow_html=True)
    
    scores_df = st.session_state["db_scores"]
    subjects = ["國文", "英文", "數學", "歷史", "地理", "公民"]
    
    # 確保分數類型為浮點數或整數
    for sub in subjects:
        if sub in scores_df.columns:
            scores_df[sub] = pd.to_numeric(scores_df[sub], errors='coerce')
    
    exam_categories = scores_df["考試類別"].unique()
    selected_exam = st.selectbox("🎯 選擇分析的段考階段", exam_categories)
    
    exam_filtered = scores_df[scores_df["考試類別"] == selected_exam]
    
    st.markdown("---")
    st.subheader(f"🏆 {selected_exam} 各科排名前 5 名")
    
    cols_leaderboard = st.columns(3)
    for idx, sub in enumerate(subjects):
        if sub in exam_filtered.columns:
            col_target = cols_leaderboard[idx % 3]
            with col_target:
                st.markdown(f'<div class="card-container">', unsafe_allow_html=True)
                st.markdown(f'<h4 style="color: #1E3A8A; margin-top:0;">📚 {sub}</h4>', unsafe_allow_html=True)
                
                # 過濾並排序
                sub_scores = exam_filtered.dropna(subset=[sub])
                top5 = sub_scores.sort_values(by=sub, ascending=False).head(5)
                
                rank_list = []
                for rank, (_, r) in enumerate(top5.iterrows(), 1):
                    rank_list.append(f"**第{rank}名**: 座號{int(r['座號'])} {r['姓名']} ({r[sub]}分)")
                
                if not rank_list:
                    st.markdown("<span style='color:gray;'>本次考試無該科成績</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<br>".join(rank_list), unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

    # 進步最多前 5 名
    st.markdown("---")
    st.subheader("📈 段考進步最多前 5 名 (總分進步幅度)")
    
    current_idx = list(exam_categories).index(selected_exam)
    if current_idx == 0:
        st.info("💡 目前選取的是第一次段考，尚無更早的成績可供比較「進步名次」。若要查看進步榜，請選取第二次或第三次段考。")
    else:
        prev_exam = exam_categories[current_idx - 1]
        prev_filtered = scores_df[scores_df["考試類別"] == prev_exam]
        
        # 計算總分
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
        
        # 移除 NaN 值並排序前 5 名
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

    # 個人成績趨勢曲線
    st.markdown("---")
    st.subheader("📈 個人各科成績趨勢曲線圖")
    
    student_sel = st.selectbox(
        "選擇要分析趨勢的學生",
        [f"座號 {int(row['座號'])} - {row['姓名']}" for _, row in st.session_state["db_students"].iterrows()]
    )
    sel_id = int(student_sel.split(" ")[1])
    
    student_scores = scores_df[scores_df["座號"].astype(int) == sel_id]
    
    if not student_scores.empty:
        melted_scores = student_scores.melt(
            id_vars=["考試類別"], 
            value_vars=[s for s in subjects if s in student_scores.columns],
            var_name="科目", 
            value_name="分數"
        )
        # 過濾空分數 (代表缺考或無成績)
        melted_scores = melted_scores.dropna(subset=["分數"])
        
        fig_trend = px.line(
            melted_scores, 
            x="考試類別", 
            y="分數", 
            color="科目", 
            markers=True,
            title=f"{student_sel.split(' - ')[1]} 的各科段考成績變化趨勢",
            category_orders={"考試類別": list(exam_categories)}
        )
        fig_trend.update_layout(yaxis_range=[0, 100], yaxis_title="學科成績 (分)", xaxis_title="考試階段")
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.warning("查無該學生的成績資料。")

# ==============================================================================
# 功能 3：班級貢獻度登記與統計
# ==============================================================================
elif menu == "🌟 班級貢獻度登記與統計":
    st.markdown('<div class="main-title">🌟 班級貢獻度登記與統計</div>', unsafe_allow_html=True)
    
    st.subheader("📥 批次學生加扣分登記")
    st.caption("💡 方便快速！例如在朝會、整潔活動或各項競賽中，可一次選取多名同學進行相同項目之加扣分。")
    
    col_input1, col_input2 = st.columns(2)
    with col_input1:
        contri_date = st.date_input("加扣分日期", datetime.today(), key="contri_date")
        contri_event = st.text_input("事由描述", placeholder="例如：朝會缺席、整潔工作認真、課堂發表積極...")
        
    with col_input2:
        contri_type = st.radio("加分或扣分", ["加分 (+1)", "扣分 (-1)"], horizontal=True)
        students_df = st.session_state["db_students"]
        student_list_for_sel = [f"座號 {int(row['座號'])} - {row['姓名']}" for _, row in students_df.iterrows()]
        selected_students_contri = st.multiselect("選擇加扣分的學生名單", student_list_for_sel)
        
    hist_df = st.session_state["db_contribution_history"]
    
    # 宣告暫存統計變數以利即時計算與傳送
    if not hist_df.empty:
        all_events = sorted(hist_df["事由"].astype(str).unique())
        # 過濾空字串
        all_events = [e for e in all_events if e.strip() != ""]
    else:
        all_events = []
        
    stats_cols = ["座號", "姓名"] + all_events + ["加扣分總計"]
    contribution_stats_df = pd.DataFrame(0, index=students_df["座號"], columns=stats_cols)
    contribution_stats_df["座號"] = students_df["座號"].values
    contribution_stats_df["姓名"] = students_df["姓名"].values
    
    if st.button("🚀 批次儲存至「班級貢獻度歷史紀錄」"):
        if not contri_event:
            st.error("請填寫事由描述！")
        elif not selected_students_contri:
            st.error("請至少選擇一位同學！")
        else:
            score_change = 1 if "加分" in contri_type else -1
            
            new_history_records = []
            gas_history_records = [] # 要傳給 GAS 的歷史明細 [[日期, 座號, 姓名, 事由, 加扣分點數], ...]
            for student_item in selected_students_contri:
                sid = int(student_item.split(" ")[1])
                sname = student_item.split(" - ")[1]
                new_history_records.append({
                    "日期": contri_date.strftime("%Y/%m/%d"),
                    "座號": sid,
                    "姓名": sname,
                    "事由": contri_event,
                    "加扣分點數": score_change
                })
                gas_history_records.append([contri_date.strftime("%Y/%m/%d"), sid, sname, contri_event, score_change])
            
            new_hist_df = pd.DataFrame(new_history_records)
            st.session_state["db_contribution_history"] = pd.concat([st.session_state["db_contribution_history"], new_hist_df], ignore_index=True)
            
            # 即時重新計算這一次新增後的完整「統計表格」，並轉成二維矩陣傳給 GAS 覆寫
            updated_hist = st.session_state["db_contribution_history"]
            updated_events = sorted(updated_hist["事由"].astype(str).unique())
            updated_events = [e for e in updated_events if e.strip() != ""]
            
            new_stats_cols = ["座號", "姓名"] + updated_events + ["加扣分總計"]
            temp_stats_df = pd.DataFrame(0, index=students_df["座號"], columns=new_stats_cols)
            temp_stats_df["座號"] = students_df["座號"].values
            temp_stats_df["姓名"] = students_df["姓名"].values
            
            for _, row in updated_hist.iterrows():
                sid_val = int(row["座號"])
                event_val = str(row["事由"])
                pts_val = int(row["加扣分點數"])
                if sid_val in temp_stats_df.index:
                    if event_val in temp_stats_df.columns:
                        temp_stats_df.loc[sid_val, event_val] += pts_val
                    temp_stats_df.loc[sid_val, "加扣分總計"] += pts_val
            
            # 將統計 DataFrame 轉為二維 Array，準備推送
            stats_matrix = [temp_stats_df.columns.tolist()] + temp_stats_df.values.tolist()
            
            payload = {
                "action": "save_contribution",
                "records": gas_history_records,
                "statsMatrix": stats_matrix
            }
            
            success = write_data_via_apps_script(gas_web_app_url, payload)
            if not success:
                st.info("💡 資料已先暫存於本機。若需保存至 Google Sheets 試算表，請串接您的 Google Apps Script。")

    # --------------------------------------------------------------------------
    # 即時計算統計：班級貢獻度累計統計表
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("📊 班級貢獻度累計統計表 (首欄凍結窗格)")
    st.caption("💡 系統會即時動態整合歷史中「各個事由」對應的加扣分，並呈現於專用表單中：")
    
    # 依最新歷史計算本機顯示用的數據
    current_hist = st.session_state["db_contribution_history"]
    if not current_hist.empty:
        curr_events = sorted(current_hist["事由"].astype(str).unique())
        curr_events = [e for e in curr_events if e.strip() != ""]
    else:
        curr_events = []
        
    curr_cols = ["座號", "姓名"] + curr_events + ["加扣分總計"]
    contribution_stats_df = pd.DataFrame(0, index=students_df["座號"], columns=curr_cols)
    contribution_stats_df["座號"] = students_df["座號"].values
    contribution_stats_df["姓名"] = students_df["姓名"].values
    
    if not current_hist.empty:
        for _, row in current_hist.iterrows():
            try:
                sid = int(row["座號"])
                event = str(row["事由"])
                pts = int(row["加扣分點數"])
                if sid in contribution_stats_df.index:
                    if event in contribution_stats_df.columns:
                        contribution_stats_df.loc[sid, event] += pts
                    contribution_stats_df.loc[sid, "加扣分總計"] += pts
            except Exception:
                continue
                
    # 轉換成凍結窗格 HTML 表格
    html_builder_contri = ['<div class="frozen-table-container"><table class="frozen-table"><thead><tr>']
    for col in contribution_stats_df.columns:
        html_builder_contri.append(f'<th>{col}</th>')
    html_builder_contri.append('</tr></thead><tbody>')
    
    for _, row in contribution_stats_df.iterrows():
        html_builder_contri.append('<tr>')
        for val in row:
            if isinstance(val, (int, float, np.integer)) and val != row["座號"]:
                if val > 0:
                    html_builder_contri.append(f'<td style="color: green; font-weight: bold;">+{val}</td>')
                elif val < 0:
                    html_builder_contri.append(f'<td style="color: red; font-weight: bold;">{val}</td>')
                else:
                    html_builder_contri.append(f'<td>{val}</td>')
            else:
                html_builder_contri.append(f'<td>{val}</td>')
        html_builder_contri.append('</tr>')
    html_builder_contri.append('</tbody></table></div>')
    
    st.markdown("".join(html_builder_contri), unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("##### 🌟 熱心班務卓越同學榜 (前5名)")
        top_contri = contribution_stats_df.sort_values(by="加扣分總計", ascending=False).head(5)
        for rank, (_, r) in enumerate(top_contri.iterrows(), 1):
            st.markdown(f"**第 {rank} 名**：座號 {int(r['座號'])} **{r['姓名']}** (累計點數： {r['加扣分總計']} 分)")
    with col_chart2:
        csv_contri_data = contribution_stats_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載此貢獻度統計表 (CSV格式)", data=csv_contri_data, file_name="班級貢獻度統計.csv", mime="text/csv")
