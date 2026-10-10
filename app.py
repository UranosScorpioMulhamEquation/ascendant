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
# 2. قواميس الأحداث الفلكية المحدثة (شاملة الصورة المرفقة)
# ==========================================
EVENTS_DICT = {
    "السفر": {"angles": ["MC", "AS"], "planets": [1, 2, 7, 5]},
    "موت الاب او الجد": {"angles": ["MC", "AS"], "planets": [6, 0, 8, 9, 4, 11]},
    "موت الام او الجدة": {"angles": ["IC", "AS"], "planets": [1, 3, 6, 8, 9, 11, 4]},
    "موت الابن": {"angles": ["IC", "DS"], "planets": [4, 6, 8, 9, 11]},
    "موت الابنة": {"angles": ["IC", "DS"], "planets": [3, 1, 8, 9, 11]},
    "ولادة ابن": {"angles": ["AS", "IC"], "planets": [4, 0, 5, 10]},
    "ولادة ابنة": {"angles": ["AS", "IC"], "planets": [3, 1, 5, 10]},
    "تاريخ الزواج/عقد القران": {"angles": ["DS", "MC"], "planets": [3, 1, 10, 5, 0, 4]},
    "عملية جراحية بمشفى": {"angles": ["AS", "MC"], "planets": [6, 8, 4]},
    "ولادة أخ أصغر": {"angles": ["H3", "IC", "DS"], "planets": [2, 5, 0, 1, 3, 10, 7, 9]},
    "ولادة أخت صغرى": {"angles": ["H3", "IC", "DS"], "planets": [1, 2, 3, 0, 5, 10, 7, 9]}
}

PLANET_NAMES = {
    0: "الشمس", 1: "القمر", 2: "عطارد", 3: "الزهرة", 4: "المريخ", 
    5: "المشتري", 6: "زحل", 7: "أورانوس", 8: "نبتون", 9: "بلوتو", 
    10: "راهو (العقدة الشمالية)", 11: "كيتو (العقدة الجنوبية)"
}

# ==========================================
# 3. الدوال الفلكية وتحليل الخرائط الثلاث
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
        "IC": (mc_deg + 180.0) % 360.0,
        "H3": houses[2]  # وتد البيت الثالث للدلالة على الإخوة والأخوات
    }

def hierarchical_rectification(birth_date, approx_time, event_date, event_type, lat, lon, tz_str):
    target_angles = EVENTS_DICT[event_type]["angles"]
    target_planets = EVENTS_DICT[event_type]["planets"]
    
    age_years = (event_date - birth_date).days / 365.2425
    
    # حساب الأقواس الشمسية
    jd_birth_approx = get_utc_julian_day(birth_date, approx_time, tz_str)
    jd_event = get_utc_julian_day(event_date, datetime.time(12, 0), tz_str)
    
    sun_birth, _ = swe.calc_ut(jd_birth_approx, 0)
    sun_event, _ = swe.calc_ut(jd_event, 0)
    solar_arc = (sun_event[0] - sun_birth[0]) % 360.0

    # النطاق الزمني الصحيح: ساعة قبل وساعة بعد الساعة المدخلة (±1 ساعة)
    base_dt = datetime.datetime.combine(birth_date, approx_time)
    start_dt = base_dt - datetime.timedelta(hours=1)
    end_dt = base_dt + datetime.timedelta(hours=1)

    max_orb_limit = 0.50  # الحد الأقصى للسماحية حتى 0.50 درجة

    # ----------------------------------------------------
    # المرحلة الأولى: خريطة اتجاهات الأقواس الشمسية (تحديد الساعة بدقة)
    # ----------------------------------------------------
    best_hour = approx_time.hour
    min_sa_orb = float('inf')
    
    current_dt = start_dt
    while current_dt <= end_dt:
        jd = get_utc_julian_day(current_dt.date(), current_dt.time(), tz_str)
        natal_angles = get_angles(jd, lat, lon)
        natal_planets = get_planet_positions(jd)
        
        prog_angles = {k: (v + solar_arc) % 360.0 for k, v in natal_angles.items()}
        
        for angle_name in target_angles:
            if angle_name in prog_angles:
                p_angle = prog_angles[angle_name]
                for p_id in target_planets:
                    n_planet = natal_planets[p_id]
                    diff = abs((p_angle - n_planet + 180) % 360 - 180)
                    if diff < min_sa_orb and diff <= max_orb_limit:
                        min_sa_orb = diff
                        best_hour = current_dt.hour
        current_dt += datetime.timedelta(minutes=1)

    # ----------------------------------------------------
    # المرحلة الثانية: خريطة الثانوية التقدمية (تحديد الدقيقة)
    # ----------------------------------------------------
    best_minute = approx_time.minute
    min_sp_orb = float('inf')
    
    for minute in range(60):
        trial_time = datetime.time(best_hour, minute, 0)
        jd_trial = get_utc_julian_day(birth_date, trial_time, tz_str)
        
        jd_prog = jd_trial + age_years
        prog_planets = get_planet_positions(jd_prog)
        natal_angles = get_angles(jd_trial, lat, lon)
        
        for angle_name in target_angles:
            if angle_name in natal_angles:
                n_angle = natal_angles[angle_name]
                for p_id in target_planets:
                    p_planet = prog_planets[p_id]
                    diff = abs((p_planet - n_angle + 180) % 360 - 180)
                    if diff < min_sp_orb and diff <= max_orb_limit:
                        min_sp_orb = diff
                        best_minute = minute

    # ----------------------------------------------------
    # المرحلة الثالثة: خريطة العبور (تحديد الثانية)
    # ----------------------------------------------------
    best_second = 0
    min_tr_orb = float('inf')
    transit_planets = get_planet_positions(jd_event)
    
    for second in range(60):
        trial_time = datetime.time(best_hour, best_minute, second)
        jd_trial = get_utc_julian_day(birth_date, trial_time, tz_str)
        natal_angles = get_angles(jd_trial, lat, lon)
        
        for angle_name in target_angles:
            if angle_name in natal_angles:
                n_angle = natal_angles[angle_name]
                for p_id in target_planets:
                    t_planet = transit_planets[p_id]
                    diff = abs((t_planet - n_angle + 180) % 360 - 180)
                    if diff < min_tr_orb and diff <= max_orb_limit:
                        min_tr_orb = diff
                        best_second = second

    final_time = datetime.time(best_hour, best_minute, best_second)
    final_jd = get_utc_julian_day(birth_date, final_time, tz_str)
    final_angles = get_angles(final_jd, lat, lon)
    asc_deg = final_angles["AS"]
    zodiac_name = get_zodiac_sign(asc_deg)

    return {
        "time": final_time,
        "ascendant": asc_deg,
        "mc_degree": final_angles["MC"],
        "zodiac": zodiac_name,
        "orbs": {
            "solar_arc": min_sa_orb,
            "secondary": min_sp_orb,
            "transit": min_tr_orb
        }
    }

# ==========================================
# 4. واجهة المستخدم (Streamlit)
# ==========================================
st.set_page_config(page_title="نظام تصحيح الطالع المتقدم", layout="wide")
st.title("نظام تصحيح الطالع الفلكي و ساعة الميلاد - استرو رادار")
st.write("التحليل وفق خرائط  (اتجاهات الأقواس الشمسية) + (التقدمية الثانوية) + (العبور) - برمجة الفلكي الدكتور ملهم احمد")
st.markdown("---")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("بيانات المولود")
        name = st.text_input("اسم الشخص:", "أحمد")
        gender = st.selectbox("الجنس", ["ذكر", "أنثى"])
        birth_date = st.date_input("تاريخ الميلاد:", min_value=datetime.date(1900, 1, 1), max_value=datetime.date.today())
        approx_time = st.time_input("ساعة الميلاد التقريبية (± 1 ساعة)", datetime.time(11, 32), step=datetime.timedelta(minutes=12))

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
        
        selected_city_data = next(city for city in country_cities if city["name"] == selected_city_name)
        lat = selected_city_data["latitude"]
        lon = selected_city_data["longitude"]
        
        tz_str = tf.timezone_at(lng=lon, lat=lat) or "UTC"
        st.info(f"📍 الإحداثيات: عرض {lat:.4f} | طول {lon:.4f}")
        st.info(f"🕒 المنطقة الزمنية التلقائية: {tz_str}")

st.divider()
st.subheader("بيانات الحدث (خلال الأعوام 2022 - 2026)")
col3, col4 = st.columns(2)
with col3:
    event_type = st.selectbox("اختر نوع الحدث من القاموس", list(EVENTS_DICT.keys()))
with col4:
    min_event_date = datetime.date(2022, 1, 1)
    max_event_date = datetime.date(2026, 12, 31)
    st.caption("ملاحظة: النطاق الزمني مدعوم للأعوام 2022 حتى 2026.")
    event_date = st.date_input("تاريخ وقوع الحدث الماضي", min_value=min_event_date, max_value=max_event_date, value=datetime.date(2025, 6, 1))

if st.button("بدء التصحيح الهرمي للخرائط الثلاث 🚀"):
    if event_date <= birth_date:
        st.error("❌ تاريخ الحدث يجب أن يكون بعد تاريخ الميلاد.")
    else:
        with st.spinner("جاري المسح الدقيق للنطاق (ساعة قبل/بعد) ومعالجة الخرائط الثلاث بالتسلسل..."):
            res = hierarchical_rectification(birth_date, approx_time, event_date, event_type, lat, lon, tz_str)
            
            if res:
                st.success("  تم إنجاز التصحيح الفلكي التام بنجاح ✅ - مع العلم أن الدقة +/- 3 درجات للطالع أو +/-12 دقيقة!")
                
                st.markdown(f"### 🕒 وقت الميلاد الدقيق المصحح (بالساعة والدقيقة والثانية): **{res['time'].strftime('%H:%M:%S')}**")
                st.markdown(f"#### 🎯 درجة الطالع (Ascendant Degree): **{res['ascendant']:.4f}°**")
                st.markdown(f"#### ♈ اسم الطالع (Ascendant Sign): **برج {res['zodiac']}**")
                st.markdown(f"#### ⛰️ درجة وتد السماء (MC): **{res['mc_degree']:.4f}°**")
                
                st.info(
                    f"**تقرير المطابقة الفلكية والدقة:**\n"
                    f"- **الساعة المستخرجة (الأقواس الشمسية):** {res['time'].hour:02d}:00 (دقة الفارق: {res['orbs']['solar_arc']:.4f}°)\n"
                    f"- **الدقيقة المستخرجة (التقدمية الثانوية):** :{res['time'].minute:02d} (دقة الفارق: {res['orbs']['secondary']:.4f}°)\n"
                    f"- **الثانية المستخرجة (العبور الفلكي):** :{res['time'].second:02d} (دقة الفارق: {res['orbs']['transit']:.4f}°)"
                )
            else:
                st.warning("⚠️ لم يتم العثور على مطابقة ضمن نطاق السماحية المحددة (0.50 درجة). يرجى التأكد من صحة تاريخ الحدث أو ضبط ساعة الميلاد التقريبية.")
