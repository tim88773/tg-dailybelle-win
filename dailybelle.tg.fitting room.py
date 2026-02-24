 import streamlit as st
import pandas as pd
import requests
import time
import os

# --- 1. 初始化設定 ---
st.set_page_config(page_title="黛莉貝爾智能美體系統", layout="wide")

# 從 Secrets 安全地讀取 API Key
try:
    API_KEY = st.secrets["TG3D_API_KEY"]
except:
    st.error("請在 secrets.toml 或 Cloud Secrets 中設定 TG3D_API_KEY")
    st.stop()

BASE_URL = "https://api.tg3ds.com/api/v1"
ATTR_KEYWORDS = ['下垂', '外擴', '副乳', '扁平', '雞胸', '不確定胸型']

# --- 2. 數據加載 (參考 ai3d0205.py) ---
@st.cache_data
def load_data():
    df_size = pd.read_csv("Size_Table.csv", encoding='utf-8-sig')
    df_product = pd.read_csv("Product_List.csv", encoding='utf-8-sig')
    # 預處理：確保群組格式正確
    if '對應尺寸群組' in df_size.columns:
        df_size['對應尺寸群組'] = df_size['對應尺寸群組'].astype(str).str.replace('.', ',', regex=False)
    return df_size, df_product

# --- 3. TG3D API 抓取邏輯 ---
def get_tg3d_measurements(keyword):
    # 撈取最新紀錄
    url_records = f'{BASE_URL}/scan_records?apikey={API_KEY}&limit=20&offset=0'
    resp = requests.get(url_records)
    if resp.status_code != 200: return None, "API 連線失敗"
    
    records = resp.json().get('records', [])
    for record in records:
        uid = record.get('user_id')
        tid = record.get('tid')
        tags = record.get('tag_list', [])

        # 比對帳號
        user_resp = requests.get(f'{BASE_URL}/users/{uid}?apikey={API_KEY}').json()
        username = user_resp.get('user', {}).get('username', '')

        if username.startswith(keyword):
            # 抓取 I Pose (胸圍/下圍)
            data_I = requests.get(f'{BASE_URL}/scan_records/{tid}/size_xt?apikey={API_KEY}&pose=I').json().get('measurement', {})
            # 隔一秒抓 A Pose (乳尖)
            time.sleep(1)
            data_A = requests.get(f'{BASE_URL}/scan_records/{tid}/size_xt?apikey={API_KEY}&pose=A').json().get('measurement', {})

            # 計算數值
            upper = data_I.get('Chest Circumference', {}).get('value', 0)
            under_obj = data_I.get('Under Bust Circumference', {})
            lower = float(under_obj.get('front', 0)) + float(under_obj.get('back', 0))
            
            # 識別胸型標籤
            detected_attr = "不確定胸型"
            for t in tags:
                for attr in ATTR_KEYWORDS:
                    if attr in t: detected_attr = attr
            
            return {
                "username": username,
                "name": user_resp.get('real_name', username),
                "upper": upper,
                "lower": lower,
                "attr": detected_attr,
                "nsp_l": data_A.get('NSP to Apex Length (Left)', {}).get('value', 0),
                "nsp_r": data_A.get('NSP to Apex Length (Right)', {}).get('value', 0)
            }, None
    return None, "找不到符合的掃描紀錄"

# --- 4. 介面與邏輯 ---
df_size, df_product = load_data()

st.title("💖 黛莉貝爾智能推薦 - API 自動化版")

search_key = st.sidebar.text_input("請輸入帳號關鍵字", placeholder="例如: 26020865")
if st.sidebar.button("獲取數據並推薦"):
    if search_key:
        with st.spinner("正在串接 TG3D 數據..."):
            data, error = get_tg3d_measurements(search_key)
            
        if error:
            st.error(error)
        else:
            # 顯示用戶基礎資料
            st.subheader(f"👤 客戶：{data['name']} ({data['username']})")
            c1, c2, c3 = st.columns(3)
            c1.metric("胸上圍 (I Pose)", f"{data['upper']} cm")
            c2.metric("胸下圍 (加總)", f"{round(data['lower'], 1)} cm")
            c3.info(f"自動識別胸型：{data['attr']}")

            # --- 推薦演算法 (根據您的 ai3d0205 邏輯) ---
            st.divider()
            diff = data['upper'] - data['lower']
            
            # 尺寸表匹配邏輯 (範例)
            row = df_size[(df_size['下圍下限'] <= data['lower']) & (df_size['下圍上限'] >= data['lower'])]
            
            if not row.empty:
                # 這裡可以根據 diff 找出對應罩杯 (您的 CSV 中應有罩杯差值對應)
                st.subheader("🎯 系統推薦方案")
                
                # 篩選產品標籤
                final_products = df_product[df_product['胸型屬性'].str.contains(data['attr'])]
                
                if not final_products.empty:
                    cols = st.columns(3)
                    for idx, p_row in final_products.head(3).iterrows():
                        with cols[idx % 3]:
                            st.success(f"款式：{p_row['商品名稱']}")
                            st.write(f"代號：{p_row['款式代號']}")
                            st.caption(f"適合您的 {data['attr']} 屬性")
                else:
                    st.warning("查無對應胸型的特定款式，建議選擇通用款。")
            else:
                st.error("量身數據超出尺寸表範圍，請手動校核。")

            with st.expander("查看原始量身細節"):
                st.write(f"頸肩至乳尖 (左): {data['nsp_l']}")
                st.write(f"頸肩至乳尖 (右): {data['nsp_r']}")