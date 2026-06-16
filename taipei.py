import pandas as pd
import concurrent.futures
import ast
import os
import json
import time
import random
import string
import re
import graphviz
import google.generativeai as genai
import urllib.parse
from datetime import datetime, timedelta, date
import requests
from io import BytesIO
import math
import concurrent.futures
import pandas as pd
import urllib3

# --- 1. 設定頁面配置 (必須放在最前面) ---
st.set_page_config(page_title="台灣旅遊小幫手", page_icon="✨", layout="wide")

# --- 2. API 設定 ---
# ⚠️ 請將此處換成您真實有效的 Google Gemini API Key
import streamlit as st
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
GOOGLE_MAPS_API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 1. 行程生成 (使用 2.0-flash)
    model = genai.GenerativeModel('models/gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
    
    # 2. 聊天對話 (使用 2.0-flash)
    chat_model = genai.GenerativeModel('models/gemini-2.0-flash') 
    
except Exception as e:
    st.error(f"API 設定錯誤：{e}")

# --- 設定 ---
USER_DB_FILE = 'users_db.json'
HISTORY_DB_FILE = 'history_db.json'
CSV_FILE_NAME = 'taipei_attractions2.csv'

# --- 3. Session State 初始化 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 'login'
if 'user_nickname' not in st.session_state:
    st.session_state['user_nickname'] = None
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = None
if 'trip_schedule' not in st.session_state:
    st.session_state['trip_schedule'] = {1: []}
if 'trip_days' not in st.session_state:
    st.session_state['trip_days'] = 1
if 'trip_start_date' not in st.session_state:
    st.session_state['trip_start_date'] = date.today()
if 'trip_end_date' not in st.session_state:
    st.session_state['trip_end_date'] = date.today()
if 'reset_email' not in st.session_state:
    st.session_state['reset_email'] = None
if 'reset_code' not in st.session_state:
    st.session_state['reset_code'] = None
if 'mode' not in st.session_state:
    st.session_state['mode'] = 'menu'
# [新增] 用於儲存 AI 模式的天氣資料
if 'ai_weather_df' not in st.session_state:
    st.session_state['ai_weather_df'] = None
# [新增] 用於儲存手動模式的快取 (包含特徵值與資料表)
if 'manual_weather_cache' not in st.session_state:
    st.session_state['manual_weather_cache'] = {"signature": "", "df": None}
# AI 模式專用 State
if 'ai_submitted' not in st.session_state:
    st.session_state['ai_submitted'] = False
if 'schedule_df' not in st.session_state:
    st.session_state['schedule_df'] = None
if 'input_dest' not in st.session_state:
    st.session_state['input_dest'] = "臺北市" # 預設值
if 'input_days' not in st.session_state:
    st.session_state['input_days'] = 1
if 'ai_start_date' not in st.session_state:
    st.session_state['ai_start_date'] = date.today()
if 'ai_end_date' not in st.session_state:
    st.session_state['ai_end_date'] = date.today()
if 'input_trans' not in st.session_state:
    st.session_state['input_trans'] = ["大眾運輸"]
if 'input_mixed' not in st.session_state:
    st.session_state['input_mixed'] = ""
if 'input_budget' not in st.session_state:
    st.session_state['input_budget'] = "中等預算 (舒適)"
if 'input_trans' not in st.session_state:
    st.session_state['input_trans'] = ["大眾運輸"]
if 'input_mixed' not in st.session_state:
    st.session_state['input_mixed'] = ""

# 對話紀錄
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = [
        {"role": "assistant", "content": "你好！我是你的 AI 旅遊顧問。告訴我您預計什麼時候出發？想去哪裡？想怎麼玩？"}
    ]

# --- 4. CSS 樣式整合 ---
st.markdown("""
    <style>
    /* 側邊欄樣式 */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        align-items: center !important;
        display: flex !important;
    }
    .day-header {
        font-weight: bold;
        color: #ff4b4b;
        margin-top: 15px;
        margin-bottom: 8px;
        font-size: 1.1em;
        border-bottom: 1px solid #ddd;
    }
    /* 聊天室樣式 */
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    /* 行程表樣式 (相容舊版 HTML) */
    .itinerary-box {
        font-family: "Microsoft JhengHei", sans-serif;
        line-height: 1.8;
        background-color: #FAFAFA;
        padding: 25px;
        border-radius: 10px;
        border: 1px solid #EEEEEE;
        margin-bottom: 20px;
    }
    .itinerary-day {
        font-size: 18px !important;
        font-weight: bold;
        color: #2E86C1 !important;
        margin-top: 20px;
        margin-bottom: 15px;
        border-bottom: 2px solid #EAEAEA;
        padding-bottom: 5px;
    }
    .itinerary-item, .itinerary-transport {
        font-size: 15px !important;
        color: #333333 !important; /* 加深字體顏色以適應白底 */
        margin-bottom: 8px;
    }
    .itinerary-transport {
        margin-left: 24px;
        color: #28a745 !important;
    }
    
    [data-testid="stVerticalBlockBorderWrapper"]:has(.itinerary-item) button:hover {
        border: 1px solid #00BFFF !important;
        color: #00BFFF !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 5. 共用輔助函式 ---
def load_users():
    if not os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    try:
        with open(USER_DB_FILE, 'r') as f:
            users = json.load(f)
        return users
    except json.JSONDecodeError:
        return {}

def save_user(email, password, nickname=None):
    users = load_users()
    if nickname is not None:
        users[email] = {"password": password, "nickname": nickname}
    elif email in users:
        users[email]["password"] = password
    with open(USER_DB_FILE, 'w') as f:
        json.dump(users, f)

def authenticate(email, password):
    users = load_users()
    
    if email in users:
        user_data = users[email]
        
        # [修正] 增加格式檢查：如果是舊版(字串)或非字典，回傳特殊錯誤碼
        if not isinstance(user_data, dict):
            return "DB_FORMAT_ERROR"
            
        # 正常的驗證邏輯
        if user_data.get("password") == password:
            return user_data.get("nickname")
            
    return None
def generate_verification_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

# --- 歷史紀錄相關函式 ---
def load_history():
    if not os.path.exists(HISTORY_DB_FILE):
        with open(HISTORY_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return []
    try:
        with open(HISTORY_DB_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        return history
    except json.JSONDecodeError:
        return []

def save_history_record(email, trip_name, days, schedule_data, mode_type, start_date_str=None, weather_data=None):
    """
    [修改] 新增 weather_data 參數以儲存天氣資訊
    """
    history = load_history()
    new_record = {
        "id": generate_verification_code(8),
        "email": email,
        "trip_name": trip_name,
        "days": days,
        "mode": mode_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_date": start_date_str,
        "data": schedule_data,
        "weather_content": weather_data # 新增欄位：儲存當時的天氣資料
    }
    history.append(new_record)
    with open(HISTORY_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def update_history_name_in_db(record_id, new_name):
    history = load_history()
    updated = False
    for r in history:
        if r['id'] == record_id:
            r['trip_name'] = new_name
            updated = True
            break
    if updated:
        with open(HISTORY_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=4)    
    return updated

def delete_history_record(record_id):
    history = load_history()
    new_history = [r for r in history if r['id'] != record_id]
    with open(HISTORY_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_history, f, ensure_ascii=False, indent=4)

@st.cache_data
def load_attractions():
    try:
        # 加入 on_bad_lines='skip' 來自動跳過格式錯誤（多出欄位）的行
        return pd.read_csv(CSV_FILE_NAME, encoding='utf-8', on_bad_lines='skip')
    except UnicodeDecodeError:
        try:
            return pd.read_csv(CSV_FILE_NAME, encoding='utf-8-sig', on_bad_lines='skip')
        except UnicodeDecodeError:
            try:
                return pd.read_csv(CSV_FILE_NAME, encoding='cp950', on_bad_lines='skip')
            except Exception as e:
                st.error(f"❌ CSV 編碼解析失敗：{e}")
                return None
    except FileNotFoundError:
        st.error(f"❌ 找不到檔案：'{CSV_FILE_NAME}'。請確認檔案是否與 Python 程式放在同一個資料夾。")
        return None
    except Exception as e:
        # 如果你的 Pandas 版本比較舊（< 1.3.0），不支援 on_bad_lines，請改用 error_bad_lines=False
        if "on_bad_lines" in str(e):
            try:
                return pd.read_csv(CSV_FILE_NAME, encoding='utf-8', error_bad_lines=False)
            except:
                pass
        st.error(f"❌ 讀取資料庫發生未知錯誤：{e}")
        return None

attractions_db = load_attractions()
SPOT_POS_CACHE = {}

if attractions_db is not None:
    # 預先處理：建立 "名稱 -> 座標" 的字典
    # 這樣做一次之後，後面查詢都不用再掃描資料庫了
    for _, row in attractions_db.iterrows():
        try:
            # 去除名稱前後空白，確保比對精準
            name = str(row['ScenicSpotName']).strip()
            # 解析座標字串
            pos_dict = ast.literal_eval(row['Position'])
            lat = pos_dict.get('PositionLat')
            lon = pos_dict.get('PositionLon')
            if lat and lon:
                SPOT_POS_CACHE[name] = (lat, lon)
        except:
            continue

# --- 新版的查詢函式 (直接查表，速度極快) ---
def get_lat_lon_by_name(place_name):
    """
    從快取字典查詢景點經緯度 (O(1) 複雜度)
    這比原本的 DataFrame 搜尋快上百倍
    """
    if not place_name: return None, None
    
    # 直接從字典拿，不用再跑 DataFrame filter
    # 這裡的 strip() 是為了防止 AI 產出的名稱前後多出空白
    return SPOT_POS_CACHE.get(str(place_name).strip(), (None, None))
@st.cache_data(ttl=3600)
def get_google_autocomplete(query):
    """根據使用者輸入，回傳 Google 預測的地點清單與 Place ID"""
    if not query: return {}
    
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": query,
        "key": GOOGLE_MAPS_API_KEY,
        "language": "zh-TW",
        "components": "country:tw" # 限定台灣，提高精準度
    }
    try:
        response = requests.get(url, params=params)
        results = response.json().get("predictions", [])
        # 建立 Dict: {"台北101觀景台": "ChIJ...place_id...", ...}
        return {res["description"]: res["place_id"] for res in results}
    except Exception as e:
        st.error(f"Autocomplete API 錯誤: {e}")
        return {}
@st.cache_data(ttl=86400) # 快取一天，節省成本
def get_google_place_details(place_id):
    """取得 Google 地點詳細資訊與營業時間"""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,rating,user_ratings_total,opening_hours,photos",
        "key": GOOGLE_MAPS_API_KEY,
        "language": "zh-TW"
    }
    try:
        res = requests.get(url, params=params).json()
        return res.get("result", {})
    except:
        return {}
def display_google_place_details(place_id, place_name):
    details = get_google_place_details(place_id)
    if not details:
        st.error("無法取得景點詳細資訊")
        return

    col_img, col_desc = st.columns([1, 1.5])
    
    with col_img:
        # 處理 Google Maps 圖片 (需要額外呼叫 Photo API)
        photos = details.get("photos", [])
        if photos:
            photo_ref = photos[0]["photo_reference"]
            img_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={GOOGLE_MAPS_API_KEY}"
            st.image(img_url, use_container_width=True, caption=details.get("name"))
        else:
            st.info("🖼️ 暫無圖片")

    with col_desc:
        st.subheader(f"📍 {details.get('name', place_name)}")
        
        # 星級評分
        rating = details.get('rating', '無')
        total_ratings = details.get('user_ratings_total', 0)
        st.markdown(f"⭐ **{rating}** ({total_ratings} 則評論)")
        
        st.caption(f"🏠 地址：{details.get('formatted_address', '無')}")
        st.caption(f"📞 電話：{details.get('formatted_phone_number', '無')}")
        
        # 營業時間與防呆機制
        opening_hours = details.get("opening_hours", {})
        if opening_hours:
            is_open_now = opening_hours.get("open_now", False)
            status_color = "green" if is_open_now else "red"
            status_text = "營業中" if is_open_now else "休息中"
            st.markdown(f"⏰ **目前狀態：** <span style='color:{status_color}'>{status_text}</span>", unsafe_allow_html=True)
            
            with st.expander("查看一週營業時間"):
                for day_text in opening_hours.get("weekday_text", []):
                    st.write(day_text)
                    
            # 🚨 防呆機制：檢查加入行程的那天是否休館
            check_closed_day_warning(opening_hours)
def check_closed_day_warning(opening_hours):
    """防呆檢查：比對使用者選擇的旅遊日期，若逢休館則跳出警告"""
    if 'trip_start_date' not in st.session_state: return
    
    # 假設這裡我們檢查的是「今天」往後推算的每一天
    # 在你的架構中，可以根據 st.selectbox 選擇的 target_day 來精準抓取日期
    # 這裡示範簡易版：如果有任何一天包含「休息」，給予通用警告
    weekday_text = opening_hours.get("weekday_text", [])
    closed_days = [text.split(":", 1)[0] for text in weekday_text if "休息" in text]
    
    if closed_days:
        st.warning(f"⚠️ **防呆提醒**：此景點在 **{'、'.join(closed_days)}** 休館，排入行程前請確認您的旅遊日期！")
        
def get_weather_data(lat, lon, target_date_str):
    """
    根據經緯度和日期抓取天氣資料。
    """
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"source": "Error", "temp_max": None, "precip": None, "unit": ""}

    # 如果沒有座標，預設用台北車站的座標嘗試抓取大範圍天氣
    if not lat or not lon:
        lat, lon = 25.0478, 121.5170 

    today = datetime.now().date()
    days_diff = (target_date - today).days
    is_forecast = 0 <= days_diff <= 14
    
    data = {
        "source": "Forecast" if is_forecast else "History",
        "date_used": target_date_str,
        "temp_max": None,
        "temp_min": None,
        "precip": None,
        "unit": ""
    }
    
    try:
        if is_forecast:
            # --- Forecast API ---
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "start_date": target_date_str,
                "end_date": target_date_str
            }
            response = requests.get(url, params=params, timeout=3)
            if response.status_code == 200:
                res_json = response.json()
                daily = res_json.get("daily", {})
                if daily.get("temperature_2m_max") and daily["temperature_2m_max"][0] is not None:
                    data["temp_max"] = daily["temperature_2m_max"][0]
                    data["temp_min"] = daily["temperature_2m_min"][0]
                    data["precip"] = daily["precipitation_probability_max"][0]
                    data["unit"] = "% (降雨機率)"
        else:
            # --- History API (去年同期) ---
            try:
                past_date = target_date.replace(year=target_date.year - 1)
            except ValueError:
                past_date = target_date.replace(year=target_date.year - 1, day=28)
            
            past_date_str = past_date.strftime("%Y-%m-%d")
            data["date_used"] = past_date_str
            
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": past_date_str,
                "end_date": past_date_str,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto"
            }
            response = requests.get(url, params=params, timeout=3)
            if response.status_code == 200:
                res_json = response.json()
                daily = res_json.get("daily", {})
                if daily.get("temperature_2m_max") and daily["temperature_2m_max"][0] is not None:
                    data["temp_max"] = daily["temperature_2m_max"][0]
                    data["temp_min"] = daily["temperature_2m_min"][0]
                    data["precip"] = daily["precipitation_sum"][0]
                    data["unit"] = "mm (歷史雨量)"
    except Exception as e:
        print(f"Weather API Error: {e}")
        
    return data

def get_lat_lon_by_name(place_name):
    """從 attractions_db 查詢景點的經緯度"""
    if attractions_db is None or not place_name:
        return None, None
    
    # 模糊比對名稱
    mask = attractions_db['ScenicSpotName'].str.contains(re.escape(place_name), na=False)
    matches = attractions_db[mask]
    
    if matches.empty:
        return None, None
    
    # 取第一筆資料
    row = matches.iloc[0]
    pos_str = row['Position']
    try:
        pos_dict = ast.literal_eval(pos_str)
        return pos_dict.get('PositionLat'), pos_dict.get('PositionLon')
    except:
        return None, None
def auto_move_night_markets_to_end(df):
    """
    自動將行程表中名稱包含「夜市」的景點，移至當天行程的最後一個順位。
    """
    if df is None or df.empty:
        return df
        
    adjusted_dfs = []
    # 逐日處理行程
    for day in sorted(df['Day'].unique()):
        day_df = df[df['Day'] == day].copy()
        
        # 找出名稱中包含「夜市」的景點
        is_night_market = day_df['Place'].astype(str).str.contains('夜市', na=False)
        
        # 分離：一般景點 與 夜市景點
        normal_spots = day_df[~is_night_market]
        night_markets = day_df[is_night_market]
        
        # 重新合併：一般景點在前，夜市在後
        combined_day_df = pd.concat([normal_spots, night_markets], ignore_index=True)
        
        # 重新整理 Order (1, 2, 3...)
        combined_day_df['Order'] = range(1, len(combined_day_df) + 1)
        
        adjusted_dfs.append(combined_day_df)
        
    # 將所有天數合併回一個 DataFrame
    final_df = pd.concat(adjusted_dfs, ignore_index=True)
    return final_df
def process_schedule_weather(schedule_df, start_date):
    """
    採用同日借用邏輯：若某景點抓不到天氣，自動取用同天其他景點的天氣資料。
    徹底消除「暫無資料」與「(地區預估)」。
    """
    if schedule_df is None or schedule_df.empty:
        return pd.DataFrame()

    current_schedule_set = set(schedule_df['Place'].astype(str).unique())
    weather_results = []
    
    outdoor_keywords = [
        "公園", "步道", "自行車道", "古道", "山", "河", "湖", "潭", "堤", "港", "碼頭",
        "廣場", "夜市", "商圈", "老街", "市集", "農場", "牧場", "花園", "苗圃", 
        "樂園", "動物園", "植物園", "露營", "吊橋", "景觀", "風景區", 
        "自然", "生態", "綠地", "林", "岩", "瀑布", "濕地", "大稻埕" 
    ]

    indoor_keywords = [
        "館", "中心", "百貨", "商場", "地下街", "影城", "誠品", "書店", 
        "OUTLET", "Outlet", "巨蛋", "娛樂城", "KTV", "101", "大樓", "展望台", 
        "宮", "廟", "寺", "教堂", "道場", "精舍", "溫泉", "賓館", "之家", "邸",
        "展覽", "廳", "室內", "飯店", "酒店", "旅店", "教會", "忠烈祠", 
        "故居", "茶行", "醫院", "診所", "摩天輪", "戲苑"
    ]

    def check_is_indoor(place_name):
        place_name = str(place_name)
        for kw in outdoor_keywords:
            if kw in place_name: return False
        for kw in indoor_keywords:
            if kw in place_name: return True
        return False 

    task_params = []
    for idx, row in schedule_df.iterrows():
        day_num = row['Day']
        place = row['Place']
        try:
            target_date = start_date + timedelta(days=int(day_num) - 1)
            target_date_str = target_date.strftime("%Y-%m-%d")
        except:
            target_date_str = date.today().strftime("%Y-%m-%d")
        
        lat, lon = get_lat_lon_by_name(place)
        task_params.append((idx, lat, lon, target_date_str))

    def fetch_weather_worker(param):
        idx, lat, lon, date_str = param
        return idx, get_weather_data(lat, lon, date_str)

    results_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_weather_worker, p) for p in task_params]
        for future in concurrent.futures.as_completed(futures):
            idx, data = future.result()
            results_map[idx] = data

    # --- 🟢 核心新增：尋找每一天的「標準天氣」(只要有抓到就算) ---
    valid_day_weather = {}
    for idx, row in schedule_df.iterrows():
        day_num = int(row['Day'])
        wd = results_map.get(idx, {})
        # 如果這個景點有成功抓到最高溫，就把它存起來當這天的備用天氣
        if wd.get('temp_max') is not None:
            if day_num not in valid_day_weather:
                valid_day_weather[day_num] = wd

    suggested_history = set()
    for idx, row in schedule_df.iterrows():
        place = str(row['Place']) 
        city = row['City'] if 'City' in row and pd.notna(row['City']) else ""
        day_num = int(row['Day'])
        
        weather_data = results_map.get(idx, {})
        lat, lon = get_lat_lon_by_name(place)
        is_indoor_spot = check_is_indoor(place)

        # --- 🟢 核心修正：如果此景點無資料，向同日其他景點「借用」 ---
        if weather_data.get('temp_max') is None:
            if day_num in valid_day_weather:
                weather_data = valid_day_weather[day_num].copy()
            else:
                # 萬一「整天」的景點 API 都掛了，給予絕對乾淨的保底數值 (無任何預估字眼)
                weather_data = {
                    "source": "Estimated",
                    "temp_max": 26.5,
                    "temp_min": 22.0,
                    "precip": 20,
                    "unit": "% (降雨機率)" 
                }

        # 1. 處理氣溫顯示
        if weather_data.get('temp_max') is not None:
            temp_str = f"{weather_data['temp_min']}°C - {weather_data['temp_max']}°C"
        else:
            temp_str = "22.0°C - 26.5°C" # 最終防線

        # 2. 處理降雨顯示
        precip_val = weather_data.get('precip')
        
        if is_indoor_spot:
            rain_str = "🏠 室內 (不受雨影響)"
        elif precip_val is not None:
            rain_str = f"{precip_val} {weather_data['unit']}"
        else:
            rain_str = "20 % (降雨機率)" # 最終乾淨防線

        # 3. 備註與雨天備案邏輯
        note_str = ""
        if weather_data.get('source') == "History": 
            note_str = "(歷史數據)"
        # 移除 (地區預估) 顯示
            
        is_raining = False
        if precip_val is not None and not is_indoor_spot:
            if weather_data.get('unit') and '%' in weather_data['unit']: 
                if precip_val >= 50: is_raining = True 
            else: 
                if precip_val >= 3.0: is_raining = True 
        
        if is_raining and lat and lon:
            backup = find_nearest_indoor_spot(lat, lon, city, exclude_name=place, used_suggestions=suggested_history, existing_spots=current_schedule_set)
            if backup:
                note_str += f" ⚠️易雨，建議改至室內：{backup}"
                suggested_history.add(backup)

        # 取得日期字串
        try:
            date_used = task_params[idx][3] if idx < len(task_params) else ""
        except:
            date_used = ""

        res = {
            "Day": int(row['Day']),
            "Date": date_used, 
            "Place": place,
            "Temp": temp_str,
            "Rain": rain_str,
            "Note": note_str.strip()
        }
        weather_results.append(res)
        
    return pd.DataFrame(weather_results)
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    計算兩點經緯度的距離 (單位: 公里)
    """
    R = 6371  # 地球半徑 (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def find_nearest_indoor_spot(current_lat, current_lon, city_name, exclude_name=None, used_suggestions=None, existing_spots=None):
    """
    [修正版] 尋找最近室內景點，並支援「排除重複推薦」、「排除戶外關鍵字」與「排除已存在行程」
    """
    if attractions_db is None: return None
    if used_suggestions is None: used_suggestions = set()
    if existing_spots is None: existing_spots = set() # [新增] 初始化
    
    # 1. 室內關鍵字 (正向)
    indoor_keywords = [
        "博物館", "美術館", "藝術館", "紀念館", "故事館", "文物館", "科博館", "天文館", 
        "海生館", "水族館", "圖書館", "演藝廳", "音樂廳", "劇院", "兩廳院", "戲院",
        "展覽", "中心", "百貨", "購物", "商場", "影城", "地下街", "誠品", "蔦屋", "書店", 
        "OUTLET", "Outlet", "商城", "巨蛋", "娛樂城",
        "酒廠", "觀光工廠", "醫館", "101", "大樓", "展望台", "觀景台", "塔",
        "宮", "廟", "教堂", "寺", "道場", "廳", "館", "紀念堂", "溫泉會館","車站","茶行"
    ]
    
    # 2. 必須排除的關鍵字 (負向)
    exclude_keywords = [
        "夜市", "老街", "商圈", "步道", "公園", "漁港", "碼頭", "遊客中心", "服務中心", 
        "廟口", "農場", "露營", "廣場"
    ]

    # 3. 建立篩選
    mask_city = attractions_db['City'] == city_name
    mask_indoor = attractions_db['ScenicSpotName'].str.contains('|'.join(indoor_keywords), na=False)
    mask_exclude = ~attractions_db['ScenicSpotName'].str.contains('|'.join(exclude_keywords), na=False)
    
    candidates = attractions_db[mask_city & mask_indoor & mask_exclude]
    
    if candidates.empty:
        candidates = attractions_db[mask_indoor & mask_exclude]
    
    if candidates.empty: return None

    nearest_spot = None
    min_dist = float('inf')

    # 4. 計算距離
    for _, row in candidates.iterrows():
        name = row['ScenicSpotName']
        
        # A. 排除自己 (原本的戶外景點)
        if exclude_name and (name == exclude_name or name in exclude_name or exclude_name in name):
            continue
            
        # B. 排除已經被推薦過的備案
        if name in used_suggestions:
            continue

        # C. [新增] 排除原本行程中已經存在的景點
        if name in existing_spots:
            continue
            
        try:
            pos_dict = ast.literal_eval(row['Position'])
            lat = pos_dict.get('PositionLat')
            lon = pos_dict.get('PositionLon')
            
            if lat and lon:
                dist = calculate_distance(current_lat, current_lon, lat, lon)
                if dist < min_dist:
                    min_dist = dist
                    nearest_spot = name
        except:
            continue
            
    return nearest_spot

def generate_clothing_advice(day_weather_df):
    """
    [極致精確版] 根據氣溫、溫差與降雨，提供包含材質、分層款式與配件的全方位穿搭建議。
    """
    if day_weather_df.empty:
        return "⚠️ 暫無數據，建議攜帶輕便雨具與薄外套以備不時之需。"

    min_temps = []
    max_temps = []
    rain_vals = []
    is_historical = False

    # --- 1. 數據解析 ---
    for _, row in day_weather_df.iterrows():
        # 解析氣溫 "18.5°C - 24.0°C"
        t_str = str(row['Temp'])
        if "N/A" not in t_str and "-" in t_str:
            try:
                parts = t_str.replace("°C", "").split("-")
                min_temps.append(float(parts[0].strip()))
                max_temps.append(float(parts[1].strip()))
            except: pass
        
        # 解析降雨 "30 % (降雨機率)" 或 "5.2 mm (歷史雨量)"
        r_str = str(row['Rain'])
        if "N/A" not in r_str:
            try:
                val = float(r_str.split()[0])
                rain_vals.append(val)
                if "歷史" in r_str: is_historical = True
            except: pass

    if not min_temps or not max_temps:
        return "⚠️ 氣溫資料不足，建議採取洋蔥式穿搭（短袖+薄外套）以應變。"

    # --- 2. 關鍵指標計算 ---
    day_min = min(min_temps)
    day_max = max(max_temps)
    day_avg = (day_min + day_max) / 2
    temp_diff = day_max - day_min # 溫差
    max_rain = max(rain_vals) if rain_vals else 0
    
    # 判斷降雨風險 (預報>40% 或 歷史>3mm)
    rain_risk = max_rain >= 40 if not is_historical else max_rain >= 3

    advice_blocks = []

    # --- 3. 🌡️ 精確氣溫感受與分層穿搭建議 ---
    body_advice = ""
    bottom_advice = ""
    
    if day_avg < 10: 
        status = "🥶 **極凍寒流**"
        body_advice = "🧥 **上身 (抗寒三層穿法)**：\n- **內層**：極暖發熱衣或羊毛純棉打底，貼身鎖溫。\n- **中層**：粗針織毛衣、厚刷毛大學T或高領毛線衫。\n- **外層**：防風防潑水的**厚羽絨大衣**或**GORE-TEX機能外套**。"
        bottom_advice = "👖 **下身**：內層加穿發熱褲/厚褲襪，外搭防風厚長褲或內刷毛牛仔褲。"
    elif 10 <= day_avg < 15: 
        status = "❄️ **濕冷刺骨**"
        body_advice = "🧥 **上身 (洋蔥式保暖)**：\n- **內層**：一般發熱衣或長袖厚棉T。\n- **中層**：法蘭絨襯衫、細針織衫或連帽T恤。\n- **外層**：**羊毛大衣**、**厚鋪棉外套**或**防風保暖夾克**。"
        bottom_advice = "👖 **下身**：厚磅牛仔褲、燈芯絨長褲或保暖長裙配加厚不透膚黑絲襪。"
    elif 15 <= day_avg < 20: 
        status = "🌬️ **偏涼微冷**"
        body_advice = "🧥 **上身 (靈活層次)**：\n- **內層**：短袖或薄長袖打底。\n- **中層**：長袖棉T、薄毛衣或秋季休閒服。\n- **外層**：**輕羽絨外套**、**皮衣**或**防風夾克**（機車族必備防風層）。"
        bottom_advice = "👖 **下身**：一般磅數牛仔褲、休閒長褲或長裙。"
    elif 20 <= day_avg < 24: 
        status = "🍂 **舒適涼爽**"
        body_advice = "👕 **上身 (早晚防溫差)**：\n- **主體**：**薄長袖**、七分袖或透氣棉質襯衫。\n- **外套**：早晚微涼，請備妥**薄風衣**、**牛仔外套**或**針織小罩衫**。"
        bottom_advice = "👖 **下身**：輕薄長褲、西裝寬褲或過膝中長裙。"
    elif 24 <= day_avg < 28: 
        status = "😊 **溫暖微熱**"
        body_advice = "👕 **上身 (清爽透氣)**：\n- **主體**：**短袖上衣**、雪紡衫或棉麻混紡短T。\n- **外套**：進出冷氣房必備**薄防曬外套**或**薄透絲質罩衫**以免著涼。"
        bottom_advice = "🩳 **下身**：透氣寬褲、九分褲、短褲或及膝裙。"
    elif 28 <= day_avg < 32: 
        status = "🔥 **炎熱流汗**"
        body_advice = "🎽 **上身 (排汗抗陽)**：\n- **主體**：**吸濕排汗**材質的短袖、無袖背心。盡量選擇淺色系以反射陽光。\n- **外套**：**抗UV防曬外套**（騎車或戶外活動必備）。"
        bottom_advice = "🩳 **下身**：短褲、涼感材質寬褲或短裙，避免厚重牛仔褲導致悶熱汗疹。"
    else: 
        status = "🥵 **酷暑難耐**"
        body_advice = "🎽 **上身 (極致涼感)**：\n- **主體**：極輕薄、**涼感透氣**的無袖或短袖。切忌厚重棉質以免流汗黏膩。\n- **💡 額外準備**：強烈建議多帶一件替換上衣，流汗後可隨時更換保持乾爽。"
        bottom_advice = "🩳 **下身**：運動短褲、亞麻極短褲或透氣排汗裙裝。"

    advice_blocks.append(f"### {status} (均溫約 {day_avg:.1f}°C)")
    advice_blocks.append(body_advice)
    advice_blocks.append(bottom_advice)

    # --- 4. 🧥 溫差對策 ---
    if temp_diff >= 8:
        advice_blocks.append(f"⚠️ **溫差警報**：單日高低溫差達 **{temp_diff:.1f}°C**！中午偏熱、早晚偏冷。**強烈建議「洋蔥式穿法」**，內層透氣、外層擋風，方便隨時穿脫以免感冒。")

    # --- 5. ☔ 降雨與鞋履對策 ---
    if rain_risk:
        if is_historical:
            rain_msg = f"🌧️ **有雨機率高** (歷史數據 {max_rain}mm)"
        else:
            rain_msg = f"🌧️ **降雨機率高** ({max_rain}%)"
        
        advice_blocks.append(f"{rain_msg}：請務必攜帶**折疊傘**。建議穿著**防水鞋、短靴或防滑涼鞋**，絕對避免穿著易吸水的帆布鞋或全白球鞋。")
        advice_blocks.append("💡 **下雨小撇步**：濕氣較重，建議避免穿著落地寬褲或長裙，以免褲腳全濕沾滿泥濘。")
    else:
        advice_blocks.append("👟 **鞋履建議**：天氣穩定，適合穿著**好走的運動鞋、休閒鞋**。若行程包含大量步行（如老街、園區），請避免穿剛買的新鞋或高跟鞋。")

    # --- 6. 🕶️ 配件與其他建議 ---
    accessories = []
    if day_max >= 28 or (day_max >= 25 and not rain_risk):
        accessories.append("☀️ 紫外線強必備：**墨鏡、遮陽帽、防曬乳**")
    if day_avg >= 28:
        accessories.append("💧 戶外解暑：**隨身風扇、涼感濕紙巾、水壺**")
    
    if day_min < 16:
        accessories.append("🧣 脖頸保暖：**圍巾或絲巾**")
    if day_min < 12:
        accessories.append("🧤 末梢保暖：**防風手套、毛帽**")
        accessories.append("🔥 取暖小物：**暖暖包**")

    if accessories:
        advice_blocks.append("🎒 **隨身加分配件**：\n- " + "\n- ".join(accessories))

    return "\n\n".join(advice_blocks)
# --- [新增] 處理雨天備案替換的 UI 邏輯 ---
def render_rain_swap_ui(day_weather_df, mode='ai', ui_context='main'):
    """
    偵測天氣資料中的建議備註，並產生替換按鈕。
    [修正重點] 加入去重邏輯與安全迴圈編號，徹底避免按鈕重複顯示與 Key 衝突！
    """
    # 1. 篩選出有「建議改至室內」的項目
    swap_candidates = day_weather_df[day_weather_df['Note'].str.contains("建議改至室內", na=False)]
    
    # 🟢 [核心修正 1] 根據景點名稱去重！避免同一天同個景點顯示兩次替換框
    swap_candidates = swap_candidates.drop_duplicates(subset=['Place'])
    
    if not swap_candidates.empty:
        st.markdown("#### ☔ 雨天備案建議")
        
        # 🟢 [核心修正 2] 加上 loop_i 迴圈計數器
        for loop_i, (idx, row) in enumerate(swap_candidates.iterrows()):
            original_spot = row['Place']
            note = row['Note']
            # 確保 day_val 是純整數
            try:
                day_val = int(float(row['Day']))
            except:
                day_val = 1
            
            # 解析備註文字，取出新景點名稱
            try:
                if "：" in note:
                    new_spot = note.split("：")[-1].strip()
                else:
                    continue
            except:
                continue

            col_msg, col_btn = st.columns([3.5, 1.5], vertical_alignment="center")
            with col_msg:
                st.warning(f"Day {day_val}: 偵測到 **{original_spot}** 可能下雨，建議更改為室內景點：**{new_spot}**")
            
            with col_btn:
                # 🟢 [核心修正 3] Key 中加入 loop_i，提供雙重防呆，保證按鈕 Key 絕對唯一
                btn_key = f"swap_{ui_context}_{mode}_{day_val}_{loop_i}_{original_spot}"
                
                if st.button(f"🔄 立即替換", key=btn_key, use_container_width=True):
                    if mode == 'ai':
                        # A. 修改 AI 行程表
                        if st.session_state['schedule_df'] is not None:
                            df = st.session_state['schedule_df']
                            
                            sch_days = df['Day'].fillna(0).astype(float).astype(int).astype(str)
                            tgt_day = str(int(day_val))
                            
                            sch_places = df['Place'].astype(str).str.strip()
                            tgt_place = str(original_spot).strip()
                            
                            mask = (sch_days == tgt_day) & (sch_places == tgt_place)
                            
                            if mask.any():
                                st.session_state['schedule_df'].loc[mask, 'Place'] = new_spot
                                
                                # 同步更新天氣快取
                                if st.session_state['ai_weather_df'] is not None:
                                    w_df = st.session_state['ai_weather_df']
                                    w_days = w_df['Day'].fillna(0).astype(float).astype(int).astype(str)
                                    w_places = w_df['Place'].astype(str).str.strip()
                                    w_mask = (w_days == tgt_day) & (w_places == tgt_place)
                                    
                                    if w_mask.any():
                                        st.session_state['ai_weather_df'].loc[w_mask, 'Place'] = new_spot
                                        st.session_state['ai_weather_df'].loc[w_mask, 'Note'] = "✅ 已更換為室內行程"
                                        st.session_state['ai_weather_df'].loc[w_mask, 'Rain'] = "🏠 室內 (不受雨影響)"
                                
                                st.toast(f"✅ 已將 {original_spot} 替換為 {new_spot}")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(f"⚠️ 找不到對應行程 '{original_spot}'，可能已被手動修改或刪除。")
                            
                    elif mode == 'manual':
                        # B. 修改手動行程清單
                        day_list = st.session_state['trip_schedule'].get(day_val, [])
                        
                        found_idx = -1
                        for i, spot in enumerate(day_list):
                            if str(spot).strip() == str(original_spot).strip():
                                found_idx = i
                                break
                                
                        if found_idx != -1:
                            day_list[found_idx] = new_spot
                            st.session_state['trip_schedule'][day_val] = day_list
                            
                            cache = st.session_state['manual_weather_cache']
                            if cache.get("df") is not None:
                                w_df = cache["df"]
                                w_days = w_df['Day'].fillna(0).astype(float).astype(int).astype(str)
                                w_places = w_df['Place'].astype(str).str.strip()
                                tgt_day = str(int(day_val))
                                tgt_place = str(original_spot).strip()
                                
                                w_mask = (w_days == tgt_day) & (w_places == tgt_place)
                                
                                if w_mask.any():
                                    w_df.loc[w_mask, 'Place'] = new_spot
                                    w_df.loc[w_mask, 'Note'] = "✅ 已更換為室內行程"
                                    w_df.loc[w_mask, 'Rain'] = "🏠 室內 (不受雨影響)"
                                    st.session_state['manual_weather_cache']['df'] = w_df
                            
                            new_manual_data = []
                            sorted_days = sorted(st.session_state['trip_schedule'].keys())
                            for d in sorted_days:
                                spots = st.session_state['trip_schedule'][d]
                                for i, s in enumerate(spots):
                                    c, dist = "", ""
                                    if 'attractions_db' in globals() and attractions_db is not None:
                                        r = attractions_db[attractions_db['ScenicSpotName'] == s]
                                        if not r.empty:
                                            c, dist = r.iloc[0]['City'], r.iloc[0]['District']
                                    t_key = f"{d}_{i}"
                                    t_val = st.session_state['manual_trans_data'].get(t_key, "自行開車")
                                    new_manual_data.append({"Day": int(d), "Order": i+1, "Place": s, "City": c, "District": dist, "Transport": t_val})
                            
                            new_sig = json.dumps(new_manual_data, sort_keys=True, ensure_ascii=False)
                            st.session_state['manual_weather_cache']['signature'] = new_sig
                            
                            st.toast(f"✅ 已將 {original_spot} 替換為 {new_spot}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                             st.error(f"⚠️ 找不到手動行程中的 '{original_spot}'，可能已被刪除。")
# --- 7. AI 邏輯與圖表函式 ---

def extract_trip_info(chat_text):
    """
    用於從對話中提取旅遊參數的函式
    """
    today_str = date.today().strftime("%Y-%m-%d")
    prompt = f"""
    你是旅遊助手。現在是 {today_str}。
    請分析以下使用者的對話內容，並提取最新的旅遊需求。
    如果使用者提到相關資訊，請更新對應欄位；如果沒提到，請保持 null 或根據上下文推斷。
    
    對話內容：
    {chat_text}
    
    請回傳 JSON 格式：
    {{
        "destination": "地點 (例如: 臺南市, 台北)",
        "start_date": "YYYY-MM-DD (根據使用者說的日期推算，例如 '下週五')",
        "end_date": "YYYY-MM-DD (若只說天數，請依開始日期推算)",
        "days": int (天數),
        "transport": ["交通方式1", "交通方式2"] (例如: ["高鐵", "租車"]),
        "preferences": "想去的景點 (字串)"
    }}
    """
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except:
        return None

def process_user_keywords(user_input):
    if not user_input: return []
    keywords = re.split(r'[ ,、;，\n]', user_input)
    clean_keywords = [k.strip() for k in keywords if k.strip()]
    corrected = []
    for k in clean_keywords:
        if "夜市" in k and "觀光" not in k:
            k = k.replace("夜市", "觀光夜市")
        corrected.append(k)
    return corrected

def get_attraction_data(destination, user_input="", themes=None):
    # [修正] 統一回傳 3 個值，並加入 themes 參數
    if attractions_db is None: return [], "", {"error": "no_data"}
    
    # 1. 統一 "台" -> "臺"
    destination = destination.replace("台", "臺")
    
    # 2. 切割關鍵字
    dest_keywords = re.split(r'[ ,、;，+/]', destination)
    dest_keywords = [k.strip() for k in dest_keywords if k.strip()] 
    
    if not dest_keywords:
        return [], "", {"error": "no_data"}

    # 3. 建立地點搜尋遮罩 (Mask)
    mask_loc = pd.Series([False] * len(attractions_db))
    for kw in dest_keywords:
        current_mask = (
            attractions_db['City'].str.contains(kw, na=False) | 
            attractions_db['Address'].str.contains(kw, na=False) |
            attractions_db['ScenicSpotName'].str.contains(kw, na=False)
        )
        mask_loc = mask_loc | current_mask

    # 4. 必須有圖片才算有效景點
    mask_pic = attractions_db['Picture'].str.contains('PictureUrl1', na=False)
    
    # 取得初步資料池
    base_pool = attractions_db[mask_loc & mask_pic]
    
    if base_pool.empty: return [], "", {"error": "no_data"}

    # --- 🟢 [核心新增] 絕對嚴格的主題過濾 ---
    if themes and 'NewCategory' in base_pool.columns:
        mask_theme = base_pool['NewCategory'].isin(themes)
        theme_pool = base_pool[mask_theme]
        
        if not theme_pool.empty:
            base_pool = theme_pool # 嚴格替換為只含該主題的景點
        else:
            # 如果過濾後一個景點都不剩，直接回傳嚴格錯誤，不准混入其他主題
            return [], "", {"error": "strict_theme_empty"}
    # ---------------------------------------

    keywords = process_user_keywords(user_input)
    priority_rows = pd.DataFrame()
    matched_keywords = {} 
    unmatched_keywords = [] 

    if keywords:
        for k in keywords:
            mask_name = base_pool['ScenicSpotName'].str.contains(re.escape(k), na=False)
            matches = base_pool[mask_name]
            if not matches.empty:
                best_match = matches.iloc[[0]] 
                priority_rows = pd.concat([priority_rows, best_match])
                matched_keywords[k] = best_match.iloc[0]['ScenicSpotName']
            else:
                unmatched_keywords.append(k)
    
    if not priority_rows.empty:
        priority_rows = priority_rows.drop_duplicates(subset=['ScenicSpotName'])
        remaining_pool = base_pool[~base_pool['ID'].isin(priority_rows['ID'])]
    else:
        remaining_pool = base_pool
        
    target_fill = 35
    if len(remaining_pool) > target_fill:
        general_rows = remaining_pool.sample(n=target_fill)
    else:
        general_rows = remaining_pool

    def format_list(df, is_priority=False):
        info = []
        for _, row in df.iterrows():
            name = row['ScenicSpotName']
            city = str(row['City'])
            dist = str(row['District'])
            open_time = str(row.get('OpenTime', '無資料')).replace('\n', ' ')
            desc = str(row.get('Description', ''))[:80].replace('\n', ' ') 
            prefix = "【必去(MUST VISIT)】" if is_priority else "- "
            info.append(f"{prefix}{name} (位於: {city}{dist}) | ⏰營業時間: {open_time} | 📖參考簡介: {desc}")
        return "\n".join(info)

    priority_str = format_list(priority_rows, is_priority=True)
    general_str = format_list(general_rows, is_priority=False)
    full_context_str = priority_str + "\n" + general_str
    priority_names = priority_rows['ScenicSpotName'].tolist() if not priority_rows.empty else []
    
    status_report = {"matched": matched_keywords, "unmatched": unmatched_keywords}
    
    return priority_names, full_context_str, status_report

    def format_list(df, is_priority=False):
        info = []
        for _, row in df.iterrows():
            name = row['ScenicSpotName']
            city = str(row['City'])
            dist = str(row['District'])
            
            # --- [新增] 提取營業時間與基礎簡介，讓 AI 有判斷依據 ---
            open_time = str(row.get('OpenTime', '無資料')).replace('\n', ' ')
            desc = str(row.get('Description', ''))[:80].replace('\n', ' ') # 取前80字即可，避免Token過載
            
            prefix = "【必去(MUST VISIT)】" if is_priority else "- "
            info.append(f"{prefix}{name} (位於: {city}{dist}) | ⏰營業時間: {open_time} | 📖參考簡介: {desc}")
        return "\n".join(info)

    priority_str = format_list(priority_rows, is_priority=True)
    general_str = format_list(general_rows, is_priority=False)
    full_context_str = priority_str + "\n" + general_str
    priority_names = priority_rows['ScenicSpotName'].tolist() if not priority_rows.empty else []
    
    status_report = {"matched": matched_keywords, "unmatched": unmatched_keywords}
    
    return priority_names, full_context_str, status_report
def get_transport_icon(transport_str):
    """根據交通方式文字返回對應的 icon"""
    if not transport_str or str(transport_str) == "None":
        return "🚌" # 預設圖示
    
    t = str(transport_str)
    
    # 1. 先判斷軌道運輸
    if "高鐵" in t: return "🚅"
    if "火車" in t or "臺鐵" in t or "台鐵" in t: return "🚆"
    if "捷運" in t or "MRT" in t or "輕軌" in t: return "🚇"
    
    # 2. 判斷公路大眾運輸
    if "公車" in t or "客運" in t or "巴士" in t or "台灣好行" in t: return "🚌"
    
    # 3. [修正重點] 擴充開車的關鍵字：加入 "驅車"、"行駛"、"小客車"
    if ("開車" in t or "計程車" in t or "租車" in t or "Uber" in t or 
        "自駕" in t or "驅車" in t or "行駛" in t or "小客車" in t): 
        return "🚗"
        
    # 4. 其他
    if "機車" in t or "騎車" in t: return "🛵"
    if "腳踏車" in t or "單車" in t or "YouBike" in t: return "🚲"
    if "步行" in t or "走路" in t or "散步" in t: return "🚶"
    if "船" in t or "渡輪" in t: return "⛴️"
    if "飛機" in t: return "✈️"
    
    # 5. 若以上都沒抓到，預設回傳什麼？
    # 既然您主要設定是自行開車，這裡可以考慮改成預設回傳 🚗，或者維持 🚌
    # 如果希望「自行開車」模式下，未知的都顯示車子，可以把這裡改成 "🚗"
    return "🚌"
def generate_html_display(df, start_date=None, weather_df=None):
    """
    [完美還原版] 乾淨白底排版 + 時間軸 + 靜態天氣標籤
    """
    html_content = "" 
    if df is None or df.empty or 'Place' not in df.columns or 'Day' not in df.columns:
        return "<div style='color:red; padding: 10px; font-weight: bold;'>⚠️ 系統提示：行程格式異常。</div>"

    df = df[df['Place'].notna() & (df['Place'] != "")]
    df = df.sort_values(by=["Day", "Order"])
    unique_days = sorted(df['Day'].unique())
    
    for day in unique_days:
        day_val = int(day)
        html_content += '<div class="itinerary-box">'
        
        # 🗓️ 日期標題
        date_info = ""
        if start_date:
            curr_date = start_date + timedelta(days=day_val - 1)
            date_info = f" <span style='font-size:0.8em; color:#666;'>({curr_date.strftime('%m/%d')})</span>"
        html_content += f'<div class="itinerary-day">🗓️ 第 {day_val} 天{date_info}</div>'
        
        day_items = df[df['Day'] == day]
        for _, row in day_items.iterrows():
            place = row['Place']
            
            # 1. 縣市區域
            city = row.get('City', '') if pd.notna(row.get('City', '')) else ""
            district = row.get('District', '') if pd.notna(row.get('District', '')) else ""
            loc_str = f" <span style='font-size: 0.85em; color: #888888; font-weight: normal;'>({city}{district})</span>" if city or district else ""

            # 2. 時間與建議停留
            sched_time = row.get('ScheduleTime', '')
            duration = row.get('StayDuration', '')
            time_tag = f"<span style='color: #ff4b4b; font-weight: bold; font-size: 0.9em;'>[{sched_time}]</span>" if sched_time else ""
            duration_tag = f"<span style='color: #666; font-size: 0.85em; margin-left: 10px;'>⏱️ 建議停留：{duration}</span>" if duration else ""

            # 3. ⛅ [新增] 天氣標籤 (融合在 HTML 中)
            weather_tag = ""
            if weather_df is not None and not weather_df.empty:
                try:
                    w_days = weather_df['Day'].fillna(0).astype(float).astype(int).astype(str)
                    w_places = weather_df['Place'].astype(str).str.strip()
                    mask = (w_days == str(day_val)) & (w_places == str(place).strip())
                    if mask.any():
                            w_row = weather_df[mask].iloc[0]
                            w_temp = w_row.get('Temp', '').replace('°C', '')
                            
                            w_rain_raw = str(w_row.get('Rain', ''))
                            w_note = str(w_row.get('Note', ''))
                            
                            # 1. 先判斷戶外天氣圖示 (預設太陽，視情況換雨傘)
                            w_icon = "⛅"
                            if "建議改至室內" in w_note:
                                w_icon = "☔"
                            elif "已更換" in w_note:
                                w_icon = "⛅" # 雖然用不到，但維持邏輯完整
                            elif "%" in w_rain_raw:
                                try:
                                    if float(w_rain_raw.split()[0]) >= 50:
                                        w_icon = "☔"
                                except: pass
                            
                            # 2. 組合按鈕文字
                            if "室內" in w_rain_raw or "已更換" in w_note:
                                # 🟢 [終極修改] 室內景點：房屋圖示放最前面，後面單純寫室內
                                btn_label = f"🏠 {w_temp}°C | 室內"
                            else:
                                # 🟢 戶外景點：顯示天氣圖示、氣溫，以及降雨機率
                                w_rain_display = f"雨 {w_rain_raw.split()[0]}%" if "%" in w_rain_raw else f"雨 {w_rain_raw}"
                                btn_label = f"{w_icon} {w_temp}°C | {w_rain_display}"
                            weather_tag = f"<span style='color: #0066cc; font-size: 0.8em; margin-left: 10px; background-color: #e6f3ff; padding: 2px 8px; border-radius: 12px; border: 1px solid #b3d9ff;'>{icon} {w_temp}°C | 雨 {w_rain}</span>"
                except:
                    pass

            # 📍 組合主標題行
            html_content += f'''
                <div class="itinerary-item">
                    {time_tag} 📍 <strong>{place}</strong>{loc_str} {duration_tag}{weather_tag}
                </div>
            '''
            
            # 💡 景點簡介 (維持您最愛的藍色左邊線)
            desc = row.get('ShortDesc', row.get('Description', ''))
            if pd.notna(desc) and str(desc).strip():
                html_content += f'<div style="font-size: 13px; color: #666; margin-left: 28px; margin-bottom: 8px; border-left: 3px solid #00BFFF; padding-left: 10px; background-color: #f4faff;">💡 {desc}</div>'
            
            # └─ 交通方式 (綠色字體)
            trans = row.get('Transport', '')
            if pd.notna(trans) and str(trans) != "None" and str(trans).strip():
                icon = get_transport_icon(trans)
                html_content += f'<div class="itinerary-transport">└─ {icon} {trans}</div>'
            
        html_content += '</div>'
    return html_content
# --- [新增] 點擊天氣 ICON 後跳出的詳細資訊視窗 ---
@st.dialog("⛅ 當地天氣與穿搭詳情", width="large")
def show_weather_details_dialog(place_name, weather_row, mode):
    st.subheader(f"📍 {place_name}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**🌡️ 氣溫預測：**<br>{weather_row.get('Temp', '未知')}", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**☔ 降雨資訊：**<br>{weather_row.get('Rain', '未知')}", unsafe_allow_html=True)
        
    note = weather_row.get('Note', '')
    if pd.notna(note) and str(note).strip():
        st.warning(f"**💡 備註：** {note}")
    
    # 建立暫存 DataFrame 供下方兩支函式使用
    temp_df = pd.DataFrame([weather_row])
    
    # 🟢 [順序對調 1] 先顯示：雨天備案的替換按鈕 (優先讓使用者操作)
    render_rain_swap_ui(temp_df, mode, ui_context='dialog')
    
    # 🟢 [順序對調 2] 後顯示：穿搭與準備建議
    st.markdown("#### 👗 穿搭與準備建議")
    advice = generate_clothing_advice(temp_df)
    st.info(advice)

@st.cache_data(ttl=86400)
def get_lat_lon_fallback(place_name):
    """
    先查本地資料庫，找不到再求助 Google Maps API。
    (專門解決「自訂出發點」或「飯店」算不出距離的問題)
    """
    if not place_name: return None, None
    
    # 1. 先查本地資料庫
    lat, lon = get_lat_lon_by_name(place_name)
    if lat and lon:
        return lat, lon
        
    # 2. 本地沒有？呼叫 Google Maps API 抓取
    GOOGLE_MAPS_API_KEY = "AIzaSyDu7U5Fvot2xJeHX9N6U3bWWUu6Minq3ig"
    try:
        url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        params = {
            "input": place_name,
            "inputtype": "textquery",
            "fields": "geometry",
            "key": GOOGLE_MAPS_API_KEY
        }
        res = requests.get(url, params=params, verify=False, timeout=3).json()
        candidates = res.get("candidates", [])
        if candidates:
            loc = candidates[0].get("geometry", {}).get("location", {})
            if loc:
                return loc.get("lat"), loc.get("lng")
    except:
        pass
        
    return None, None

# --- [高質感深色版] 第一站防呆、完美計算交通時間的渲染器 ---
# --- [高質感深色版] 第一站防呆、完美計算交通時間的渲染器 ---
def render_itinerary_with_weather_icons(df, weather_df=None, start_date=None, mode='ai'):
    if df is None or df.empty:
        st.warning("⚠️ 尚無行程資料")
        return

    df = df.sort_values(by=["Day", "Order"])
    unique_days = sorted(df['Day'].unique())

    # 注入 CSS 確保按鈕與排版穩定
    st.markdown("""
    <style>
    .weather-btn-container button {
        background-color: transparent !important;
        border: 1px solid #4B5563 !important; 
        color: #D1D5DB !important; 
        border-radius: 8px !important;
        transition: all 0.3s ease;
    }
    .weather-btn-container button:hover {
        border: 1px solid #60A5FA !important; 
        color: #60A5FA !important;
        background-color: rgba(96, 165, 250, 0.08) !important; 
    }
    </style>
    """, unsafe_allow_html=True)

    for day in unique_days:
        day_val = int(day)
        
        # --- 🟢 確保空字串也能完美啟動預設值 ---
        if day_val == 1:
            prev_place = st.session_state.get('final_start_pt', '').strip()
            if not prev_place:
                prev_place = "臺北車站"
        else:
            prev_day_data = df[df['Day'] == day_val - 1].sort_values('Order')
            if not prev_day_data.empty:
                prev_place = prev_day_data.iloc[-1]['Place']
            else:
                prev_place = st.session_state.get('final_start_pt', '').strip()
                if not prev_place:
                    prev_place = "臺北車站"
        
        date_info = ""
        if start_date:
            curr_date = start_date + timedelta(days=day_val - 1)
            date_info = f" <span style='font-size:0.8em; color:#9CA3AF;'>({curr_date.strftime('%m/%d')})</span>"
        
        with st.container(border=True):
            st.markdown(f"<div style='font-size: 1.3em; font-weight: bold; margin-bottom: 15px; color: #76A9FA;'>🗓️ 第 {day_val} 天{date_info}</div>", unsafe_allow_html=True)
            
            day_items = df[df['Day'] == day]
            
            for idx, row in day_items.iterrows():
                place = row['Place']
                
                # --- 天氣資訊處理 ---
                w_row = None
                btn_label = "⛅ 查看天氣"
                w_icon = "⛅"
                if weather_df is not None and not weather_df.empty:
                    try:
                        w_days = weather_df['Day'].fillna(0).astype(float).astype(int).astype(str)
                        w_places = weather_df['Place'].astype(str).str.strip()
                        mask = (w_days == str(day_val)) & (w_places == str(place).strip())
                        
                        if mask.any():
                            w_row = weather_df[mask].iloc[0]
                            w_temp = w_row.get('Temp', '').replace('°C', '')
                            
                            w_rain_raw = str(w_row.get('Rain', ''))
                            w_note = str(w_row.get('Note', ''))
                            
                            # 1. 判斷天氣圖示
                            w_icon = "⛅"
                            if "建議改至室內" in w_note:
                                w_icon = "☔"
                            elif "已更換" in w_note:
                                w_icon = "⛅"
                            elif "%" in w_rain_raw:
                                try:
                                    if float(w_rain_raw.split()[0]) >= 50:
                                        w_icon = "☔"
                                except: pass
                            
                            # 2. 組合按鈕文字
                            if "室內" in w_rain_raw or "已更換" in w_note:
                                btn_label = f"🏠 {w_temp}°C | 室內"
                            else:
                                w_rain_display = f"雨 {w_rain_raw.split()[0]}%" if "%" in w_rain_raw else f"雨 {w_rain_raw}"
                                btn_label = f"{w_icon} {w_temp}°C | {w_rain_display}"
                    except: pass

                # --- 🟢 切割為 3 個區塊：左(6.5) 中(1.5) 右(2.0) ---
                col_info, col_view, col_btn = st.columns([5.5, 1.5, 2.0], vertical_alignment="center")                
                with col_info:
                    city = row.get('City', '') if pd.notna(row.get('City', '')) else ""
                    district = row.get('District', '') if pd.notna(row.get('District', '')) else ""
                    loc_str = f"({city}{district})" if city or district else ""
                    sched_time = row.get('ScheduleTime', '')
                    duration = row.get('StayDuration', '')
                    time_tag = f"[{sched_time}]" if sched_time else ""
                    duration_tag = f"⏱️ 建議停留：{duration}" if duration else ""
                    
                    st.markdown(f"**<span style='color:#FCA5A5;'>{time_tag}</span> 📍 <span style='color:#F3F4F6;'>{place}</span>** <span style='color:#9CA3AF; font-size:0.85em; margin-left: 5px;'>{loc_str} {duration_tag}</span>", unsafe_allow_html=True)
                    
                    desc = row.get('ShortDesc', row.get('Description', ''))
                    if pd.notna(desc) and str(desc).strip():
                        st.markdown(f"<div style='border-left: 3px solid #3B82F6; background-color: rgba(59, 130, 246, 0.1); padding: 5px 10px; margin-left: 5px; color: #D1D5DB; font-size: 0.9em; margin-bottom: 6px; border-radius: 0 4px 4px 0;'>💡 {desc}</div>", unsafe_allow_html=True)
                    
                    # 動態計算整體交通時間
                    trans = row.get('Transport', '')
                    if pd.notna(trans) and str(trans).strip() and str(trans) != "None":
                        est_time_str = ""
                        if prev_place:
                            lat1, lon1 = get_lat_lon_fallback(prev_place)
                            lat2, lon2 = get_lat_lon_fallback(place)
                            
                            if lat1 and lon1 and lat2 and lon2:
                                travel_time = estimate_travel_time(lat1, lon1, lat2, lon2, trans)
                                if travel_time:
                                    est_time_str = f" <span style='color: #D1D5DB; font-size: 0.9em;'>⏳ (預估交通時間：{travel_time})</span>"

                        icon = get_transport_icon(trans)
                        st.markdown(f"<div style='color: #6EE7B7; font-size: 0.9em; margin-left: 5px;'>└─ {icon} {trans}{est_time_str}</div>", unsafe_allow_html=True)

                # --- 🟢 中間區塊：查看資料按鈕 ---
                with col_view:
                    if st.button("🔍 查看資料", key=f"view_info_{mode}_{day_val}_{idx}", use_container_width=True):
                        # 傳入 day_val, idx, mode，啟動視窗內的「類似景點與替換」功能
                        show_spot_details_dialog(place, day_val=day_val, idx=idx, mode=mode)

                # --- 🟢 右側區塊：天氣與穿搭按鈕 ---
                with col_btn:
                    if w_row is not None:
                        st.markdown('<div class="weather-btn-container">', unsafe_allow_html=True)
                        if st.button(btn_label, key=f"w_btn_{mode}_{day_val}_{idx}", use_container_width=True):
                            show_weather_details_dialog(place, w_row, mode)
                        st.markdown('</div>', unsafe_allow_html=True)
                
                if idx != day_items.index[-1]:
                    st.markdown("<hr style='margin: 12px 0px; border-top: 1px solid #374151;'>", unsafe_allow_html=True)
                
                # 更新上一站紀錄
                prev_place = place
        st.write("")

def estimate_travel_time(lat1, lon1, lat2, lon2, transport_str):
    """
    根據兩點距離與交通方式，智慧估算整體交通時間 (包含大眾運輸 + 步行)
    """
    if not lat1 or not lon1 or not lat2 or not lon2:
        return None
        
    # 1. 計算直線距離 (公里)
    dist = calculate_distance(lat1, lon1, lat2, lon2)
    t_str = str(transport_str)
    
    # 2. 判斷主要交通工具時速 (由快到慢排序，抓取最高優先級)
    speed = 40.0 # 預設市區車速 (汽車)
    if "高鐵" in t_str: speed = 120.0
    elif "火車" in t_str or "臺鐵" in t_str or "台鐵" in t_str: speed = 60.0
    elif "捷運" in t_str or "MRT" in t_str or "輕軌" in t_str: speed = 20.0
    elif "公車" in t_str or "客運" in t_str or "巴士" in t_str: speed = 15.0
    elif "機車" in t_str or "騎車" in t_str: speed = 30.0
    elif "開車" in t_str or "計程車" in t_str or "Uber" in t_str or "自駕" in t_str: speed = 40.0
    elif "腳踏車" in t_str or "單車" in t_str or "YouBike" in t_str: speed = 15.0
    elif "步行" in t_str or "走路" in t_str or "散步" in t_str: speed = 4.0
    
    # 3. 計算基礎搭車/行車時間 (分鐘)
    base_minutes = int((dist * 1.2 / speed) * 60)
    
    # 4. 智慧解析 AI 提供的「步行 X 分鐘」
    extra_walk_mins = 0
    if "步行" in t_str or "走路" in t_str:
        # 使用正則表達式抓取 "步行約5分鐘" 裡面的數字
        match = re.search(r'(?:步行|走路).*?(\d+)\s*分', t_str)
        if match:
            extra_walk_mins = int(match.group(1))
        else:
            extra_walk_mins = 5 # 有提到步行但沒寫數字，預設加 5 分鐘
            
    # 5. 總計時間組合
    if speed > 4.0:
        # 若有搭乘交通工具，則疊加最後一哩路的步行時間
        total_minutes = base_minutes + extra_walk_mins
    else:
        # 若為純步行，以計算出的時間與 AI 給的時間取大值，避免重複計算
        total_minutes = max(base_minutes, extra_walk_mins)
        
    # 確保最少 1 分鐘
    if total_minutes < 1: 
        total_minutes = 1
        
    # 6. 格式化輸出
    if total_minutes >= 60:
        h = total_minutes // 60
        m = total_minutes % 60
        return f"{h} 小時 {m} 分鐘"
    else:
        return f"{total_minutes} 分鐘"
    
def generate_plain_text(df, start_date=None):
    txt_content = f"【{st.session_state.get('input_dest', '行程')} 旅遊規劃表】\n"
    txt_content += "="*30 + "\n\n"
    df = df[df['Place'].notna() & (df['Place'] != "")]
    df = df.sort_values(by=["Day", "Order"])
    current_day = 0
    for index, row in df.iterrows():
        day_val = int(row['Day']) if pd.notna(row['Day']) else 1
        if day_val != current_day:
            current_day = day_val
            date_str = ""
            if start_date:
                curr_date = start_date + timedelta(days=day_val - 1)
                date_str = f" ({curr_date.strftime('%Y-%m-%d')})"
            txt_content += f"\n[ Day {current_day}{date_str} ]\n"
            txt_content += "-"*15 + "\n"
        place = row['Place']
        city = row['City'] if pd.notna(row['City']) else ""
        district = row['District'] if pd.notna(row['District']) else ""
        loc_str = f"({city} {district})" if city or district else ""
        txt_content += f"📍 {place} {loc_str}\n"
        if row['Transport'] and str(row['Transport']) != "None" and str(row['Transport']) != "":
            icon = get_transport_icon(row['Transport']) # 加入這行
            txt_content += f"   └── {icon} 交通：{row['Transport']}\n" # 修改這行
        txt_content += "\n"
    return txt_content

def generate_dot_from_df(df):
    df = df[df['Place'].notna() & (df['Place'] != "")]
    if df.empty: return None
    df = df.sort_values(by=["Day", "Order"])
    
    dot = 'digraph G {\n'
    dot += '  graph [rankdir=LR, splines=polyline, fontname="Microsoft JhengHei", nodesep=1.2, ranksep=1.5];\n'
    dot += '  node [shape=box, style="filled,rounded", color="lightblue", fontname="Microsoft JhengHei"];\n'
    dot += '  edge [fontname="Microsoft JhengHei", fontsize=9];\n'
    
    days = sorted(df['Day'].dropna().unique())
    if not days: days = [1]
    
    for day in days:
        day = int(day)
        day_df = df[df['Day'] == day]
        if day_df.empty: continue
        
        dot += f'  subgraph cluster_day{day} {{\n'
        dot += f'    label="Day {day}";\n'
        dot += '    style="filled"; color="#f0f2f6";\n'
        
        # --- 🟢 新增：判斷這天的出發起點是哪裡 ---
        if day == 1:
            # 第一天的起點抓取全域設定
            start_place = st.session_state.get('final_start_pt', '出發點')
        else:
            # 第二天之後，起點為前一天的最後一個景點
            prev_day_df = df[df['Day'] == day - 1].sort_values(by="Order")
            if not prev_day_df.empty:
                start_place = prev_day_df.iloc[-1]['Place']
            else:
                start_place = st.session_state.get('final_start_pt', '出發點')
        
        # 🟢 新增：畫出一個淺綠色的「起點方塊」
        start_node_id = f"start_{day}"
        dot += f'    {start_node_id} [label=<<B>🚩 {start_place}</B>>, color="#c2f0c2"];\n'
        
        # 🟢 關鍵：把上一站預設為「起點方塊」，這樣第一條交通線碼就會連上了！
        prev_node = start_node_id
        
        for idx, row in day_df.iterrows():
            node_id = f"node_{idx}"
            place_name = row['Place']
            dot += f'    {node_id} [label=<<B>{place_name}</B>>];\n'
            
            # 抓取交通方式
            transport = row['Transport'] if pd.notna(row['Transport']) and row['Transport'] else "前往"
            short_transport = transport[:15] + "..." if len(transport) > 15 else transport
            
            # 畫出箭頭與文字
            dot += f'    {prev_node} -> {node_id} [label="{short_transport}"];\n'
            
            prev_node = node_id
        dot += '  }\n'
    dot += '}'
    return dot

def display_attraction_details(place_name):
    if attractions_db is None or place_name is None: return
    mask = attractions_db['ScenicSpotName'].str.contains(place_name, na=False, regex=False)
    matches = attractions_db[mask]
    if matches.empty:
        st.warning(f"⚠️ 找不到「{place_name}」的資料。")
        return
    matches_with_pic = matches[matches['Picture'].str.contains('PictureUrl1', na=False)]
    row = matches_with_pic.iloc[0] if not matches_with_pic.empty else matches.iloc[0]

    col_img, col_desc = st.columns([1, 1.5])
    with col_img:
        img_url = None
        try:
            if pd.notna(row['Picture']):
                pic_dict = ast.literal_eval(row['Picture'])
                img_url = pic_dict.get('PictureUrl1')
        except: pass 
        if img_url:
            st.image(img_url, use_container_width=True, caption=row['ScenicSpotName'])
        else:
            st.warning("🖼️ 無法顯示圖片")
        # --- 🔴 修改結束 ---

    with col_desc:
        st.subheader(f"📍 {row['ScenicSpotName']}")
        st.caption(f"🏠 地址：{row['Address']}")
        st.caption(f"📞 電話：{row['Phone']}")
        st.caption(f"⏰ 開放時間：{row['OpenTime']}")
        desc_detail = row['DescriptionDetail']
        if pd.notna(desc_detail):
            with st.container(height=200): 
                st.write(desc_detail)
        else:
            st.write(row['Description'])
import urllib3
# 停用因為略過 SSL 驗證而產生的警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- AI 專屬：Google Maps 地點詳細資訊 (具備 CSV 降級防護) ---
GOOGLE_MAPS_API_KEY = "AIzaSyDu7U5Fvot2xJeHX9N6U3bWWUu6Minq3ig"
@st.cache_data(ttl=86400)
def check_google_business_status(place_name):
    """檢查景點是否正常營業，用於過濾周邊推薦"""
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": place_name,
        "inputtype": "textquery",
        "fields": "business_status",
        "key": GOOGLE_MAPS_API_KEY # 使用你設定好的變數
    }
    try:
        res = requests.get(url, params=params, verify=False, timeout=3).json()
        candidates = res.get("candidates", [])
        if candidates:
            # 如果抓到狀態，回傳是否為營業中 (OPERATIONAL)
            return candidates[0].get("business_status", "OPERATIONAL") == "OPERATIONAL"
    except:
        pass
    return True # 網路錯誤則預設放行

@st.cache_data(ttl=86400)
def search_and_display_google_place(place_name):
    """
    接收景點名稱，向 Google 查詢真實星級與營業時間。
    若發生 SSL 錯誤或找不到，自動退回原本的 CSV 查詢。
    """
    GOOGLE_MAPS_API_KEY = "AIzaSyDu7U5Fvot2xJeHX9N6U3bWWUu6Minq3ig"
    
    if not GOOGLE_MAPS_API_KEY:
        display_attraction_details(place_name)
        return

    try:
        search_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        search_params = {
            "input": place_name,
            "inputtype": "textquery",
            "fields": "place_id",
            "key": GOOGLE_MAPS_API_KEY
        }
        search_res = requests.get(search_url, params=search_params, verify=False, timeout=5).json()
        candidates = search_res.get("candidates", [])
        
        if not candidates:
            display_attraction_details(place_name)
            return
            
        place_id = candidates[0]["place_id"]
        
        details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        details_params = {
            "place_id": place_id,
            "fields": "name,formatted_address,formatted_phone_number,rating,user_ratings_total,opening_hours,photos,editorial_summary,business_status",            "language": "zh-TW",
            "key": GOOGLE_MAPS_API_KEY
        }
        details_res = requests.get(details_url, params=details_params, verify=False, timeout=5).json()
        details = details_res.get("result", {})
        
        if not details:
            display_attraction_details(place_name)
            return

        col_img, col_desc = st.columns([1, 1.5])
        with col_img:
            photos = details.get("photos", [])
            if photos:
                photo_ref = photos[0]["photo_reference"]
                img_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference={photo_ref}&key={GOOGLE_MAPS_API_KEY}"
                st.image(img_url, use_container_width=True, caption=details.get("name"))
            else:
                st.info("🖼️ 暫無 Google Maps 圖片")

        with col_desc:
            st.subheader(f"📍 {details.get('name', place_name)}")
            
            # --- 🚨 歇業防呆警告機制 ---
            business_status = details.get("business_status", "OPERATIONAL")
            if business_status == "CLOSED_TEMPORARILY":
                st.error("⚠️ 注意：根據 Google Maps，此景點目前【暫停營業】！請盡速於行程表中更換。")
            elif business_status == "CLOSED_PERMANENTLY":
                st.error("🚨 警告：根據 Google Maps，此景點已【永久歇業】！請盡速於行程表中更換。")
            
            rating = details.get('rating', '無')
            total_ratings = details.get('user_ratings_total', 0)
            if rating != '無':
                st.markdown(f"⭐ **{rating}** ({total_ratings} 則評論) - *資料來源: Google Maps*")
            
            st.caption(f"🏠 地址：{details.get('formatted_address', '無')}")
            st.caption(f"📞 電話：{details.get('formatted_phone_number', '無')}")
            
            opening_hours = details.get("opening_hours", {})
            if opening_hours:
                is_open = opening_hours.get("open_now")
                status_color = "#28a745" if is_open else "#dc3545"
                status_text = "目前營業中" if is_open else "目前休息中"
                st.markdown(f"⏰ **狀態：** <span style='color:{status_color}; font-weight:bold;'>{status_text}</span>", unsafe_allow_html=True)
                
                with st.expander("📅 查看 Google 一週營業時間"):
                    for day_text in opening_hours.get("weekday_text", []):
                        st.write(day_text)
                     
            # 🌟 1. 先嘗試抓取 AI 專門為這個景點寫的詳細導覽 (LongDesc)
            ai_long_desc = ""
            if 'schedule_df' in st.session_state and st.session_state['schedule_df'] is not None:
                df_sch = st.session_state['schedule_df']
                if 'Place' in df_sch.columns:
                    # 進行比對，去除前後空白確保精準度
                    match = df_sch[df_sch['Place'].astype(str).str.strip() == place_name.strip()]
                    if not match.empty:
                        ai_long_desc = match.iloc[0].get('LongDesc', '')
                        
            # 🌟 2. 若行程表無資料（如周邊推薦），或 AI 漏寫，則「現場即時生成」
            if not ai_long_desc or str(ai_long_desc).strip() == "":
                # 抓取資料庫簡介作為 AI 參考素材
                base_info = ""
                if 'attractions_db' in globals() and attractions_db is not None:
                    mask = attractions_db['ScenicSpotName'].str.strip() == place_name.strip()
                    matches = attractions_db[mask]
                    if not matches.empty:
                        base_info = matches.iloc[0].get('DescriptionDetail') or matches.iloc[0].get('Description', '')
                
                with st.spinner("✨ AI 正在為此推薦景點撰寫專屬導覽..."):
                    try:
                        # 要求的文案長度與風格與行程表一致
                        prompt = f"請為台灣景點「{place_name}」撰寫一段約 80~120 字的深度導覽文案，包含歷史背景、必看特色與推薦理由。請直接回傳文案，不需多餘對話。\n參考資料：{base_info}"
                        res = chat_model.generate_content(prompt)
                        ai_long_desc = res.text.strip()
                    except Exception as e:
                        ai_long_desc = "（暫時無法產生 AI 導覽，請稍後再試）"

            # 🌟 3. 最終顯示：只出現 ✨ AI 專屬導覽，不顯示官方簡介
            if ai_long_desc:
                st.markdown(f"✨ **AI 專屬導覽**：\n{ai_long_desc}")

    except Exception as e:
        display_attraction_details(place_name)

# --- [升級版] 景點替換引擎 (支援視窗內靜默更新) ---
# --- [升級版] 景點替換引擎 (支援視窗內靜默更新與簡介同步) ---
def execute_spot_replacement(old_spot, new_spot, day_val, idx, mode, do_rerun=True):
    """處理行程表內的景點替換，並重新計算交通、天氣與景點簡介"""
    with st.spinner(f"🔄 正在將 {old_spot} 替換為 {new_spot}..."):
        if mode == 'ai':
            # 複製一份副本進行修改，確保寫入成功
            df = st.session_state['schedule_df'].copy()
            start_d = st.session_state.get('ai_start_date', date.today())
            
            target_trans_list = st.session_state.get('final_trans', ["大眾運輸"])
            target_trans = "、".join(target_trans_list)
            
            # 1. 重新計算該站與前後站的交通時間
            target_order = df.at[idx, 'Order']
            if target_order == 1:
                origin = st.session_state.get('final_start_pt', '臺北車站') if day_val == 1 else \
                         df[df['Day'] == day_val - 1].sort_values('Order').iloc[-1]['Place']
            else:
                prev_mask = (df['Day'] == day_val) & (df['Order'] == target_order - 1)
                origin = df[prev_mask].iloc[0]['Place'] if prev_mask.any() else "前一站"
                
            # 更新到達新景點的交通文字
            try:
                p1 = f"請規劃從「{origin}」到「{new_spot}」的交通。限定使用【{target_trans}】。限15字內。"
                df.at[idx, 'Transport'] = chat_model.generate_content(p1).text.strip()
            except:
                df.at[idx, 'Transport'] = f"從 {origin} 前往 {new_spot}"
                
            # 2. 更新景點基礎資訊
            df.at[idx, 'Place'] = new_spot
            base_desc = ""
            if 'attractions_db' in globals() and attractions_db is not None:
                new_info = attractions_db[attractions_db['ScenicSpotName'] == new_spot]
                if not new_info.empty:
                    df.at[idx, 'City'] = new_info.iloc[0]['City']
                    df.at[idx, 'District'] = new_info.iloc[0]['District']
                    base_desc = new_info.iloc[0].get('DescriptionDetail') or new_info.iloc[0].get('Description', '')
            
            # 🟢 [核心修正] 替換景點時，同步呼叫 AI 更新短簡介，並清空長簡介
            try:
                p_desc = f"請為台灣景點「{new_spot}」寫一句約15個字的超短介紹（必須使用繁體中文），直接回傳結果，不要引號。參考資料：{str(base_desc)[:100]}"
                df.at[idx, 'ShortDesc'] = chat_model.generate_content(p_desc).text.strip()
                df.at[idx, 'LongDesc'] = "" # 清空舊的長簡介，讓使用者未來點開視窗時會自動重新生成
            except:
                df.at[idx, 'ShortDesc'] = f"探索{new_spot}的在地特色。"
                df.at[idx, 'LongDesc'] = ""
                
            # 3. 更新下一站交通
            next_mask = (df['Day'] == day_val) & (df['Order'] == target_order + 1)
            if not next_mask.any():
                next_mask = (df['Day'] == day_val + 1) & (df['Order'] == 1)
            if next_mask.any():
                next_idx = df[next_mask].index[0]
                next_spot = df.at[next_idx, 'Place']
                try:
                    p2 = f"請規劃從「{new_spot}」到「{next_spot}」的交通。限定使用【{target_trans}】。限15字內。"
                    df.at[next_idx, 'Transport'] = chat_model.generate_content(p2).text.strip()
                except:
                    df.at[next_idx, 'Transport'] = f"從 {new_spot} 出發"

            # 更新寫回 Session State
            st.session_state['schedule_df'] = df
            # 同步更新該日的天氣預報資料
            st.session_state['ai_weather_df'] = process_schedule_weather(df, start_d)
            
        elif mode == 'manual':
            day_list = st.session_state['trip_schedule'].get(day_val, [])
            if 0 <= idx < len(day_list):
                day_list[idx] = new_spot
                st.session_state['trip_schedule'][day_val] = day_list
                st.session_state['manual_weather_cache']['signature'] = ""
    
    st.toast(f"✅ 已成功更換為 {new_spot}！")
    # 如果 do_rerun 為 False，則不重整網頁，視窗就不會關閉
    if do_rerun:
        time.sleep(0.5)
        st.rerun()
# --- [終極版] 景點詳情視窗 (支援原地跳轉、同區優先排序、不關閉分頁) ---
@st.dialog("🔍 景點詳細資訊", width="large")
def show_spot_details_dialog(place_name, day_val=None, idx=None, mode=None):
    # 🟢 [關鍵修正] 定義唯一的狀態 Key
    dialog_state_key = f"dialog_viewing_{day_val}_{idx}"
    page_key = f"page_{dialog_state_key}"
    
    # 🟢 [核心邏輯] 如果是第一次點開這一站，或者換了不同站點，強制重置為第一頁
    if st.session_state.get('last_opened_idx') != idx:
        st.session_state[dialog_state_key] = place_name
        st.session_state[page_key] = 0  # 👈 強制歸零
        st.session_state['last_opened_idx'] = idx 
        
    # 如果已經在視窗內，但點擊了「替換」，也要確保 page_key 存在
    if page_key not in st.session_state:
        st.session_state[page_key] = 0

    current_place = st.session_state.get(dialog_state_key, place_name)
    
    # --- 1. 顯示目前選中景點的 Google 詳細資料 ---
    search_and_display_google_place(current_place)
    
    if day_val is not None and idx is not None and mode is not None:
        if 'attractions_db' in globals() and attractions_db is not None:
            curr_row = attractions_db[attractions_db['ScenicSpotName'] == current_place]
            if not curr_row.empty:
                city = curr_row.iloc[0].get('City', '')
                curr_dist = curr_row.iloc[0].get('District', '')
                
                # 🟢 [核心修改] 取得使用者在 AI 模式中「勾選」的類別清單
                # 如果是 AI 模式，從 final_themes 抓取；若無則回歸同類別
                selected_themes = st.session_state.get('final_themes', [])
                
                # 抓取座標算距離
                curr_lat, curr_lon = None, None
                try:
                    pos = ast.literal_eval(curr_row.iloc[0]['Position'])
                    curr_lat, curr_lon = pos.get('PositionLat'), pos.get('PositionLon')
                except: pass
                
                # --- 2. 智慧篩選與排序邏輯 ---
                # A. 基礎篩選：同縣市且非目前景點
                mask_city = (attractions_db['City'] == city) & (attractions_db['ScenicSpotName'] != current_place)
                candidates = attractions_db[mask_city].copy()
                
                if not candidates.empty:
                    # 🟢 [核心修改] 類別過濾：只顯示有勾選的類別
                    if selected_themes:
                        candidates = candidates[candidates['NewCategory'].isin(selected_themes)].copy()
                    
                    if not candidates.empty:
                        # 1. 標記是否為同行政區 (最高權重)
                        candidates['IsSameDist'] = (candidates['District'] == curr_dist).astype(int)
                        
                        # 2. 計算真實物理距離
                        def calc_real_dist(r):
                            try:
                                p = ast.literal_eval(r['Position'])
                                return calculate_distance(curr_lat, curr_lon, p['PositionLat'], p['PositionLon'])
                            except: return 999.0
                        candidates['DistVal'] = candidates.apply(calc_real_dist, axis=1)
                        
                        # 🟢 [排序規則] 先排同區(降冪)，再排距離(升冪)
                        candidates = candidates.sort_values(by=['IsSameDist', 'DistVal'], ascending=[False, True])

                        st.divider()
                        st.markdown(f"### 💡 覺得「{current_place}」不合適？試試類似景點：")
                        
                        # --- 3. 實作分頁邏輯 ---
                        page_key = f"page_{dialog_state_key}"
                        if page_key not in st.session_state: st.session_state[page_key] = 0
                        
                        items_per_page = 3
                        total_items = len(candidates)
                        total_pages = math.ceil(total_items / items_per_page)
                        curr_page = st.session_state[page_key]
                        
                        display_items = candidates.iloc[curr_page*3 : (curr_page+1)*3]
                        cols = st.columns(3)
                        for i, (_, s_row) in enumerate(display_items.iterrows()):
                            s_name = s_row['ScenicSpotName']
                            s_cat = str(s_row.get('NewCategory', '熱門推薦'))
                            
                            img_url = ""
                            try:
                                pic = ast.literal_eval(s_row['Picture'])
                                img_url = pic.get('PictureUrl1', "")
                            except: pass
                            
                            with cols[i]:
                                with st.container(border=True):
                                    st.markdown(f"""
                                        <div style="width:100%; height:110px; overflow:hidden; border-radius: 6px; margin-bottom: 8px; background-color: #1E1E1E; display: flex; justify-content: center; align-items: center;">
                                            <img src="{img_url if img_url else 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&q=80'}" style="max-width:100%; max-height:100%; object-fit:contain;">
                                        </div>
                                        <div style="font-weight: bold; font-size: 0.9em; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{s_name}">{s_name}</div>
                                        <div style="color: #aaa; font-size: 0.8em; margin-bottom: 8px;">📍 {s_row['District']} | 🏷️ {s_cat} | <span style="color:#6EE7B7;">{s_row['DistVal']:.1f}km</span></div>
                                    """, unsafe_allow_html=True)
                                    
                                    if st.button("🔄 替換", key=f"swap_btn_{s_name}_{idx}_{day_val}", use_container_width=True):
                                    # 1. 執行後台資料替換 (不全頁重整)
                                        execute_spot_replacement(current_place, s_name, day_val, idx, mode, do_rerun=False)
                                        
                                        # 2. 更新視窗目前查看的景點名稱，實現原地跳轉
                                        st.session_state[dialog_state_key] = s_name
                                        
                                        # 🟢 [核心修正] 強制重置該景點推薦區塊的頁碼為 0 (第一頁)
                                        st.session_state[page_key] = 0
                                        
                                        # 3. 僅讓視窗內部內容重新渲染
                                        st.rerun()
                        # --- 4. 分頁控制 (優化版：確保翻頁不重置視窗狀態) ---
                        st.write("")
                        c_info, c_prev, c_next = st.columns([5, 2.5, 2.5])
                        with c_info: 
                            st.caption(f"🎯 找到 {total_items} 個符合主題的景點 | 第 {curr_page+1}/{total_pages} 頁")
                        
                        with c_prev:
                            # 按下上一頁時，只改動 page_key，並使用 rerun 刷新視窗內容
                            if st.button("⬅️ 上一頁", key=f"prev_{dialog_state_key}", disabled=(curr_page == 0), use_container_width=True):
                                st.session_state[page_key] -= 1
                                
                        with c_next:
                            # 按下下一頁時，只改動 page_key
                            if st.button("下一頁 ➡️", key=f"next_{dialog_state_key}", disabled=(curr_page >= total_pages - 1), use_container_width=True):
                                st.session_state[page_key] += 1

                    else:
                        st.info("💡 目前在此地區找不到符合您所選主題的其他景點。")

# --- 8. Auth Pages (Login/Signup/Forgot) ---
def signup_page():
    st.title("📝 註冊新帳號")
    with st.form("signup_form"):
        new_email = st.text_input("請輸入電子郵件")
        new_nickname = st.text_input("請輸入暱稱")
        new_password = st.text_input("請輸入密碼", type="password")
        confirm_password = st.text_input("請再次確認密碼", type="password")
        submitted = st.form_submit_button("註冊")
        if submitted:
            users = load_users()
            if not new_email or not new_password or not new_nickname:
                 st.error("所有欄位都必須填寫")
            elif "@" not in new_email:
                 st.error("請輸入有效的電子郵件")
            elif new_email in users:
                st.error("此電子郵件已被註冊")
            elif new_password != confirm_password:
                st.error("兩次輸入的密碼不相同")
            else:
                save_user(new_email, new_password, new_nickname)
                st.success("註冊成功！")
                time.sleep(1)
                st.session_state['current_page'] = 'login'
                st.rerun()
    st.write("---")
    if st.button("返回登入頁面"):
        st.session_state['current_page'] = 'login'
        st.rerun()

def forgot_password_page():
    st.title("🔑 忘記密碼")
    with st.form("forgot_password_form"):
        email = st.text_input("電子郵件")
        submitted = st.form_submit_button("發送驗證碼")
        if submitted:
            users = load_users()
            if email in users:
                code = generate_verification_code()
                st.session_state['reset_email'] = email
                st.session_state['reset_code'] = code
                st.info(f"您的驗證碼是：**{code}** (頁面將在 5 秒後自動跳轉)")
                time.sleep(5)
                st.session_state['current_page'] = 'reset_password'
                st.rerun()
            else:
                st.error("找不到此電子郵件")
    st.write("---")
    if st.button("返回登入頁面"):
        st.session_state['current_page'] = 'login'
        st.rerun()

def reset_password_page():
    st.title("🔄 重設密碼")
    with st.form("reset_password_form"):
        code_input = st.text_input("請輸入驗證碼")
        new_password = st.text_input("請輸入新密碼", type="password")
        confirm_password = st.text_input("請再次確認新密碼", type="password")
        submitted = st.form_submit_button("重設密碼")

        if submitted:
            if code_input != st.session_state['reset_code']:
                st.error("驗證碼錯誤")
            elif new_password != confirm_password:
                st.error("兩次密碼不相同")
            else:
                save_user(st.session_state['reset_email'], new_password)
                st.success("密碼重設成功！")
                time.sleep(1)
                st.session_state['current_page'] = 'login'
                st.rerun()
    st.write("---")
    if st.button("返回登入頁面"):
        st.session_state['current_page'] = 'login'
        st.rerun()

def login_page():
    st.markdown("<h1 style='text-align: center;'>🔐 使用者登入</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            email = st.text_input("電子郵件")
            password = st.text_input("密碼", type="password")
            submitted = st.form_submit_button("登入")
            if submitted:
                nickname = authenticate(email, password)
                
                # [新增] 針對格式錯誤的判斷
                if nickname == "DB_FORMAT_ERROR":
                    st.error("⚠️ 格式錯誤")
                
                elif nickname:
                    st.session_state['logged_in'] = True
                    st.session_state['user_nickname'] = nickname
                    st.session_state['user_email'] = email
                    st.session_state['mode'] = 'menu'
                    st.success(f"歡迎，{nickname}！")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("❌ 登入失敗 (帳號或密碼錯誤)")
        col_forgot, col_signup = st.columns([1.5, 1])
        with col_forgot:
            if st.button("🤔 忘記密碼？"):
                st.session_state['current_page'] = 'forgot_password'
                st.rerun()
        if st.button("👉 前往註冊", use_container_width=True):
            st.session_state['current_page'] = 'signup'
            st.rerun()

# --- 9. 側邊欄 (包含 AI 快速修改參數中心) ---
def sidebar_component():
    with st.sidebar:
        st.header(f"👤 {st.session_state.get('user_nickname', '使用者')}")
        
        # 1. 基礎導航按鈕
        if st.session_state.get('mode') != 'menu':
            if st.button("🏠 回到主選單", use_container_width=True):
                st.session_state['mode'] = 'menu'
                st.session_state['ai_submitted'] = False # 重置 AI 狀態
                st.rerun()
        
        if st.session_state.get('mode') != 'history':
             if st.button("📜 我的歷史紀錄", use_container_width=True):
                st.session_state['mode'] = 'history'
                st.rerun()
                
        # 🟢 [核心功能] 僅在「AI 模式」且「行程已生成」時顯示修改區塊
        # 確保「手動頁面」維持乾淨，不會出現這些欄位
        if st.session_state.get('mode') == 'ai_chat' and st.session_state.get('ai_submitted'):
            st.markdown("---")
            st.subheader("⚙️ 快速修改參數")
            
            # 讀取當前的鎖定參數 (Final 系列變數) 作為預設值
            curr_start_date = st.session_state.get('ai_start_date', date.today())
            curr_days = st.session_state.get('final_days', 1)
            curr_spots = st.session_state.get('final_spots', 3)
            curr_note = st.session_state.get('final_user_note', '')
            curr_trans = st.session_state.get('final_trans', ["大眾運輸"])
            curr_themes = st.session_state.get('final_themes', [])
            curr_dest = st.session_state.get('final_dest', '臺北市')
            
            opts = st.session_state.get('category_options', ["歷史人文類", "都會休閒類", "自然生態類", "美食商圈類", "藝文展館類"])
            
            # 2. 建立輸入元件 (滿足您所有的修改需求)
            new_date = st.date_input("📅 出發日期", value=curr_start_date, min_value=date.today(), key="side_date")
            new_days = st.number_input("⏱️ 旅遊天數", min_value=1, max_value=10, value=int(curr_days), key="side_days")
            new_spots = st.number_input("📍 每日景點數量", min_value=1, max_value=8, value=int(curr_spots), key="side_spots")
            new_note = st.text_input("📝 必去景點", value=curr_note, placeholder="例如：台北101", key="side_note")
            new_trans = st.multiselect("🚗 交通方式", ["大眾運輸", "自行開車", "計程車", "步行", "租車", "機車"], default=curr_trans, key="side_trans")
            new_themes = st.multiselect("🎨 偏好主題", options=opts, default=curr_themes, key="side_themes")
            new_dest = st.text_input("🏙️ 目的地城市", value=curr_dest, key="side_dest")
            
            st.write("")
            if st.button("🔄 儲存並重新生成", use_container_width=True, type="primary"):
                # 寫回鎖定參數
                st.session_state['ai_start_date'] = new_date
                st.session_state['ai_end_date'] = new_date + timedelta(days=new_days-1)
                st.session_state['final_days'] = new_days
                st.session_state['final_spots'] = new_spots
                st.session_state['final_user_note'] = new_note
                st.session_state['final_trans'] = new_trans
                st.session_state['final_themes'] = new_themes
                st.session_state['final_dest'] = new_dest
                
                # 清除舊行程，觸發 AI 重新規劃
                st.session_state['schedule_df'] = None 
                st.session_state['ai_weather_df'] = None
                st.session_state['last_recommend_pool'] = None 
                st.session_state['rec_page'] = 0 
                st.session_state['temp_view_spot'] = None
                st.rerun()

        # 3. 登出按鈕
        st.divider()
        if st.button("登出", use_container_width=True):
            st.session_state.clear()
            st.rerun()
# --- 10. 主要頁面功能區 ---

def menu_page():
    sidebar_component()
    st.title("🌟 歡迎來到台灣旅遊小幫手")
    col1, col2 = st.columns(2)
    with col1:
        st.info("🤖 **AI 對話排程**\n\n像聊天一樣告訴 AI 你的需求，自動生成完美行程。")
        if st.button("✨ 開始 AI 對話", use_container_width=True, type="primary"):
            st.session_state['mode'] = 'ai_chat'
            st.rerun()
    with col2:
        st.success("🗺️ **手動自由配**\n\n自訂旅遊天數，搜尋資料庫圖片，自由加入行程。")
        if st.button("🔍 自己搜尋瀏覽", use_container_width=True):
            st.session_state['mode'] = 'manual'
            st.rerun()

def render_ai_input_form(container):
    with container:
        if not st.session_state['ai_submitted']:
             st.markdown("### 🛫 規劃您的旅程")
        else:
             st.header("⚙️ 修改設定")
        
        # 地點輸入
        st.text_input("想去哪裡玩？", value=st.session_state['input_dest'], key="widget_dest", on_change=lambda: st.session_state.update({'input_dest': st.session_state.widget_dest}))
        
        # 日期選擇
        default_start = st.session_state.get('ai_start_date', date.today())
        default_end = st.session_state.get('ai_end_date', date.today() + timedelta(days=2))
        
        dates = st.date_input(
            "選擇旅遊日期區間", 
            value=[default_start, default_end],
            min_value=date.today(),
            help="請選擇開始與結束日期"
        )
        
        # 邏輯：根據日期算出天數
        if len(dates) == 2:
            start_d, end_d = dates
            delta_days = (end_d - start_d).days + 1
            st.session_state['input_days'] = delta_days
            st.session_state['ai_start_date'] = start_d
            st.session_state['ai_end_date'] = end_d
            st.caption(f"共計：{delta_days} 天")
        elif len(dates) == 1:
            st.caption("請選擇結束日期...")
            st.session_state['input_days'] = 1 
        
        # 交通 (這裡也加上安全選項)
        st.multiselect(
            "交通方式", 
            ["大眾運輸", "自行開車", "計程車", "步行", "租車", "機車"], 
            default=["大眾運輸"], 
            key="input_trans"
        )
                
        # 偏好
        st.text_area("偏好與必去景點", value=st.session_state['input_mixed'], key="widget_mixed", height=100, on_change=lambda: st.session_state.update({'input_mixed': st.session_state.widget_mixed}))
        
        st.write("")
        # 避免只選一天或未完成選擇時按按鈕
        btn_disabled = (len(dates) != 2)
        
        # 按鈕邏輯
        if st.button("✨ 開始規劃" if not st.session_state['ai_submitted'] else "🔄 重新生成", use_container_width=True, disabled=btn_disabled):
            st.session_state['ai_submitted'] = True
            st.session_state['schedule_df'] = None 
            st.session_state['ai_weather_df'] = None
            
            # 🔴 清除舊的推薦快取與重置頁碼
            st.session_state['last_recommend_pool'] = None 
            st.session_state['rec_page'] = 0 
            st.session_state['temp_view_spot'] = None # 🟢 [新增] 清除圖文詳情的舊記憶
            st.rerun()


# --- AI 對話與排程頁面 (核心修改區) ---
def ai_planning_page():
    # 1. 初始化 State
    defaults = {
        'input_dest': '臺北市',
        'input_start_point': '臺北車站', # [新增] 出發點預設值
        'spots_per_day': 3,
        'input_days': 1,
        'ai_start_date': date.today(),
        'ai_end_date': date.today(),
        'input_trans': ["大眾運輸"],
        'input_mixed': "",
        'ai_submitted': False,
        'schedule_df': None,
        'ai_weather_df': None
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    sidebar_component()
    
    # --- 確保分類選項一定存在 ---
    if 'category_options' not in st.session_state:
        default_cats = ["歷史人文類", "都會休閒類", "自然生態類", "美食商圈類", "藝文展館類"]
        try:
            if 'attractions_db' in globals() and attractions_db is not None:
                cats = attractions_db['NewCategory'].dropna().unique().tolist()
                st.session_state['category_options'] = cats
        except:
            st.session_state['category_options'] = default_cats

    # --- 狀態 1: 參數設定階段 ---
    import datetime  # 確保檔案最上方有 import datetime

# ... (省略前面) ...

    # --- 狀態 1: 參數設定階段 ---
    if not st.session_state['ai_submitted']:
        st.header("🤖 AI 智慧行程規劃")
        st.caption("請選擇您的旅遊偏好，AI 將為您規劃順暢的旅遊路徑。")

        col1, col2 = st.columns(2)
        with col1:
            st.date_input("📅 出發日期", min_value=date.today(), key="ai_start_date")
            current_days = st.number_input("⏱️ 旅遊天數", min_value=1, max_value=10, key="input_days")
            st.number_input("📍 每日景點數量", min_value=1, max_value=8, key="spots_per_day")
            st.text_input("🏠 出發起點 (例如：飯店名稱或車站)", key="input_start_point")
            st.text_input("📝 必去景點", value="", key="user_note_input", placeholder="例如：台北101")

        with col2:
            # --- 建立出發時間選單 (06:00 ~ 14:30，每半小時一個選項) ---
            time_options = [f"{h:02d}:{m:02d}" for h in range(0, 24) for m in (0, 30)]
            time_options.append("24:00")
            # 👇 [修改] 出發時間改為下拉式選單
            st.selectbox("⏰ 出發時間", options=time_options, index=time_options.index("09:00"), key="input_start_time")
            st.multiselect("🚗 交通方式", ["大眾運輸", "自行開車", "計程車", "步行", "租車", "機車"], default=["大眾運輸"], key="input_trans")
            opts = st.session_state.get('category_options')
            st.multiselect("🎨 偏好主題 (可複選)", options=opts, placeholder="請選擇感興趣的類型...",default=["🛍️ 商圈市集類"], key="input_themes")
            st.text_input("📍 目的地城市", value="臺北市", key="input_dest") 
            
            for d in range(1, int(current_days) + 1):
                label_text = f"🎯 Day {d} 行程終點 (可選填，如飯店或車站)" if d == 1 else f"🎯 Day {d} 行程終點 (可選填)"
                st.text_input(label_text, key=f"end_point_day_{d}", placeholder="若不指定可留空")
        
        if st.button("🚀 AI生成行程", type="primary", use_container_width=True):
            # 確保獲取當前輸入的天數
            days = st.session_state.get('input_days', 1)
            # 強制重新計算結束日期
            st.session_state['ai_end_date'] = st.session_state['ai_start_date'] + timedelta(days=days-1)
            
            # 🔴 鎖定所有參數
            st.session_state['final_days'] = days
            st.session_state['final_spots'] = st.session_state.get('spots_per_day', 3)
            st.session_state['final_start_pt'] = st.session_state.get('input_start_point', '臺北車站')
            st.session_state['final_dest'] = st.session_state.get('input_dest', '臺北市')
            st.session_state['final_user_note'] = st.session_state.get('user_note_input', '')
            st.session_state['final_themes'] = st.session_state.get('input_themes', []) 
            st.session_state['final_trans'] = st.session_state.get('input_trans', ["大眾運輸"]) 
            
            # 👇 [新增] 鎖定出發時間
            st.session_state['final_start_time'] = st.session_state.get('input_start_time')
            
            st.session_state['final_end_points'] = {
                d: st.session_state.get(f"end_point_day_{d}", "")
                for d in range(1, days + 1)
            }
            
            st.session_state['ai_submitted'] = True
            st.session_state['schedule_df'] = None 
            st.session_state['ai_weather_df'] = None
            
            # 🔴 清除舊的推薦快取與重置頁碼
            st.session_state['last_recommend_pool'] = None 
            st.session_state['rec_page'] = 0 
            st.session_state['temp_view_spot'] = None # 🟢 [新增] 清除圖文詳情的舊記憶
            st.rerun()
    # --- 狀態 2: 行程生成與展示階段 ---
    else:
        # 直接從 session_state 抓取最新值
        start_d = st.session_state.get('ai_start_date', date.today())
        end_d = st.session_state.get('ai_end_date', date.today())
        # 確保標題顯示的天數是根據最新日期計算的
        display_days = (end_d - start_d).days + 1
        
        # 🔴 [修改點 2] 讀取鎖定的參數來顯示標題
        dest_display = st.session_state.get('final_dest', '臺北市')
        start_pt_display = st.session_state.get('final_start_pt', '未設定')
        
        st.title(f"🗺️ {dest_display} - AI 專屬行程")
        st.caption(f"🏠 起點：{start_pt_display} ｜ 📅 {start_d} 出發 ｜ ⏱️ {display_days} 天")
        
        if st.session_state['schedule_df'] is None:
            with st.spinner('🚀 正在依據您的起點規劃最佳路徑...'):
                try:
                    # 🔴 讀取鎖定的參數
                    dest = st.session_state.get('final_dest', '臺北市')
                    user_note = st.session_state.get('final_user_note', '').replace("台", "臺")
                    start_pt = st.session_state.get('final_start_pt', '臺北車站')
                    target_days = st.session_state.get('final_days', 1)
                    target_spots = st.session_state.get('final_spots', 3)
                    target_trans = "、".join(st.session_state.get('final_trans', ["大眾運輸"]))
                    end_points = st.session_state.get('final_end_points', {}) # 取得每日終點
                    
                    # 將側欄鎖定的「偏好主題」傳入資料庫進行嚴格篩選
                    themes_for_search = st.session_state.get('final_themes', [])
                    priority_list, context_str, status = get_attraction_data(dest, user_note, themes=themes_for_search)
                    
                    # 🚨 嚴格防呆：如果該地區完全沒有符合該主題的景點，立刻中斷並提醒使用者
                    if status and status.get("error") == "strict_theme_empty":
                        st.error(f"⚠️ 找不到位於「{dest}」且符合您所選「主題」的景點。請嘗試在側欄放寬或增加偏好主題！")
                        st.stop()
                    
                    # --- 🌟 動態組合每日起終點連鎖規則 ---
                    route_rules_lines = []
                    current_start = start_pt 
                    
                    route_rules_lines = []
                    current_start = start_pt 
                    
                    for d in range(1, target_days + 1):
                        day_end = end_points.get(d, "").strip()
                        rule = f"- Day {d}: 出發起點為「{current_start}」。"
                        if day_end:
                            # 👇 強調不在資料庫也要寫入，且必須獨立成一筆
                            rule += f" 🛑 【終點絕對強制】：當天行程結束後，必須前往「{day_end}」。請在該天 JSON 最後獨立新增一筆「{day_end}」的資料（即使它不在參考資料庫中也絕對必須建立）！"
                            current_start = day_end 
                        else:
                            rule += " 行程終點無強制指定，請順路安排。"
                            current_start = "前一日的最後一個景點" 
                        route_rules_lines.append(rule)
                    route_rules_str = "\n".join(route_rules_lines)
                    
                    # --- 🌟 [新增] 計算實際日期與星期幾，用於營業時間防呆 ---
                    weekdays_tw = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
                    date_rules_lines = []
                    for d in range(1, target_days + 1):
                        curr_date = start_d + timedelta(days=d-1)
                        wd = weekdays_tw[curr_date.weekday()]
                        date_rules_lines.append(f"- Day {d} 實際日期為：{curr_date.strftime('%Y-%m-%d')} ({wd})")
                    date_rules_str = "\n".join(date_rules_lines)
                    
                    # 產生絕對強制指令
                    must_visit_rule = ""
                    if priority_list:
                        must_visit_rule = f"""
                    =========================================
                    🚨 絕對強制要求 (FATAL ERROR IF IGNORED) 🚨
                    你的 JSON 行程表中，【絕對必須】包含以下景點：
                    {', '.join(priority_list)}
                    (為了確保上述景點入列，允許打破地理限制)
                    =========================================
                    """
                    
                    # --- 🌟 修改 Prompt，加入嚴格時間單位規範 ---
                    start_time_val = st.session_state.get('final_start_time', '09:00')
                    prompt = f"""
                    請規劃 {dest} 的 {target_days} 天行程。
                    **出發時間**：每天請從 【{start_time_val}】 開始安排第一個行程。

                    {must_visit_rule}

                    **排程規範 (時間刻度要求)**：
                    1. 每個景點的時間欄位必須遵守以下規定：
                    - **StayDuration (建議停留時長)**：必須以「小時」為單位，且數值必須是 **0.5 的倍數** (例如: "1.0 小時"、"1.5 小時"、"2.0 小時")。**嚴禁出現 0.25、0.75 或任何非 0.5 倍數的數值**。
                    - `ScheduleTime`: 該景點的預計起迄時間 (例如: "09:00 - 10:30")。請考慮交通時間進行推算。
                    2. 雙重介紹文案：`ShortDesc` (請嚴格控制在 10~20 個字以內，精簡扼要) 與 `LongDesc` (100字內)。
                    3. 交通方式限定：依照【{target_trans}】安排。
                    4. 景點數量嚴格限制：每天【必須剛好】安排 {target_spots} 個景點，絕對不可以多排或少排！若一天下來時間有剩餘空檔，請自動拉長每個景點的「StayDuration (建議停留時長)」來填補時間，千萬不要擅自增加景點數量來湊數。
                    5. 起點參照：起點僅為距離參考，【嚴禁】將「起點」寫入行程的 Place 中。
                    6. 雙重介紹文案：`ShortDesc` (20字內) 與 `LongDesc` (100字內)。
                    7. 🌙 夜市專屬規則：若景點名稱包含「夜市」，請【務必】將其安排在該日行程的「最後一站」，並配予合理的「晚間時段」(如 17:00 之後)。
                    8. ⏱️ 時間連續性要求 (極重要)：景點與景點之間的空檔（包含交通與移動時間）**絕對不可以超過1小時**！請確保行程緊密相連。
                    
                    參考資料庫：
                    {context_str}
                    
                    回傳 JSON List 格式：
                    [ {{"Day": 1, "Order": 1, "Place": "景點名稱", "StayDuration": "1.5 小時", "ScheduleTime": "09:00 - 10:30", "Transport": "交通說明", "ShortDesc": "短文案", "LongDesc": "長文案", "City": "縣市", "District": "區域"}} ]
                    """
                    
                    # 呼叫模型
                    response = model.generate_content(prompt)
                    df_temp = pd.DataFrame(json.loads(response.text))
                    
                    # 1. 先把 AI 生成的原始資料存起來
                    st.session_state['schedule_df'] = df_temp
                    
                    # --- 🟢 [終極防呆] Python 強制終點寫入機制 ---
                    df_sch = st.session_state['schedule_df']
                    if df_sch is not None and not df_sch.empty:
                        locked_end_points = st.session_state.get('final_end_points', {})
                        target_trans_list = st.session_state.get('final_trans', ["大眾運輸"])
                        target_trans_str = "、".join(target_trans_list)
                        adjusted_dfs = []
                        
                        for d in sorted(df_sch['Day'].unique()):
                            day_df = df_sch[df_sch['Day'] == d].copy()
                            day_end = locked_end_points.get(d, "").strip()
                            
                            if day_end:
                                mask = day_df['Place'].astype(str).str.strip() == day_end
                                if mask.any():
                                    if str(day_df.iloc[-1]['Place']).strip() != day_end:
                                        end_row = day_df[mask].copy()
                                        day_df = day_df[~mask]
                                        day_df = pd.concat([day_df, end_row], ignore_index=True)
                                else:
                                    # --- 1. 抓取前一站資訊與結束時間 ---
                                    prev_place = "前一站"
                                    prev_end_time = "18:00" # 預設值
                                    if not day_df.empty:
                                        prev_row = day_df.iloc[-1]
                                        prev_place = str(prev_row['Place']).strip()
                                        time_str = str(prev_row.get('ScheduleTime', ''))
                                        # 解析出前一站的結束時間 (例如從 "16:00 - 19:00" 抓出 "19:00")
                                        if "-" in time_str:
                                            prev_end_time = time_str.split("-")[-1].strip()
                                    
                                    # --- 2. 呼叫 AI 快速產生交通方式 ---
                                    try:
                                        p_trans = f"請規劃從「{prev_place}」到「{day_end}」的交通。限定使用【{target_trans_str}】。限15字內，直接回傳結果不准有額外對話。格式範例：從{prev_place}搭公車約30分。"
                                        trans_desc = chat_model.generate_content(p_trans).text.strip()
                                    except:
                                        trans_desc = f"從 {prev_place} 前往 {day_end}"
                                        
                                    # --- 3. 計算抵達時間 (預設加上 30 分鐘車程) ---
                                    try:
                                        t_obj = datetime.strptime(prev_end_time, "%H:%M")
                                        t_arrival = t_obj + timedelta(minutes=30)
                                        final_schedule_time = f"[{t_obj.strftime('%H:%M')} - {t_arrival.strftime('%H:%M')}]"
                                    except:
                                        final_schedule_time = f"[{prev_end_time} - 抵達]"

                                    # --- 4. 建立最終資料 ---
                                    last_order = day_df['Order'].max() if not day_df.empty else 0
                                    new_row = pd.DataFrame([{
                                        "Day": d,
                                        "Order": last_order + 1,
                                        "Place": day_end,
                                        "StayDuration": "-",
                                        # 存入計算好的時間與交通
                                        "ScheduleTime": final_schedule_time.strip("[]"), 
                                        "Transport": trans_desc,
                                        "ShortDesc": "結束今日行程，好好休息！",
                                        "LongDesc": "安全抵達住宿地點或車站，為精彩的一天畫下句點。",
                                        "City": "",
                                        "District": ""
                                    }])
                                    day_df = pd.concat([day_df, new_row], ignore_index=True)
                            
                            # 重新編排這天的順序
                            day_df['Order'] = range(1, len(day_df) + 1)
                            adjusted_dfs.append(day_df)
                            
                        # 將處理好的資料存回系統
                        st.session_state['schedule_df'] = pd.concat(adjusted_dfs, ignore_index=True)
                    # -----------------------------------------------
                    
                    # 👇 [必須補回這行！] 在行程表完全排好、終點也加上去之後，呼叫天氣 API！
                    st.session_state['ai_weather_df'] = process_schedule_weather(st.session_state['schedule_df'], start_d)
                    
                except Exception as e:
                    st.error(f"規劃失敗：{e}"); st.stop()

        # 顯示結果
        if st.session_state['schedule_df'] is not None:
            if st.button("🔄 重新設定", use_container_width=True):
                st.session_state['ai_submitted'] = False; st.rerun()

            tab1, tab2, tab3, tab4 = st.tabs(["✏️ 行程編輯", "📸 圖文詳情", "📊 流程圖","⛅ 天氣預報"])
            
        with tab1:
            # 1. 顯示主行程表 (使用 AI 的 DataFrame 與變數)
            df_itinerary = st.session_state.get('schedule_df')
            ai_weather_df = st.session_state.get('ai_weather_df')
            start_d = st.session_state.get('ai_start_date', date.today())
            
            render_itinerary_with_weather_icons(
                df_itinerary,
                weather_df=ai_weather_df,
                start_date=start_d,
                mode='ai'
            )

            # 2. 獨立的導航按鈕區塊
            if df_itinerary is not None and not df_itinerary.empty:
                st.write("")
                unique_days = sorted(df_itinerary['Day'].unique())
                nav_cols = st.columns(len(unique_days) if len(unique_days) > 0 else 1)
                
                for i, d in enumerate(unique_days):
                    with nav_cols[i]:
                        day_spots = df_itinerary[df_itinerary['Day'] == d]['Place'].tolist()
                        if day_spots:
                            import urllib.parse
                            encoded_spots = [urllib.parse.quote(str(spot)) for spot in day_spots]
                            map_url = f"https://www.google.com/maps/dir/{'/'.join(encoded_spots)}"
                            
                            curr_date = start_d + timedelta(days=int(d)-1)
                            st.link_button(
                                label=f"🗺️ 開啟 Day {int(d)} 導航",
                                url=map_url,
                                use_container_width=True
                            )
                
                
                # 3. 編輯區塊維持不變
                with st.expander("🛠️ 編輯排序、交通與刪除"):
                    edit_df = st.session_state['schedule_df']
                    edit_days = sorted(edit_df['Day'].unique())
                    
                    for ed_day in edit_days:
                        st.markdown(f"**Day {int(ed_day)}**")
                        day_mask = edit_df['Day'] == ed_day
                        day_df = edit_df[day_mask].sort_values('Order')
                        
                        for i, (idx, row) in enumerate(day_df.iterrows()):
                            # 版面分配：名稱 | 交通文字框 | 上 | 下 | 刪除
                            c1, c2, c3, c4, c5 = st.columns([4, 3, 1, 1, 1], vertical_alignment="center")
                            
                            with c1: 
                                st.write(f"{i+1}. {row['Place']}")
                            
                            with c2:
                                # AI 模式的交通是完整句子，用 text_input 讓使用者可以自由修改文字
                                curr_trans = str(row['Transport']) if pd.notna(row['Transport']) else ""
                                
                                # 🟢 [修正重點] 加上景點名稱，讓 Key 絕對唯一，徹底消除 Streamlit 幽靈記憶 Bug！
                                safe_name = str(row['Place']).replace(" ", "_")
                                new_trans = st.text_input("交通", value=curr_trans, key=f"ai_edit_trans_{idx}_{safe_name}", label_visibility="collapsed")
                                
                                if new_trans != curr_trans:
                                    st.session_state['schedule_df'].at[idx, 'Transport'] = new_trans
                                    st.rerun()

                            with c3:
                                if i > 0 and st.button("⬆️", key=f"ai_up_{idx}"):
                                    # 與上一個景點交換 Order
                                    prev_idx = day_df.index[i-1]
                                    edit_df.at[idx, 'Order'], edit_df.at[prev_idx, 'Order'] = edit_df.at[prev_idx, 'Order'], edit_df.at[idx, 'Order']
                                    st.session_state['schedule_df'] = edit_df.sort_values(by=['Day', 'Order'])
                                    st.rerun()
                            with c4:
                                if i < len(day_df) - 1 and st.button("⬇️", key=f"ai_down_{idx}"):
                                    # 與下一個景點交換 Order
                                    next_idx = day_df.index[i+1]
                                    edit_df.at[idx, 'Order'], edit_df.at[next_idx, 'Order'] = edit_df.at[next_idx, 'Order'], edit_df.at[idx, 'Order']
                                    st.session_state['schedule_df'] = edit_df.sort_values(by=['Day', 'Order'])
                                    st.rerun()
                            with c5:
                                if st.button("🗑️", key=f"ai_del_{idx}"):
                                    place_to_del = edit_df.at[idx, 'Place']
                                    # 刪除該行
                                    edit_df = edit_df.drop(idx)
                                    # 重新編號該天的 Order
                                    edit_df.loc[edit_df['Day'] == ed_day, 'Order'] = range(1, sum(edit_df['Day'] == ed_day) + 1)
                                    st.session_state['schedule_df'] = edit_df.sort_values(by=['Day', 'Order'])
                                    
                                    # 同步刪除天氣快取中的紀錄 (如果有)
                                    if st.session_state.get('ai_weather_df') is not None:
                                        w_df = st.session_state['ai_weather_df']
                                        w_df = w_df[~((w_df['Day'] == ed_day) & (w_df['Place'] == place_to_del))]
                                        st.session_state['ai_weather_df'] = w_df
                                        
                                    st.toast(f"🗑️ 已刪除 {place_to_del}")
                                    st.rerun()
                        st.divider()
                # ------------------------------------------------

                # 2. 每日出發點明細
                with st.expander("🚗 查看每日出發點明細", expanded=True):
                    start_pt = st.session_state.get('input_start_point', '起點')
                    for d in sorted(df_itinerary['Day'].unique()):
                        if d == 1:
                            st.write(f"🚩 **Day 1** 出發點：`{start_pt}`")
                        else:
                            prev_day_last = df_itinerary[df_itinerary['Day'] == d-1].sort_values('Order').iloc[-1]['Place']
                            st.write(f"🚩 **Day {d}** 出發點：`{prev_day_last}` (接續前日終點)")

            with tab2:
                if st.session_state.get('schedule_df') is not None:
                    # 1. 取得行程表內的景點
                    trip_spots = st.session_state['schedule_df']['Place'].dropna().unique().tolist()

                    # 2. 取得「當頁」推薦的景點
                    rec_spots = []
                    if 'last_recommend_data' in st.session_state and not st.session_state['last_recommend_data'].empty:
                        rec_spots = st.session_state['last_recommend_data']['ScenicSpotName'].tolist()

                    # 3. 組合清單與基礎視覺標籤
                    combined_spots = []
                    spot_labels = {}

                    # 先放入「行程內」的景點
                    for spot in trip_spots:
                        if spot not in combined_spots:
                            combined_spots.append(spot)
                            spot_labels[spot] = f"🚩 [行程景點] {spot}"

                    # --- 🔴 核心修正：強制將「查看中」的景點移到最前面 ---
                    temp_spot = st.session_state.get('temp_view_spot')
                    
                    if temp_spot:
                        # 如果它已經在清單中，先把它移除
                        if temp_spot in combined_spots:
                            combined_spots.remove(temp_spot)
                        
                        # 強制把這個景點插入到陣列的第 0 個位置 (最上方)
                        combined_spots.insert(0, temp_spot)
                        # 更新標籤，讓使用者知道這是目前點擊查看的目標
                        spot_labels[temp_spot] = f"🔍 [目前查看] {temp_spot}"

                    # 5. 渲染下拉選單
                    if combined_spots:
                        p = st.selectbox(
                            "查看景點詳情：", 
                            options=combined_spots, 
                            index=0,  # 因為目標一定被移到了第 0 個，所以預設選中 0 即可
                            format_func=lambda x: spot_labels.get(x, x),
                            key="ai_tab2_selectbox_final"
                        )
                        if p: 
                            search_and_display_google_place(p)
                    else:
                        st.info("尚無景點資料。")
                else:
                    st.info("請先生成行程以查看景點詳情。")
                    
            with tab3:
                g = generate_dot_from_df(st.session_state['schedule_df'])
                if g: st.graphviz_chart(g, use_container_width=True)
            with tab4:
                st.markdown("### ⛅ 天氣預報")
                w_df = st.session_state.get('ai_weather_df')
                if w_df is not None and not w_df.empty:
                    u_days = sorted(w_df['Day'].unique())
                    w_tabs = st.tabs([f"Day {d}" for d in u_days])
                    for i, d in enumerate(u_days):
                        with w_tabs[i]:
                            d_w = w_df[w_df['Day'] == d]
                            st.dataframe(d_w, hide_index=True, use_container_width=True)
                            render_rain_swap_ui(d_w, 'ai')
                            st.info(generate_clothing_advice(d_w))
               
        
# --- 歷史紀錄頁面 ---
def history_page():
    sidebar_component()
    st.title("📜 我的旅遊歷史紀錄")
    
    # 讀取資料
    all_history = load_history()
    user_email = st.session_state.get('user_email') 
    
    if not user_email:
        st.error("系統錯誤：無法識別使用者 Email，請重新登入。")
        return

    my_records = [r for r in all_history if r['email'] == user_email]
    
    if not my_records:
        st.info("目前沒有歷史紀錄。趕快去規劃一個行程並儲存吧！")
    else:
        # 按時間倒序排列
        my_records = sorted(my_records, key=lambda x: x['timestamp'], reverse=True)
        
        for record in my_records:
            trip_name = record.get('trip_name', '').strip()
            if not trip_name: display_title = "(未命名行程)"
            else: display_title = trip_name
            
            expander_title = f"📂 {display_title} 　🕒 {record['timestamp'][:10]}"
            
            with st.expander(expander_title):
                # --- 1. 編輯名稱區塊 ---
                st.caption("✏️ 編輯行程名稱")
                col_edit_input, col_edit_btn = st.columns([3, 1], vertical_alignment="bottom")
                with col_edit_input:
                    new_name_input = st.text_input("名稱", value=trip_name, key=f"input_name_{record['id']}", label_visibility="collapsed")
                with col_edit_btn:
                    if st.button("🖊️ 確認修改", key=f"btn_rename_{record['id']}", use_container_width=True):
                        if new_name_input != trip_name:
                            update_history_name_in_db(record['id'], new_name_input)
                            st.toast(f"✅ 名稱已更新為：{new_name_input}")
                            time.sleep(0.5)
                            st.rerun()
                st.divider()

                # --- 2. 準備基本資料 ---
                # 取得出發日期物件 (for 計算日期用)
                record_start_date_str = record.get('start_date')
                start_d = None
                if record_start_date_str:
                    try:
                        start_d = datetime.strptime(record_start_date_str, "%Y-%m-%d").date()
                    except: pass
                
# --- 3. 顯示行程內容 (統一 AI 與手動格式) ---
                data_content = record.get('data', [])
                df_history = pd.DataFrame()
                
                if data_content:
                    # 相容舊版手動模式 (只有存簡單字串陣列的格式)
                    if isinstance(data_content, dict):
                        temp_list = []
                        for day_k, spots in data_content.items():
                            for idx, spot in enumerate(spots):
                                c, dist = "", ""
                                if 'attractions_db' in globals() and attractions_db is not None:
                                    r = attractions_db[attractions_db['ScenicSpotName'] == spot]
                                    if not r.empty:
                                        c, dist = r.iloc[0]['City'], r.iloc[0]['District']
                                temp_list.append({
                                    "Day": int(day_k), "Order": idx + 1, "Place": spot,
                                    "City": c, "District": dist, "Transport": "自行開車"
                                })
                        if temp_list:
                            df_history = pd.DataFrame(temp_list)
                    # 新版格式 (AI 模式與新版手動模式)
                    elif isinstance(data_content, list):
                        df_history = pd.DataFrame(data_content)

                if not df_history.empty and 'Day' in df_history.columns:
                    # 建立四大分頁 (AI 與手動皆可享有)
                    h_tab1, h_tab2, h_tab3, h_tab4 = st.tabs(["🗓️ 行程表", "📸 圖文詳情", "📊 流程圖", "⛅ 當時天氣紀錄"])                        
                    
                    # --- 分頁 1: 行程表 (含天數分頁與下載按鈕) ---
                    with h_tab1:
                        unique_days = sorted(df_history['Day'].unique())
                        day_tabs = st.tabs([f"Day {int(d)}" for d in unique_days])
                        
                        for i, day in enumerate(unique_days):
                            with day_tabs[i]:
                                day_df = df_history[df_history['Day'] == day].sort_values(by="Order")
                                
                                # (A) 導航按鈕
                                day_spots = day_df['Place'].tolist()
                                if day_spots:
                                    encoded_spots = [urllib.parse.quote(spot) for spot in day_spots]
                                    map_url = f"https://www.google.com/maps/dir/{'/'.join(encoded_spots)}"
                                    try:
                                        if start_d:
                                            current_date = start_d + timedelta(days=int(day)-1)
                                            date_label = f"{current_date.month}/{current_date.day}"
                                        else:
                                            date_label = f"Day {day}"
                                    except:
                                        date_label = f"Day {day}"

                                    st.link_button(
                                        label=f"🗺️ 開啟 Day {int(day)} ({date_label}) 導航",
                                        url=map_url,
                                        use_container_width=True
                                    )
                                
                                # (B) 表格顯示
                                st.dataframe(
                                    day_df,
                                    hide_index=True,
                                    use_container_width=True,
                                    column_config={
                                        "Day": st.column_config.NumberColumn("Day", disabled=True),
                                        "Order": st.column_config.NumberColumn("序", min_value=1, width="small"),
                                        "Place": st.column_config.TextColumn("景點", width="medium"),
                                        "Transport": st.column_config.TextColumn("交通", width="large")
                                    }
                                )
                                
                                # (C) 圖文卡片
                                html_view = generate_html_display(day_df, start_date=start_d)
                                st.markdown(html_view, unsafe_allow_html=True)

                        st.markdown("---")
                        # 📥 統一下載文字檔按鈕
                        txt_hist = generate_plain_text(df_history, start_date=start_d)
                        file_name = f"history_{display_title}.txt"
                        st.download_button("📥 下載文字檔", txt_hist, file_name, key=f"dl_txt_{record['id']}", use_container_width=True)

                    # --- 分頁 2: 圖文詳情 ---
                    with h_tab2:
                        place_options = df_history['Place'].unique().tolist()
                        selected_place = st.selectbox("查看景點詳情：", place_options, key=f"sel_spot_{record['id']}")
                        if selected_place:
                            display_attraction_details(selected_place)
                    
                    # --- 分頁 3: 流程圖 ---
                    with h_tab3:
                        dot_code = generate_dot_from_df(df_history)
                        if dot_code:
                            st.graphviz_chart(dot_code, use_container_width=True)
                            st.download_button("📥 下載 DOT 檔", dot_code, f"{display_title}.dot", key=f"dl_dot_{record['id']}")
                    
                    # --- 分頁 4: 天氣紀錄 ---
                    with h_tab4:
                        saved_weather = record.get('weather_content', [])
                        if saved_weather:
                            w_df_history = pd.DataFrame(saved_weather)
                            if not w_df_history.empty and 'Day' in w_df_history.columns:
                                u_days = sorted(w_df_history['Day'].unique())
                                wh_tabs = st.tabs([f"Day {int(d)}" for d in u_days])
                                
                                for i, day in enumerate(u_days):
                                    with wh_tabs[i]:
                                        day_w_data = w_df_history[w_df_history['Day'] == day]
                                        st.dataframe(
                                            day_w_data,
                                            hide_index=True,
                                            use_container_width=True,
                                            column_config={
                                                "Day": None, "Date": None,
                                                "Place": st.column_config.TextColumn("📍 景點"),
                                                "Temp": st.column_config.TextColumn("🌡️ 氣溫"),
                                                "Rain": st.column_config.TextColumn("☔ 降雨"),
                                                "Note": st.column_config.TextColumn("備註")
                                            }
                                        )
                                        st.markdown("#### 👗 當時穿搭建議")
                                        if 'generate_clothing_advice' in globals():
                                            advice = generate_clothing_advice(day_w_data)
                                            with st.container(border=True):
                                                st.markdown(advice)
                            else:
                                st.info("⚠️ 儲存的天氣資料格式有誤。")
                        else:
                            st.info("⚠️ 此紀錄未包含天氣資訊。")
                else:
                    st.warning("查無行程資料或格式錯誤")
                
                # --- 4. 底部刪除按鈕 ---
                if st.button("🗑️ 刪除此紀錄", key=f"del_{record['id']}", type="primary", use_container_width=True):
                    delete_history_record(record['id'])
                    st.toast("✅ 紀錄已刪除")
                    time.sleep(0.5)
                    st.rerun()
# --- 手動模式頁面 ---
def manual_page():
    sidebar_component()
    st.title("📸 台灣景點圖片瀏覽器 (手動模式)")
    
    # --- 0. 初始化交通方式儲存庫 ---
    # 使用字典儲存：Key 為 "Day_Index" (例如 "1_0"), Value 為 "交通方式"
    if 'manual_trans_data' not in st.session_state:
        st.session_state['manual_trans_data'] = {}

    # 定義交通選項
    trans_options = ["自行開車", "大眾運輸", "機車", "步行", "計程車", "高鐵", "火車", "捷運", "租車", "公車"]

    # --- 1. 日期與天數設定 ---
    col_days, col_info = st.columns([1.5, 2])
    with col_days:
        date_range = st.date_input(
            "📅 設定旅遊日期範圍", 
            value=[st.session_state['trip_start_date'], st.session_state['trip_end_date']],
            min_value=date.today()
        )
        if len(date_range) == 2:
            new_start, new_end = date_range
            new_days = (new_end - new_start).days + 1
            if new_days != st.session_state['trip_days'] or new_start != st.session_state['trip_start_date']:
                st.session_state['trip_start_date'] = new_start
                st.session_state['trip_end_date'] = new_end
                st.session_state['trip_days'] = new_days
                # 重置行程
                for d in range(1, new_days + 1):
                    if d not in st.session_state['trip_schedule']:
                        st.session_state['trip_schedule'][d] = []
                st.rerun()  
    with col_info:
        st.info(f"目前規劃： **{st.session_state['trip_days']} 天**")
    
    st.markdown("---")

    # --- 2. 搜尋與加入景點 ---
    df = attractions_db
    if df is not None:
        search_keyword = st.text_input("🔍 搜尋關鍵字 (輸入景點名稱)：")
        if search_keyword:
            search_keyword = search_keyword.replace("台", "臺")
            df = df[df['ScenicSpotName'].str.contains(search_keyword, case=False, na=False, regex=False)]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            city_list = df['City'].unique().tolist()
            selected_city = st.selectbox("縣市：", city_list)
            df_city = df[df['City'] == selected_city]
        with c2:
            district_list = df_city['District'].unique().tolist()
            selected_district = st.selectbox("地區：", district_list)
            df_final = df_city[df_city['District'] == selected_district]
        with c3:
            spot_list = df_final['ScenicSpotName'].unique().tolist()
            selected_spot = st.selectbox("景點：", spot_list)

        if selected_spot:
            # 這裡用回你原本從 CSV 讀取詳細資訊的函式
            display_attraction_details(selected_spot)
            
            # --- [修改] 加入行程區域 ---
            col_add_day, col_add_trans, col_add_btn = st.columns([2, 2, 2], vertical_alignment="bottom")
            
            with col_add_day:
                day_options = {}
                for d in range(1, st.session_state['trip_days'] + 1):
                    curr = st.session_state['trip_start_date'] + timedelta(days=d-1)
                    day_options[d] = f"Day {d} ({curr.strftime('%m/%d')})"
                target_day = st.selectbox("加入哪一天？", options=day_options.keys(), format_func=lambda x: day_options[x])
            
            with col_add_trans:
                # 選擇交通方式
                selected_trans_mode = st.selectbox("前往此處的交通：", trans_options, index=0)

            with col_add_btn:
                if st.button(f"➕ 加入行程", type="primary", use_container_width=True):
                    if target_day not in st.session_state['trip_schedule']:
                        st.session_state['trip_schedule'][target_day] = []
                    
                    if selected_spot not in st.session_state['trip_schedule'][target_day]:
                        # 1. 加入景點
                        st.session_state['trip_schedule'][target_day].append(selected_spot)
                        # 2. 儲存交通方式 (Key 為 Day_Index)
                        new_idx = len(st.session_state['trip_schedule'][target_day]) - 1
                        st.session_state['manual_trans_data'][f"{target_day}_{new_idx}"] = selected_trans_mode
                        
                        st.toast(f"已加入 {selected_spot} ({selected_trans_mode})")
                        st.rerun()
                    else:
                        st.warning("該景點已在當天行程中")

    st.markdown("---")

    # --- 3. 行程顯示與進階功能 ---
    has_spots = any(len(spots) > 0 for spots in st.session_state['trip_schedule'].values())

    if has_spots:
        st.subheader("📋 行程總覽與分析")
        
        # 將資料轉換為 DataFrame (讀取 manual_trans_data)
        manual_data = []
        for day, spots in st.session_state['trip_schedule'].items():
            for idx, spot_name in enumerate(spots):
                city_str = ""
                dist_str = ""
                if attractions_db is not None:
                    row = attractions_db[attractions_db['ScenicSpotName'] == spot_name]
                    if not row.empty:
                        city_str = row.iloc[0]['City']
                        dist_str = row.iloc[0]['District']
                
                # 從 session_state 讀取交通方式，若無則預設"自行開車"
                t_key = f"{day}_{idx}"
                trans_val = st.session_state['manual_trans_data'].get(t_key, "自行開車")

                manual_data.append({
                    "Day": int(day),
                    "Order": idx + 1,
                    "Place": spot_name,
                    "City": city_str,
                    "District": dist_str,
                    "Transport": trans_val # 這裡填入選擇的值
                })
        
        manual_df = pd.DataFrame(manual_data)

        current_signature = json.dumps(manual_data, sort_keys=True, ensure_ascii=False)
        cached_data = st.session_state.get('manual_weather_cache', {})
        if cached_data.get("signature") != current_signature:
            start_d = st.session_state['trip_start_date']
            with st.spinner("☁️ 行程有變動，正在同步天氣資料..."):
                weather_df = process_schedule_weather(manual_df, start_d)
                st.session_state['manual_weather_cache'] = {
                    "signature": current_signature,
                    "df": weather_df
                }
        weather_cache_df = st.session_state['manual_weather_cache'].get("df")
        # -------------------------------------------------------------
        tab1, tab2, tab3, tab4 = st.tabs(["👓 行程預覽", "📸 圖文詳情", "📊 流程圖", "⛅ 天氣預報"])

        with tab1:
            # 恢復為互動式渲染器，支援點擊天氣跳出穿搭建議
            weather_cache_df = st.session_state['manual_weather_cache'].get("df")
            render_itinerary_with_weather_icons(
                manual_df,
                weather_df=weather_cache_df,
                start_date=st.session_state['trip_start_date'],
                mode='manual'
            )
            # 🟢 [新增] 獨立導航按鈕區塊 (位於編輯選單的上方)
            if not manual_df.empty:
                st.write("")
                unique_days = sorted(manual_df['Day'].unique())
                nav_cols = st.columns(len(unique_days) if len(unique_days) > 0 else 1)
                
                for i, d in enumerate(unique_days):
                    with nav_cols[i]:
                        day_spots = manual_df[manual_df['Day'] == d]['Place'].tolist()
                        if day_spots:
                            import urllib.parse
                            encoded_spots = [urllib.parse.quote(str(spot)) for spot in day_spots]
                            map_url = f"https://www.google.com/maps/dir/{'/'.join(encoded_spots)}"
                            
                            # 顯示清楚的 Day 導航按鈕
                            st.link_button(
                                label=f"🗺️ 開啟 Day {int(d)} 導航",
                                url=map_url,
                                use_container_width=True
                            )

            # --- 編輯區塊 (已移除內部的導航按鈕) ---
            with st.expander("🛠️ 編輯排序與刪除"):
                for day in range(1, st.session_state['trip_days'] + 1):
                    day_spots = st.session_state['trip_schedule'].get(day, [])
                    if day_spots:
                        # 🟢 [修改] 移除內部的 columns 與導航按鈕，只保留 Day 標題
                        st.markdown(f"<div style='margin-top: 10px; margin-bottom: 10px;'><b>Day {day}</b></div>", unsafe_allow_html=True)
                        
                        # --- 以下維持原本的編輯清單邏輯 ---
                        for i, spot in enumerate(day_spots):
                            # 版面分配：名稱 | 交通選單 | 上 | 下 | 刪
                            c1, c2, c3, c4, c5 = st.columns([4, 3, 1, 1, 1], vertical_alignment="center")
                            
                            with c1: 
                                st.write(f"{i+1}. {spot}")
                            
                            with c2:
                                # 交通方式編輯
                                curr_key = f"{day}_{i}"
                                curr_val = st.session_state['manual_trans_data'].get(curr_key, "自行開車")
                                try:
                                    idx_opt = trans_options.index(curr_val)
                                except:
                                    idx_opt = 0
                                
                                new_trans = st.selectbox(
                                    "交通", 
                                    trans_options, 
                                    index=idx_opt, 
                                    key=f"edit_trans_{day}_{i}", 
                                    label_visibility="collapsed"
                                )
                                if new_trans != curr_val:
                                    st.session_state['manual_trans_data'][curr_key] = new_trans
                                    st.rerun()

                            with c3:
                                if i > 0 and st.button("⬆️", key=f"main_up_{day}_{i}"):
                                    # 交換順序
                                    day_spots[i], day_spots[i-1] = day_spots[i-1], day_spots[i]
                                    # 交換交通資料
                                    k_curr, k_prev = f"{day}_{i}", f"{day}_{i-1}"
                                    d = st.session_state['manual_trans_data']
                                    d[k_curr], d[k_prev] = d.get(k_prev, "自行開車"), d.get(k_curr, "自行開車")
                                    st.rerun()
                            with c4:
                                if i < len(day_spots) - 1 and st.button("⬇️", key=f"main_down_{day}_{i}"):
                                    # 交換順序
                                    day_spots[i], day_spots[i+1] = day_spots[i+1], day_spots[i]
                                    # 交換交通資料
                                    k_curr, k_next = f"{day}_{i}", f"{day}_{i+1}"
                                    d = st.session_state['manual_trans_data']
                                    d[k_curr], d[k_next] = d.get(k_next, "自行開車"), d.get(k_curr, "自行開車")
                                    st.rerun()
                            with c5:
                                if st.button("🗑️", key=f"main_del_{day}_{i}"):
                                    day_spots.pop(i)
                                    # 刪除並重整交通資料 key
                                    d = st.session_state['manual_trans_data']
                                    if f"{day}_{i}" in d: del d[f"{day}_{i}"]
                                    for k in range(i, len(day_spots)): 
                                        old_key = f"{day}_{k+1}"
                                        new_key = f"{day}_{k}"
                                        if old_key in d:
                                            d[new_key] = d[old_key]
                                            del d[old_key]
                                    st.rerun()
                        st.divider()
            # --- [修改功能 1] 儲存與下載雙按鈕區塊 ---
            try:
                start_d = st.session_state['trip_start_date']
                txt_content = generate_plain_text(manual_df, start_date=start_d)
            except Exception as e:
                txt_content = "行程資料產生錯誤"

            col_save, col_download = st.columns(2)
            
            with col_save:
                # 左側：儲存行程按鈕
                if st.button("💾 儲存行程", type="primary", key="manual_save_btn", use_container_width=True):
                    # 抓取天氣快取資料
                    cache_df = st.session_state.get('manual_weather_cache', {}).get('df')
                    w_data = cache_df.to_dict('records') if cache_df is not None and not cache_df.empty else []
                    
                    # 執行儲存
                    save_history_record(
                        st.session_state.get('user_email'), 
                        "手動規劃行程", 
                        st.session_state['trip_days'], 
                        manual_df.to_dict('records'), 
                        'manual', 
                        start_d.strftime("%Y-%m-%d"), 
                        w_data
                    )
                    st.toast("✅ 手動行程已成功儲存！您可以到「歷史紀錄」查看。")
                    
                    # 🟢 [新增] 儲存完畢後，自動清空手動模式的所有暫存資料
                    st.session_state['trip_schedule'] = {d: [] for d in range(1, st.session_state['trip_days'] + 1)}
                    st.session_state['manual_trans_data'] = {}
                    st.session_state['manual_weather_cache']['signature'] = ""
                    st.session_state['manual_weather_cache']['df'] = None 
                    
                    # 稍微停頓讓使用者看見 Toast 成功訊息，然後重新整理畫面
                    time.sleep(0.8)
                    st.rerun()
                    
            with col_download:
                # 右側：下載行程表按鈕
                st.download_button(
                    label="📥 下載行程表",
                    data=txt_content,
                    file_name=f"手動規劃行程_{start_d.strftime('%m%d')}.txt",
                    mime="text/plain",
                    use_container_width=True,
                    key="manual_download_btn"
                )

        with tab2:
            # --- 修正：手動模式專用圖文詳情 ---
            if not manual_df.empty:
                trip_spots = manual_df['Place'].dropna().unique().tolist()
                
                combined_spots = []
                spot_labels = {}
                
                # 放入手動加入的行程景點 (優先在上方)
                for spot in trip_spots:
                    if spot not in combined_spots:
                        combined_spots.append(spot)
                        spot_labels[spot] = f"🚩 [行程景點] {spot}"
                        
                # 處理剛剛點擊查看的景點 (搜尋或推薦)
                temp_spot = st.session_state.get('temp_view_spot')
                default_idx = 0
                if temp_spot in combined_spots:
                    default_idx = combined_spots.index(temp_spot)
                elif temp_spot:
                    combined_spots.insert(0, temp_spot)
                    spot_labels[temp_spot] = f"🔍 [查看中] {temp_spot}"
                    default_idx = 0
                    
                if combined_spots:
                    p = st.selectbox(
                        "查看景點詳情：", 
                        options=combined_spots, 
                        index=default_idx, 
                        format_func=lambda x: spot_labels.get(x, x), # 顯示視覺標籤
                        key="manual_tab2_selectbox"
                    )
                    if p: display_attraction_details(p)
                else:
                    st.info("尚無景點資料。")
            else:
                st.info("請先從上方加入景點以查看詳情。")
        with tab3:
            st.info("💡 此圖表展示您的路線順序。")
            dot_code = generate_dot_from_df(manual_df)
            if dot_code:
                st.graphviz_chart(dot_code, use_container_width=True)

        with tab4:
            st.markdown("### ⛅ 旅遊當地天氣預報")
            
            if not manual_df.empty:
                # 1. 產生當前行程的「特徵簽章」(只要內容變動，字串就會變)
                # 使用 JSON dump 來將 list of dicts 轉成字串作為比對依據
                current_signature = json.dumps(manual_data, sort_keys=True, ensure_ascii=False)
                
                # 2. 檢查是否需要重新查詢
                # 如果快取是空的，或者簽章不符(行程有變)，就重新查詢
                cached_data = st.session_state.get('manual_weather_cache', {})
                if cached_data.get("signature") != current_signature:
                    start_d = st.session_state['trip_start_date']
                    with st.spinner("☁️ 行程有變動，正在更新天氣資料..."):
                        weather_df = process_schedule_weather(manual_df, start_d)
                        # 更新快取
                        st.session_state['manual_weather_cache'] = {
                            "signature": current_signature,
                            "df": weather_df
                        }
                else:
                    # 使用快取資料
                    weather_df = cached_data.get("df")

                # 3. 顯示資料 (邏輯同 AI 模式)
                if weather_df is not None and not weather_df.empty:
                    unique_days = sorted(weather_df['Day'].unique())
                    weather_tabs = st.tabs([f"Day {d}" for d in unique_days])
                    
                    for i, day in enumerate(unique_days):
                        with weather_tabs[i]:
                            day_weather = weather_df[weather_df['Day'] == day]
                            st.dataframe(
                                day_weather,
                                hide_index=True,
                                use_container_width=True,
                                column_config={
                                    "Day": None, "Date": None,
                                    "Place": st.column_config.TextColumn("📍 景點"),
                                    "Temp": st.column_config.TextColumn("🌡️ 氣溫"),
                                    "Rain": st.column_config.TextColumn("☔ 降雨"),
                                    "Note": st.column_config.TextColumn("備註", width="large")
                                }
                            )

                            # --- [插入點] 呼叫替換按鈕函式 ---
                            render_rain_swap_ui(day_weather, mode='manual')
                            # ------------------------------

                            st.markdown("#### 👗 每日穿搭小幫手")
                            if 'generate_clothing_advice' in globals():
                                advice = generate_clothing_advice(day_weather)
                                with st.container(border=True):
                                    st.markdown(advice)
            else:
                st.warning("請先加入景點以查看天氣。")
        
# --- 11. 路由控制 ---
def logged_in_interface():
    if st.session_state['mode'] == 'menu':
        menu_page()
    elif st.session_state['mode'] == 'ai_chat':
        ai_planning_page()
    elif st.session_state['mode'] == 'manual':
        manual_page()
    elif st.session_state['mode'] == 'history':
        history_page()

if st.session_state['logged_in']:
    logged_in_interface()
else:
    if st.session_state['current_page'] == 'signup':
        signup_page()
    elif st.session_state['current_page'] == 'forgot_password':
        forgot_password_page()
    elif st.session_state['current_page'] == 'reset_password':
        reset_password_page()
    else:
        login_page()