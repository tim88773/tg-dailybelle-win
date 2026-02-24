import streamlit as st
import requests
import time

# ==========================================
# 1. 基本與 API 設定
# ==========================================
# 透過 st.secrets 讀取 API Key
APIKEY = st.secrets["APIKEY"] 
BASE_URL = 'https://api.tg3ds.com/api/v1'
SHAPE_TAGS = {'Rectangle', 'Inverted Triangle', 'Triangle', 'Hourglass', 'Top Hourglass', 'Oval'}

# 輔助函式：安全取得數值
def get_val(data, key):
    if not data: return '無資料'
    item = data.get(key)
    if isinstance(item, dict):
        return item.get('value', '無資料')
    return item if item is not None else '無資料'

# ==========================================
# 2. Streamlit 網頁介面設計
# ==========================================
st.set_page_config(page_title="身形數據查詢系統", page_icon="📏", layout="centered")

st.title("📏 3D 身形數據查詢系統")
st.markdown("請輸入欲查詢的使用者帳號或關鍵字，系統將自動撈取最新的 I-Pose 與 A-Pose 數據。")

# 建立輸入框與按鈕
col_input, col_btn = st.columns([3, 1])
with col_input:
    search_keyword = st.text_input("SEARCH_KEYWORD", value="26020865", label_visibility="collapsed")
with col_btn:
    search_clicked = st.button("🔍 開始查詢", use_container_width=True)

st.divider() # 分隔線

# ==========================================
# 3. 查詢邏輯與畫面呈現
# ==========================================
if search_clicked:
    if not search_keyword.strip():
        st.warning("⚠️ 請先輸入關鍵字！")
    else:
        with st.spinner(f"正在搜尋「{search_keyword}」的資料..."):
            url_records = f'{BASE_URL}/scan_records?apikey={APIKEY}&limit=20&offset=0'
            
            try:
                resp_records = requests.get(url_records, timeout=10)
                resp_records.raise_for_status()
                records = resp_records.json().get('records', [])
                found_target = False

                for record in records:
                    user_id = record.get('user_id')
                    tid = record.get('tid')
                    original_tags = record.get('tag_list', [])

                    if not user_id: continue

                    # 取得用戶詳細資料
                    url_user = f'{BASE_URL}/users/{user_id}?apikey={APIKEY}'
                    resp_user = requests.get(url_user, timeout=10)
                    
                    if resp_user.status_code == 200:
                        user_data = resp_user.json()
                        user_obj = user_data.get('user', {})
                        username = user_obj.get('username', '')

                        # 關鍵字比對
                        if username and str(search_keyword) in str(username):
                            found_target = True
                            
                            real_name = user_data.get('real_name', '無資料')
                            nickname = user_obj.get('nick_name') or user_data.get('nickname') or '無資料'

                            # --- 顯示個人資訊區塊 ---
                            st.subheader("👤 用戶基本資訊")
                            info_col1, info_col2 = st.columns(2)
                            info_col2.markdown(f"**暱稱:** {nickname}")

                            # 處理並顯示標籤
                            cleaned_tags = [t for t in original_tags if t not in SHAPE_TAGS]
                            final_tags = cleaned_tags + ["(I-Pose Shape)"]
                            st.markdown(f"**📌 整合標籤:** `{', '.join(final_tags)}`")
                            
                            st.divider()

                            # --- 抓取量測數據 ---
                            measurements = {}
                            for pose in ['I', 'A']:
                                url_pose = f'{BASE_URL}/scan_records/{tid}/size_xt?apikey={APIKEY}&pose={pose}'
                                try:
                                    m_resp = requests.get(url_pose, timeout=10).json()
                                    measurements[pose] = m_resp.get('measurement', {})
                                except Exception:
                                    measurements[pose] = {}
                                time.sleep(0.5)

                            # --- 顯示量測數據 (使用 Metric 排版) ---
                            st.subheader("📏 量測數據結果")
                            
                            st.markdown("#### 👕 I-Pose 數據")
                            i_col1, i_col2 = st.columns(2)
                            i_col1.metric("胸圍", get_val(measurements['I'], 'Chest Circumference'))
                            i_col2.metric("胸下圍", get_val(measurements['I'], 'F Under Bust Circumference B'))

                            st.markdown("#### 🧍 A-Pose 數據")
                            a_col1, a_col2, a_col3 = st.columns(3)
                            a_col1.metric("左乳尖長", get_val(measurements['A'], 'NSP to Apex Length (Left)'))
                            a_col2.metric("右乳尖長", get_val(measurements['A'], 'NSP to Apex Length (Right)'))
                            a_col3.metric("頸肩點寬", get_val(measurements['A'], 'Neck Shoulder Points Width'))

                            a_col4, a_col5 = st.columns(2)
                            a_col4.metric("腰圍", get_val(measurements['A'], 'Narrow Waist Circumference'))
                            a_col5.metric("臀圍", get_val(measurements['A'], 'Low Hip Circumference'))

                            st.success("✅ 資料讀取完成！")
                            break # 找到目標後停止搜尋

                if not found_target:
                    st.error(f"❌ 找不到關鍵字「{search_keyword}」的紀錄。請確認帳號是否正確，或該帳號是否在最新的 20 筆紀錄中。")

            except Exception as e:
                st.error(f"❌ 連線或解析時發生錯誤: {e}")