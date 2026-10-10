import os
import datetime
from typing import Tuple, Dict, List, Any, Optional

import geonamescache
import pandas as pd
import pytz
import streamlit as st
import swisseph as swe
from timezonefinder import TimezoneFinder

# ==========================================
# 0. تهيئة مسار ملفات الـ Ephemeris
# ==========================================
EPHE_PATH = "./ephe"
if not os.path.exists(EPHE_PATH):
    os.makedirs(EPHE_PATH)

swe.set_ephe_path(EPHE_PATH)

# ==========================================
# 1. خدمات البيانات الجغرافية والزمنية والفلكية
# ==========================================
@st.cache_data
def load_geo_data() -> Tuple[geonamescache.GeonamesCache, Dict[str, str], List[str], Dict[str, List[Dict[str, Any]]]]:
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    cities = gc.get_cities()

    country_map = {c["name"]: code for code, c in countries.items()}
    sorted_countries = sorted(list(country_map.keys()))

    cities_by_country: Dict[str, List[Dict[str, Any]]] = {}
    for c_code in country_map.values():
        c_cities = [city for city in cities.values() if city["countrycode"] == c_code]
        c_cities_sorted = sorted(c_cities, key=lambda x: x["population"], reverse=True)
        cities_by_country[c_code] = c_cities_sorted

    return gc, country_map, sorted_countries, cities_by_country

gc, country_map, country_list, cities_by_country = load_geo_data()

@st.cache_resource
def get_tz_finder() -> TimezoneFinder:
    return TimezoneFinder()

tf = get_tz_finder()

def get_utc_julian_day(date_obj: datetime.date, time_obj: datetime.time, tz_str: str) -> float:
    local_tz = pytz.timezone(tz_str)
    dt = datetime.datetime.combine(date_obj, time_obj)
    local_dt = local_tz.localize(dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    return swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
    )

def get_zodiac_sign(degree: float) -> str:
    """تحويل الدرجة القوسية (0-360) إلى اسم البرج الفلكي"""
    signs = [
        "الحمل", "الثور", "الجوزاء", "السرطان", 
        "الأسد", "العذراء", "الميزان", "العقرب", 
        "القوس", "الجدي", "الدلو", "الحوت"
    ]
    index = int(degree // 30) % 12
    return signs[index]

# ==========================================
# 2. قواميس الأحداث الفلكية المدعومة (12 حدث)
# ==========================================
EVENTS_DICT = {
    "زواج (للذكور)": {"angles": ["DS", "MC"], "planets": [3, 1, 10, 5]}, 
    "زواج (للإناث)": {"angles": ["DS", "MC"], "planets": [0, 5, 4, 10]}, 
    "دخول المستشفى/مرض": {"angles": ["AS", "MC"], "planets": [6, 8, 4]}, 
    "وفاة الأب/الجد": {"angles": ["MC", "AS"], "planets": [6, 0, 8, 9, 4, 11]}, 
    "وفاة الأم/الجدة": {"angles": ["IC", "AS"], "planets": [1, 3, 6, 8, 9, 11, 4]}, 
    "طلاق أو انفصال": {"angles": ["DS", "IC"], "planets": [4, 6, 8, 11, 9]}, 
    "تغيير السكن": {"angles": ["IC", "AS"], "planets": [2, 1, 10, 5, 3, 0]},
    "موت ابن": {"angles": ["IC", "DS"], "planets": [4, 6, 8, 9, 11]}, 
    "موت ابنة": {"angles": ["IC", "DS"], "planets": [3, 1, 8, 9, 11]}, 
    "ولادة ابن": {"angles": ["AS", "IC"], "planets": [4, 0, 5, 10]}, 
    "ولادة ابنة": {"angles": ["AS", "IC"], "planets": [3, 1, 5, 10]}, 
    "سفر للخارج الدولة": {"angles": ["MC", "AS"], "planets": [1, 2, 7, 5]}
}

PLANET_NAMES = {
    0: "الشمس", 1: "القمر", 2: "عطارد", 3: "الزهرة", 4: "المريخ", 
    5: "المشتري", 6: "زحل", 7: "أورانوس", 8: "نبتون", 9: "بلوتو", 
    10: "راهو (العقدة الشمالية)", 11: "كيتو (العقدة الجنوبية)"
}

# ==========================================
# 3. الدوال الفلكية لتصحيح الطالع
# ==========================================
def get_planet_positions(jd: float) -> Dict[int, float]:
    positions = {}
    for p in range(10):
        pos, ret = swe.calc_ut(jd, p)
        positions[p] = pos[0]
    
    rahu_pos, _ = swe.calc_ut(jd, swe.MEAN_NODE)
    positions[10] = rahu_pos[0]
    positions[11] = (rahu_pos[0] + 180.0) % 360.0
    return positions

def get_angles(jd: float, lat: float, lon: float) -> Dict[str, float]:
    houses, ascmc = swe.houses(jd, lat, lon, b'W')
    as_deg = ascmc[0]
    mc_deg = ascmc[1]
    return {
        "AS": as_deg,
        "MC": mc_deg,
        "DS": (as_deg + 180.0) % 360.0,
        "IC": (mc_deg + 180.0) % 360.0
    }

def find_exact_birth_time(base_date, approx_time, event_date, event_type, lat, lon, tz_str):
    age_days = (event_date - base_date).days
    arc_degrees = age_days / 365.2425 
    
    target_angles = EVENTS_DICT[event_type]["angles"]
    target_planets = EVENTS_DICT[event_type]["planets"]
    
    start_dt = datetime.datetime.combine(base_date, approx_time) - datetime.timedelta(hours=1)
    end_dt = datetime.datetime.combine(base_date, approx_time) + datetime.timedelta(hours=1)
    
    current_dt = start_dt
    matches = []

    while current_dt <= end_dt:
        jd = get_utc_julian_day(current_dt.date(), current_dt.time(), tz_str)
        
        natal_planets = get_planet_positions(jd)
        natal_angles = get_angles(jd, lat, lon)
        
        prog_angles = {k: (v + arc_degrees) % 360.0 for k, v in natal_angles.items()}
        
        for angle_name in target_angles:
            p_angle = prog_angles[angle_name]
            for p_id in target_planets:
                n_planet = natal_planets[p_id]
                
                diff = (p_angle - n_planet) % 360.0
                if 0.0 <= diff <= 0.5:
                    matches.append({
                        "time": current_dt.time(),
                        "ascendant": natal_angles["AS"],
                        "mc_degree": natal_angles["MC"],
                        "angle_hit": angle_name,
                        "planet": PLANET_NAMES[p_id],
                        "orb": diff
                    })
        
        current_dt += datetime.timedelta(minutes=1)
        
    return matches

# ==========================================
# 4. واجهة المستخدم (Streamlit)
# ==========================================
st.set_page_config(page_title="برنامج تصحيح الطالع الفلكي", layout="wide")
st.title("نظام تصحيح الطالع المتقدم - التسيير على الأوتاد - برمجة الفلكي : استرو رادار")
st.markdown("---")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("بيانات المولود")
        name = st.text_input("اسم الشخص:", "أحمد")
        gender = st.selectbox("الجنس", ["ذكر", "أنثى"])
        birth_date = st.date_input("تاريخ الميلاد:", min_value=datetime.date(1900, 1, 1), max_value=datetime.date.today())
        approx_time = st.time_input("ساعة الميلاد التقريبية (± 1 ساعات)", datetime.time(12, 0), step=datetime.timedelta(minutes=30))

    with col2:
        st.subheader("مكان الميلاد (تلقائي)")
        selected_country = st.selectbox("بلد الميلاد", country_list, index=country_list.index("Egypt") if "Egypt" in country_list else 0)
        
        c_code = country_map[selected_country]
        country_cities = cities_by_country.get(c_code, [])
        city_names = [city["name"] for city in country_cities]
        
        if not city_names:
            st.error("لم يتم العثور على مدن لهذا البلد في قاعدة البيانات.")
            st.stop()
            
        selected_city_name = st.selectbox("مدينة الميلاد (مرتبة حسب الكثافة السكانية)", city_names)
        
        # استخراج الإحداثيات للمدينة المحددة
        selected_city_data = next(city for city in country_cities if city["name"] == selected_city_name)
        lat = selected_city_data["latitude"]
        lon = selected_city_data["longitude"]
        
        # تحديد المنطقة الزمنية تلقائياً
        tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
        st.info(f"📍 الإحداثيات: عرض {lat:.4f} | طول {lon:.4f}")
        st.info(f"🕒 المنطقة الزمنية التلقائية: {tz_str}")

st.divider()
st.subheader("بيانات الحدث للفلترة والتصحيح (آخر سنتين فقط)")
col3, col4 = st.columns(2)
with col3:
    event_type = st.selectbox("اختر نوع الحدث من القاموس", list(EVENTS_DICT.keys()))
with col4:
    # تقييد تاريخ الحدث ليكون بين 2024 و 2026 فقط
    min_event_date = datetime.date(2024, 1, 1)
    max_event_date = datetime.date(2026, 12, 31)
    
    st.caption("ملاحظة: لضمان دقة التسيير، تم قصر نطاق الحدث على الأعوام 2024 - 2025 - 2026.")
    event_date = st.date_input("تاريخ وقوع الحدث", min_value=min_event_date, max_value=max_event_date, value=datetime.date(2026, 1, 1))

if st.button("بدء التصحيح (Rectification) 🚀"):
    if event_date <= birth_date:
        st.error("❌ تاريخ الحدث يجب أن يكون بعد تاريخ الميلاد.")
    else:
        with st.spinner(f"جاري معالجة البيانات، مسح 6 ساعات حول {approx_time} وحساب التسييرات..."):
            results = find_exact_birth_time(birth_date, approx_time, event_date, event_type, lat, lon, tz_str)
            
            if results:
                st.success("✅ تم العثور على أوقات مطابقة لشروط الاقتران على الأوتاد!")
                
                # استخراج النتيجة الأقرب للاقتران التام
                best_match = min(results, key=lambda x: x["orb"])
                
                asc_degree = best_match['ascendant']
                zodiac_name = get_zodiac_sign(asc_degree)
                
                st.markdown(f"### 🕒 وقت الميلاد الدقيق المصحح: **{best_match['time'].strftime('%H:%M')}**")
                st.markdown(f"#### 🎯 درجة الطالع (Ascendant): **{asc_degree:.2f}° (برج {zodiac_name})**")
                st.markdown(f"#### ⛰️ درجة وتد السماء (MC): **{best_match['mc_degree']:.2f}°**")
                
                st.info(f"**التفسير الفلكي:** وقت حدوث **{event_type}**، حدث اقتران بين كوكب **{best_match['planet']}** والوتد **{best_match['angle_hit']}** في خريطة التسيير. الفارق الدقيق وقت الحدث كان: **{best_match['orb']:.3f}°** درجة قوسية.")
                
            else:
                st.warning("⚠️ لم يظهر أي كوكب من الكواكب ذات الصلة على الأوتاد خلال نطاق البحث (±1 ساعات). يرجى اختيار حدث آخر من القائمة المنسدلة لإعادة الفحص وضبط الطالع.")