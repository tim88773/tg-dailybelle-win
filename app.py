import streamlit as st
import pandas as pd
import os
import requests
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit.components.v1 as components
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime 

# --- 1. 初始化設定 ---
st.set_page_config(page_title="黛莉貝爾智能美體系統", layout="wide")

# 初始化 session_state
if 'f_name' not in st.session_state: st.session_state['f_name'] = ""
if 'f_upper' not in st.session_state: st.session_state['f_upper'] = 82.0
if 'f_lower' not in st.session_state: st.session_state['f_lower'] = 65.0
if 'f_lsn' not in st.session_state: st.session_state['f_lsn'] = 20.0
if 'f_rsn' not in st.session_state: st.session_state['f_rsn'] = 20.0
if 'f_tags' not in st.session_state: st.session_state['f_tags'] = []
if 'f_attr' not in st.session_state: st.session_state['f_attr'] = "不確定胸型" # 紀錄自動比對到的胸型
if 'run_report' not in st.session_state: st.session_state['run_report'] = False

# TG3D API 設定
APIKEY = st.secrets.get("APIKEY", "請在secrets設定APIKEY")
BASE_URL = 'https://api.tg3ds.com/api/v1'

# 身形標籤過濾清單與胸型對應清單
SHAPE_TAGS = {'Rectangle', 'Inverted Triangle', 'Triangle', 'Hourglass', 'Top Hourglass', 'Oval'}
ATTR_OPTIONS = ["不確定胸型", "秀氣勻稱型", "自然美感型", "成熟承托型", "氣質柔順型", "渾圓美胸型", "柔潤水滴型"]

# --- 2. 核心功能函數 ---

@st.cache_data
def load_csv_data(file_name):
    if not os.path.exists(file_name):
        current_path = os.path.abspath(os.getcwd())
        st.error(f"📂 **路徑錯誤**：系統目前在資料夾「`{current_path}`」中找不到檔案 `{file_name}`。請確認執行路徑是否正確。")
        return None
        
    last_error = ""
    for enc in ['utf-8-sig', 'utf-8', 'cp950', 'big5']:
        try:
            df = pd.read_csv(file_name, encoding=enc)
            if '對應尺寸群組' in df.columns:
                df['對應尺寸群組'] = df['對應尺寸群組'].astype(str).str.replace('.', ',', regex=False)
            return df
        except Exception as e:
            last_error = str(e)
            continue
            
    st.error(f"⚠️ **格式錯誤**：讀取 `{file_name}` 失敗！檔案確實存在，但格式或編碼無法解析。\n\n**系統錯誤細節：** {last_error}")
    return None

def close_sidebar():
    components.html(
        """
        <script>
        var sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
        var button = window.parent.document.querySelector('button[kind="headerNoPadding"]');
        if (sidebar && window.innerWidth < 1000) { button.click(); }
        </script>
        """, height=0,
    )

def send_email(target_email, content):
    try:
        SENDER_EMAIL = st.secrets["EMAIL_USER"]
        SENDER_PASSWORD = st.secrets["EMAIL_PASSWORD"]
        
        msg = MIMEMultipart()
        msg['From'] = f"黛莉貝爾智能導購 <{SENDER_EMAIL}>"
        msg['To'] = target_email
        msg['Subject'] = "您的黛莉貝爾專業尺寸建議報告"
        msg.attach(MIMEText(content, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"郵件發送失敗，請檢查 Secrets 設定: {e}")
        return False

def save_log_to_gsheets(name, email, upper, lower, left_sn, right_sn, attr, recommended_info):
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        gc = gspread.authorize(credentials)
        SHEET_ID = "1xPimP10ko80GBCRLNaLItPsltKCagSo8l_DAFrmf-kQ" 
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1 
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            current_time, name if name else "未提供", email if email else "未提供", 
            upper, lower, left_sn, right_sn, attr, recommended_info
        ]
        worksheet.append_row(row_data)
        st.success("📊 數據已成功寫入雲端紀錄！")
    except Exception as e:
        st.error(f"⚠️ 寫入 Google Sheets 失敗： {e}")

def get_tg3d_float(data, key, default_val):
    if not data: return default_val
    item = data.get(key)
    val = item.get('value') if isinstance(item, dict) else item
    try:
        return float(val)
    except (ValueError, TypeError):
        return default_val

# --- 3. 介面樣式 ---
st.markdown("""
    <style>
    :root { color-scheme: light !important; }
    .stApp, [data-testid="stSidebar"], [data-testid="stHeader"] { background-color: #ffebeb !important; }
    .stApp, .stApp p, .stApp span, .stApp label, .stApp div { color: #211919 !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p { color: #000000 !important; font-weight: bold; }
    h1, h2, h3 { color: #211919 !important; font-family: "Microsoft JhengHei", sans-serif !important; }
    .stButton>button { background-color: #d6a4a4 !important; color: #ffffff !important; border-radius: 20px !important; border: none !important; }
    .stButton>button:hover { background-color: #c58e8e !important; color: white !important; }
    input[type="number"], input[type="text"], [data-baseweb="select"] div, [data-baseweb="base-input"] { background-color: #ffffff !important; color: #000000 !important; -webkit-text-fill-color: #000000 !important; }
    [data-testid="stExpander"] { background-color: #ffffff !important; border: 1px solid #d6a4a4 !important; border-radius: 10px !important; overflow: hidden; }
    [data-testid="stExpander"] details summary { background-color: #ffffff !important; color: #211919 !important; }
    [data-testid="stExpander"] details summary p { color: #211919 !important; font-weight: bold !important; }
    [data-testid="stExpander"] details summary:hover { background-color: #fff5f5 !important; }
    [data-testid="stExpander"] details div { background-color: #ffffff !important; color: #211919 !important; }
    [data-testid="stExpander"] p, [data-testid="stExpander"] span { color: #211919 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 4. 側邊欄設定 ---
with st.sidebar:
    logo_path = 'logo.png' 
    if os.path.exists(logo_path):
        st.image(logo_path, width="stretch") 
    
    st.header("☁️ 匯入 3D 測量數據")
    search_keyword = st.text_input("輸入 TG3D 帳號或關鍵字", placeholder="例如: 26020865")
    
    if st.button("⬇️ 載入數據並生成報告", use_container_width=True):
        if not search_keyword.strip():
            st.warning("請先輸入關鍵字！")
        else:
            with st.spinner("正在連接雲端撈取資料並分析..."):
                url_records = f'{BASE_URL}/scan_records?apikey={APIKEY}&limit=20&offset=0'
                try:
                    resp_records = requests.get(url_records, timeout=10)
                    resp_records.raise_for_status()
                    records = resp_records.json().get('records', [])
                    found = False

                    for record in records:
                        user_id = record.get('user_id')
                        tid = record.get('tid')
                        original_tags = record.get('tag_list', [])
                        if not user_id: continue

                        resp_user = requests.get(f'{BASE_URL}/users/{user_id}?apikey={APIKEY}', timeout=10)
                        if resp_user.status_code == 200:
                            user_data = resp_user.json()
                            username = user_data.get('user', {}).get('username', '')

                            if username and str(search_keyword) in str(username):
                                found = True
                                nickname = user_data.get('user', {}).get('nick_name') or user_data.get('nickname') or ''
                                
                                # 抓取數據
                                m_i = requests.get(f'{BASE_URL}/scan_records/{tid}/size_xt?apikey={APIKEY}&pose=I', timeout=10).json().get('measurement', {})
                                time.sleep(0.5)
                                m_a = requests.get(f'{BASE_URL}/scan_records/{tid}/size_xt?apikey={APIKEY}&pose=A', timeout=10).json().get('measurement', {})

                                # 處理標籤
                                cleaned_tags = [t for t in original_tags if t not in SHAPE_TAGS]
                                final_tags = cleaned_tags + ["(I-Pose Shape)"]
                                
                                # ⭐ 自動比對胸型屬性
                                matched_attr = "不確定胸型"
                                for tag in original_tags:
                                    if tag in ATTR_OPTIONS:
                                        matched_attr = tag
                                        break
                                
                                # 更新到 Session State
                                st.session_state['f_name'] = nickname
                                st.session_state['f_upper'] = get_tg3d_float(m_i, 'Chest Circumference', 82.0)
                                st.session_state['f_lower'] = get_tg3d_float(m_i, 'F Under Bust Circumference B', 65.0)
                                st.session_state['f_lsn'] = get_tg3d_float(m_a, 'NSP to Apex Length (Left)', 20.0)
                                st.session_state['f_rsn'] = get_tg3d_float(m_a, 'NSP to Apex Length (Right)', 20.0)
                                st.session_state['f_tags'] = final_tags
                                st.session_state['f_attr'] = matched_attr # 寫入比對到的胸型
                                
                                st.session_state['run_report'] = True 
                                break
                    if not found:
                        st.error("❌ 找不到此帳號的近期紀錄。")
                except Exception as e:
                    st.error(f"連線失敗: {e}")

    st.divider()

    st.header("👤 顧客資訊")
    user_name = st.text_input("姓名", value=st.session_state['f_name'], placeholder="請輸入姓名 (選填)") 
    user_email = st.text_input("📧 接收 Email", placeholder="example@mail.com (選填)")

    st.header("📏 數據測量")
    upper_chest = st.number_input("上胸圍 (cm)", 50.0, 150.0, float(st.session_state['f_upper']), 0.1)
    lower_chest = st.number_input("下胸圍 (cm)", 40.0, 120.0, float(st.session_state['f_lower']), 0.1)
    left_shoulder_nipple = st.number_input("頸肩-乳尖公分數(左) (cm)", 10.0, 50.0, float(st.session_state['f_lsn']), 0.1)
    right_shoulder_nipple = st.number_input("頸肩-乳尖公分數(右) (cm)", 10.0, 50.0, float(st.session_state['f_rsn']), 0.1)
    
    special_adjust = st.toggle("🛠️ 開啟特殊調整", help="選取「成熟承托型」時，上胸圍自動 +3cm 計算")
    
    st.header("🔎 胸型屬性")
    # 讀取 Session 裡面的胸型，設定為預設選項
    default_attr_index = ATTR_OPTIONS.index(st.session_state['f_attr']) if st.session_state['f_attr'] in ATTR_OPTIONS else 0
    selected_attr = st.selectbox("選擇顧客胸型", options=ATTR_OPTIONS, index=default_attr_index)
    
    if st.button("✨ 手動生成報告", use_container_width=True):
        st.session_state['run_report'] = True

# --- 5. 主要運算邏輯 ---
st.title("𝒟𝒶𝒾𝓁𝓎𝒷𝑒𝓁𝓁𝑒 專業尺寸建議系統")

SELECTED_FILE = "調整尺寸_2.58版.csv"

# 依序讀取檔案
size_table = load_csv_data(SELECTED_FILE)
product_mapping = load_csv_data('商品對應尺寸表.csv')
breast_attr = load_csv_data('胸型屬性.csv')
url_df = load_csv_data('款式官網連結.csv')

url_dict = pd.Series(url_df.官網連結.values, index=url_df.款式號碼.astype(str)).to_dict() if url_df is not None else {}

if size_table is not None and product_mapping is not None:
    if st.session_state.get('run_report', False):
        close_sidebar()
        calc_upper = upper_chest + 3.0 if (special_adjust and selected_attr == "成熟承托型") else upper_chest
        
        matches = size_table[
            (size_table['上胸圍1'] <= calc_upper) & (size_table['上胸圍2'] >= calc_upper) &
            (size_table['下胸圍1'] <= lower_chest) & (size_table['下胸圍2'] >= lower_chest)
        ]
        
        if not matches.empty:
            st.success(f"✅ 計算完成！根據上胸圍 **{upper_chest}** cm / 下胸圍 **{lower_chest}** cm 為您推薦以下尺寸：")
            
            # ⭐ 標籤改回黑底純文字格式，並使用逗號分隔
            if st.session_state['f_tags']:
                tags_text = "、".join(st.session_state['f_tags'])
                st.markdown(f"#### 📌 雲端判定標籤： **{tags_text}**")
                st.write("") # 空行排版
            
            email_body = f"【黛莉貝爾建議報表】\n"
            if user_name: email_body += f"親愛的 {user_name} 您好：\n\n"
            email_body += f"測量數據：\n  - 上胸圍 {upper_chest} cm / 下胸圍 {lower_chest} cm\n  - 頸肩-乳尖(左) {left_shoulder_nipple} cm / 頸肩-乳尖(右) {right_shoulder_nipple} cm\n判定屬性：{selected_attr}\n\n"
            
            attr_products = []
            if selected_attr != "不確定胸型" and breast_attr is not None:
                attr_products = breast_attr[breast_attr['胸型屬性'] == selected_attr]['款式代號'].astype(str).tolist()

            log_recommend_str = "" 
            for i, (_, row) in enumerate(matches.iterrows()):
                group_name = str(row['對應尺寸群組']) 
                size_label = row['對應尺寸請使用.號隔開']
                
                all_group_products = product_mapping[product_mapping['對應尺寸群組'].astype(str) == group_name]['款式代號'].astype(str).unique().tolist()
                final_products = all_group_products if selected_attr == "不確定胸型" else [p for p in all_group_products if p in attr_products]
                
                if final_products:
                    log_recommend_str += f"[方案{i+1}: 尺寸{size_label}, 款式:{'/'.join(final_products)}] "
                    with st.expander(f"方案 {i+1}：建議尺寸 {size_label} (群組 {group_name})", expanded=True):
                        email_body += f"方案 {i+1}：{size_label} (群組 {group_name})\n建議款式：{', '.join(final_products)}\n\n"
                        cols = st.columns(4)
                        for idx, p in enumerate(final_products):
                            url = url_dict.get(p)
                            display_text = f"[**{p}**]({url})" if url else f"**{p}**"
                            cols[idx % 4].markdown(f"{display_text}\n\n尺寸：{size_label}")
            
            save_log_to_gsheets(user_name, user_email, upper_chest, lower_chest, left_shoulder_nipple, right_shoulder_nipple, selected_attr, log_recommend_str)

            if user_email:
                with st.spinner('正在為您生成並寄送報告中...'):
                    if send_email(user_email, email_body):
                        st.toast(f"報告已成功寄送至 {user_email}")
        else:
            st.warning("⚠️ 查無匹配數據，請嘗試手動微調測量值。")

st.markdown("---")
st.caption("© 黛莉貝爾 Daily Belle - 專業美體系統 V5.2 (自動胸型帶入版)")