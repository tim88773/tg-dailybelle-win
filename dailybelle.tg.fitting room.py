import streamlit as st
import pandas as pd
import requests
import time

# --- 1. 初始化與 Secrets 讀取 ---
st.set_page_config(page_title="黛莉貝爾智能量身系統", layout="wide")

# 安全讀取 API Key
if "TG3D_API_KEY" not in st.secrets:
    st.error("❌ 找不到 API 金鑰！請在 Streamlit Secrets 中設定 `TG3D_API_KEY`")
    st.stop()

API_KEY = st.secrets["TG3D_API_KEY"]
BASE_URL = "https://api.tg3ds.com/api/v1"
ATTR_KEYWORDS = ['下垂', '外擴', '副乳', '扁平', '雞胸', '不確定胸型']

# --- 2. 加載 CSV 資料 (請確保檔案在同目錄) ---
@st.cache_data
def load_csv():
    try:
        df_size = pd.read_csv("Size_Table.csv", encoding='utf-8-sig')
        df_product = pd.read_csv("Product_List.csv", encoding='utf-8-sig')
        return df_size, df_product
    except Exception as e:
        st.error(f"讀取 CSV 失敗: {e}")
        return None, None

df_size, df_product = load_csv()

# --- 3. 核心 API 抓取邏輯 ---
def fetch_data(keyword):
    # 搜尋掃描紀錄
    url_records = f'{BASE_URL}/scan_records?apikey={API_KEY}&limit=10&offset=0'
    resp = requests.get(url_records)
    
    if resp.status_code != 200:
        return None, f"API 連線失敗 (代碼:{resp.status_code})"
    
    records = resp.json().get('records', [])
    if not records:
        return None, "目前系統中無任何掃描紀錄"

    for record in records:
        uid = record.get('user_id')
        tid = record.get('tid')
        tags = record.get('tag_list', [])

        # 抓取用戶帳號比對
        u_resp = requests.get(f'{BASE_URL}/users/{uid}?apikey={API_KEY}')
        if u_resp.status_code == 200:
            user_info = u_resp.json()
            username = user_info.get('user', {}).get('username', '')

            # 匹配關鍵字
            if username.startswith(keyword):
                # 抓 I Pose (胸圍/下圍)
                data_I = requests.get(f'{BASE_URL}/scan_records/{tid}/size_xt?apikey={API_KEY}&pose=I').json().get('measurement', {})
                # 隔 1 秒避免卡頓
                time.sleep(1)
                # 抓 A Pose (乳尖)
                data_A = requests.get(f'{BASE_URL}/scan_records/{tid}/size_xt?apikey={API_KEY}&pose=A').json().get('measurement', {})

                # 數據整理
                upper = data_I.get('Chest Circumference', {}).get('value', 0)
                under_obj = data_I.get('Under Bust Circumference', {})
                lower = float(under_obj.get('front', 0)) + float(under_obj.get('back', 0))
                
                # 胸型識別
                attr = "不確定胸型"
                for t in tags:
                    for k in ATTR_KEYWORDS:
                        if k in t: attr = k
                
                return {
                    "username": username,
                    "name": user_info.get('real_name', username),
                    "upper": upper,
                    "lower": lower,
                    "attr": attr,
                    "nsp_l": data_A.get('NSP to Apex Length (Left)', {}).get('value', 0),
                    "nsp_r": data_A.get('NSP to Apex Length (Right)', {}).get('value', 0)
                }, None
    
    return None, f"找不到開頭為 '{keyword}' 的用戶紀錄"

# --- 4. Streamlit 介面 ---
st.title("👗 黛莉貝爾智能美體推薦")

with st.sidebar:
    st.header("🔍 數據同步")
    search_input = st.text_input("輸入手機或帳號前綴", placeholder="26020865")
    submit_btn = st.button("取得量身數據並推薦")

if submit_btn:
    if not search_input:
        st.warning("請先輸入帳號關鍵字")
    else:
        with st.spinner("🚀 正在跨雲端抓取 TG3D 數據，請稍候..."):
            result, err = fetch_data(search_input)
        
        if err:
            st.error(err)
        else:
            # 顯示結果
            st.success(f"✅ 已對接用戶：{result['name']}")
            
            # 數據儀表板
            m1, m2, m3 = st.columns(3)
            m1.metric("胸上圍 (I Pose)", f"{result['upper']} cm")
            m2.metric("胸下圍 (加總)", f"{round(result['lower'], 1)} cm")
            m3.info(f"識別標籤：{result['attr']}")

            # 尺寸推薦邏輯
            st.divider()
            st.subheader("🎯 智能尺寸方案")
            
            # 計算罩杯差
            cup_diff = result['upper'] - result['lower']
            
            # 從 CSV 篩選對應下圍區間
            if df_size is not None:
                match_size = df_size[(df_size['下圍下限'] <= result['lower']) & (df_size['下圍上限'] >= result['lower'])]
                if not match_size.empty:
                    st.write(f"根據下圍 {round(result['lower'],1)}，建議底圍尺寸為：**{match_size.iloc[0]['對應尺寸群組']}**")
                else:
                    st.warning("下圍數值超出對照表範圍，建議人工覆核。")

            # 產品篩選
            if df_product is not None:
                st.subheader(f"✨ 針對「{result['attr']}」推薦款式")
                products = df_product[df_product['胸型屬性'].str.contains(result['attr'])]
                if not products.empty:
                    for idx, p_row in products.head(3).iterrows():
                        st.write(f"🔹 {p_row['商品名稱']} (代碼: {p_row['款式代號']})")
                else:
                    st.write("目前無特定屬性款式，推薦黛莉貝爾經典機能款。")

            with st.expander("詳細量身參數"):
                st.json(result)