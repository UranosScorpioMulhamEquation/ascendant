import os
import datetime
import uuid
from typing import Tuple, Dict, List, Any

import geonamescache
import pandas as pd
import pytz
import streamlit as st
from timezonefinder import TimezoneFinder

import engine as E

# ==========================================
# ستايل الواجهة الاحترافية (كحلي داكن ملكي + ذهبي مشع)
# ==========================================
CUSTOM_UI_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&display=swap');

/* إعدادات الخط والاتجاه والخلفية العامة */
html, body, [class*="css"], .stApp {
    font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif !important;
    direction: rtl !important;
    text-align: right !important;
    background-color: #050B18 !important;
    color: #F5E096 !important;
}

/* التدرج الفلكي الفاخر للخلفية */
.stApp {
    background: radial-gradient(ellipse at 50% 5%, #0F2044 0%, #071026 50%, #030712 100%) !important;
    background-attachment: fixed !important;
}

/* شريط الرأس في ستريمليت */
header[data-testid="stHeader"] {
    background: rgba(5, 11, 24, 0.7) !important;
    backdrop-filter: blur(12px) !important;
}

/* العناوين الرئيسية والفرعية */
h1, h2, h3, h4, h5, h6, .stHeading {
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    color: #FFD700 !important;
    text-shadow: 0 0 15px rgba(255, 215, 0, 0.3) !important;
    letter-spacing: -0.3px;
}

h1 {
    font-size: 2.2rem !important;
    background: linear-gradient(135deg, #FFF099 0%, #FFD700 50%, #D4AF37 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding-bottom: 8px;
    border-bottom: 2px solid rgba(255, 215, 0, 0.35);
    margin-bottom: 18px !important;
}

h2, h3 {
    color: #FFDF73 !important;
    border-right: 4px solid #D4AF37;
    padding-right: 12px !important;
    margin-top: 15px !important;
}

p, span, label, div {
    color: #F7E1A0;
}

.stCaption, small, [data-testid="stCaptionContainer"] {
    color: #D4BA72 !important;
    font-size: 0.88rem !important;
    line-height: 1.6 !important;
}

/* بطاقات الأعمدة وحاويات الإدخال */
[data-testid="column"] {
    background: rgba(12, 25, 54, 0.55) !important;
    border: 1px solid rgba(218, 165, 32, 0.28) !important;
    border-radius: 14px !important;
    padding: 20px 22px !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 215, 0, 0.15) !important;
    transition: all 0.3s ease-in-out !important;
}

[data-testid="column"]:hover {
    border-color: rgba(255, 215, 0, 0.5) !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 15px rgba(218, 165, 32, 0.15) !important;
}

/* حقول الإدخال النصية والرقمية والتواريخ */
input, textarea, [data-baseweb="input"], [data-baseweb="base-input"] {
    background-color: #0A1630 !important;
    color: #FFF2B2 !important;
    border-color: rgba(212, 175, 55, 0.4) !important;
    border-radius: 9px !important;
    font-family: 'Cairo', sans-serif !important;
}

input:focus, textarea:focus, [data-baseweb="input"]:focus-within {
    border-color: #FFD700 !important;
    box-shadow: 0 0 14px rgba(255, 215, 0, 0.4) !important;
}

/* حقول الاختيار المنسدلة */
[data-baseweb="select"] {
    background-color: #0A1630 !important;
    border-radius: 9px !important;
    color: #FFF2B2 !important;
}

[data-baseweb="select"] > div {
    background-color: #0A1630 !important;
    border-color: rgba(212, 175, 55, 0.4) !important;
    color: #FFF2B2 !important;
}

/* نوافذ القوائم المنبثقة */
div[data-baseweb="popover"], div[data-baseweb="popover"] > div, ul[data-baseweb="menu"] {
    background-color: #0B1A3B !important;
    border: 1px solid rgba(255, 215, 0, 0.45) !important;
    border-radius: 10px !important;
    color: #FFDF73 !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7) !important;
}

li[role="option"] {
    color: #F5E096 !important;
    background-color: transparent !important;
    transition: all 0.2s ease;
}

li[role="option"]:hover, li[aria-selected="true"] {
    background-color: #173268 !important;
    color: #FFD700 !important;
    font-weight: 700 !important;
}

/* وسم الاختيارات المتعددة */
[data-baseweb="tag"] {
    background: linear-gradient(135deg, #1C3566 0%, #112349 100%) !important;
    border: 1px solid #D4AF37 !important;
    border-radius: 6px !important;
    color: #FFD700 !important;
}

[data-baseweb="tag"] span {
    color: #FFD700 !important;
}

/* بطاقات النتائج الإحصائية الفلكية */
[data-testid="stMetric"] {
    background: linear-gradient(145deg, #0F2044 0%, #081228 100%) !important;
    border: 1px solid rgba(218, 165, 32, 0.45) !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 215, 0, 0.2) !important;
    text-align: center !important;
}

[data-testid="stMetricValue"] {
    color: #FFD700 !important;
    font-size: 1.65rem !important;
    font-weight: 900 !important;
    text-shadow: 0 0 14px rgba(255, 215, 0, 0.4) !important;
    display: flex;
    justify-content: center;
}

[data-testid="stMetricLabel"] {
    color: #FCE69C !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    display: flex;
    justify-content: center;
}

/* الأزرار العادية والأساسية */
.stButton > button {
    background: linear-gradient(135deg, #D4AF37 0%, #AA7A1E 100%) !important;
    color: #060D1D !important;
    font-weight: 800 !important;
    font-size: 1.05rem !important;
    border: 1px solid #FFE57F !important;
    border-radius: 10px !important;
    padding: 0.6rem 2rem !important;
    box-shadow: 0 4px 18px rgba(212, 175, 55, 0.3) !important;
    transition: all 0.3s ease !important;
    font-family: 'Cairo', sans-serif !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #FFDF73 0%, #E5BE3B 100%) !important;
    color: #040814 !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 24px rgba(255, 215, 0, 0.6) !important;
    border-color: #FFFFFF !important;
}

/* الزر الرئيسي لإطلاق التصحيح */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #FFD700 0%, #E5B83B 50%, #B8860B 100%) !important;
    color: #050B17 !important;
    font-size: 1.25rem !important;
    font-weight: 900 !important;
    padding: 0.8rem 3rem !important;
    box-shadow: 0 6px 28px rgba(255, 215, 0, 0.45) !important;
    border: 1px solid #FFF2A3 !important;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #FFF099 0%, #FFD700 60%, #E5B83B 100%) !important;
    box-shadow: 0 8px 35px rgba(255, 215, 0, 0.75) !important;
    transform: translateY(-3px);
}

/* صناديق التنبيهات والمعلومات والتحذيرات */
[data-testid="stAlert"] {
    background-color: #091736 !important;
    border-right: 5px solid #FFD700 !important;
    border-top: 1px solid rgba(255, 215, 0, 0.3) !important;
    border-bottom: 1px solid rgba(255, 215, 0, 0.3) !important;
    border-left: 1px solid rgba(255, 215, 0, 0.3) !important;
    border-radius: 10px !important;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.35) !important;
}

[data-testid="stAlert"] * {
    color: #FFDF73 !important;
}

/* محرر البيانات والجداول */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    background-color: #08132B !important;
    border: 1px solid rgba(212, 175, 55, 0.4) !important;
    border-radius: 12px !important;
    padding: 8px !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45) !important;
}

/* الأكورديون والقوائم القابلة للتوسيع */
[data-testid="stExpander"] {
    background: #09152E !important;
    border: 1px solid rgba(212, 175, 55, 0.35) !important;
    border-radius: 10px !important;
    margin-bottom: 10px !important;
}

[data-testid="stExpander"] details summary {
    color: #FFDF73 !important;
    font-weight: 700 !important;
}

[data-testid="stExpander"] details summary:hover {
    color: #FFD700 !important;
}

/* أشرطة التمرير والمنزلقات */
[data-testid="stSlider"] div[role="slider"] {
    background-color: #FFD700 !important;
    border: 2px solid #060D1D !important;
    box-shadow: 0 0 12px #FFD700 !important;
}

/* الفواصل الأفقية المزخرفة بالذهب */
hr {
    border: none !important;
    height: 1.5px !important;
    background: linear-gradient(90deg, transparent, rgba(255, 215, 0, 0.7), transparent) !important;
    margin: 28px 0 !important;
}

/* تخصيص شريط التمرير الدقيق */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #050B17;
}
::-webkit-scrollbar-thumb {
    background: #8A6F27;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #FFD700;
}
</style>
"""

# ==================== 1. Security (Fixed) ====================
KEY_FILE = "license.key"

def get_machine_id():
    return hex(uuid.getnode())

def generate_password(mid):
    # مطابقة تامة لمنطق أداة فك الحماية الثابتة
    digits = ''.join(filter(str.isdigit, mid))
    if not digits:
        try:
            digits = str(int(mid, 16))
        except:
            return "Error"
    num = int(digits)
    result = round(abs(num / 2 * 3.14))
    return str(result)[:6]

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = os.path.exists(KEY_FILE)

if not st.session_state['authenticated']:
    st.set_page_config(page_title="Security", layout="centered")
    st.markdown(CUSTOM_UI_STYLE, unsafe_allow_html=True)
    st.title("Security Activation - Ask the programmer for your password")
    st.warning("Send your Machine ID to programmer email : mulham81ahmed@gmail.com ")

    mid = get_machine_id()
    st.info(f"Machine ID: {mid}")
    pwd = st.text_input("Enter Activation Key:", type="password")

    if st.button("Activate"):
        if pwd == generate_password(mid):
            with open(KEY_FILE, "w") as f:
                f.write(pwd)
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.error("Invalid Activation Key.")

    st.stop()

st.set_page_config(page_title="نظام تصحيح الطالع المتقدم", layout="wide")
st.markdown(CUSTOM_UI_STYLE, unsafe_allow_html=True)

# ==========================================
# 0. تهيئة مسار ملفات الـ Ephemeris
# ==========================================
EPHE_PATH = "./ephe"
if not os.path.exists(EPHE_PATH):
    os.makedirs(EPHE_PATH)

@st.cache_resource
def get_eph() -> E.SwissEphemeris:
    return E.SwissEphemeris(EPHE_PATH)

# ==========================================
# 1. البيانات الجغرافية
# ==========================================
@st.cache_data
def load_geo_data():
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    cities = gc.get_cities()
    country_map = {c["name"]: code for code, c in countries.items()}
    sorted_countries = sorted(list(country_map.keys()))
    cities_by_country: Dict[str, List[Dict[str, Any]]] = {}
    for c_code in country_map.values():
        c_cities = [city for city in cities.values() if city["countrycode"] == c_code]
        cities_by_country[c_code] = sorted(c_cities, key=lambda x: x["population"], reverse=True)
    return country_map, sorted_countries, cities_by_country

country_map, country_list, cities_by_country = load_geo_data()

@st.cache_resource
def get_tz_finder() -> TimezoneFinder:
    return TimezoneFinder()

tf = get_tz_finder()

def make_to_utc(tz_str: str):
    tz = pytz.timezone(tz_str)
    def f(naive: datetime.datetime) -> datetime.datetime:
        return tz.localize(naive, is_dst=False).astimezone(pytz.utc).replace(tzinfo=None)
    return f

# ==========================================
# 2. النوافذ الزمنية الثمانية (3 ساعات لكل نافذة)
# ==========================================
WINDOWS = {
    "من 7 ص إلى 10 ص  (07–10)": 7,
    "من 10 ص إلى 1 م  (10–13)": 10,
    "من 1 م إلى 4 م  (13–16)": 13,
    "من 4 م إلى 7 م  (16–19)": 16,
    "من 7 م إلى 10 م  (19–22)": 19,
    "من 10 م إلى 1 فجرًا  (22–01)": 22,
    "من 1 فجرًا إلى 4 فجرًا  (01–04)": 1,
    "من 4 فجرًا إلى 7 ص  (04–07)": 4,
}

# ==========================================
# 3. الواجهة
# ==========================================
st.title("نظام تصحيح الطالع الفلكي و درجته و ساعة الميلاد - من أحداث الماضي")
st.write("التسيير بالاتجاهات الأولية + الأقواس الشمسية + التقدمية الثانوية + العبور") 
st.write("تطوير الفلكي استرو رادار")
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    st.subheader("بيانات المولود")
    name = st.text_input("اسم الشخص:", "أحمد")
    gender_ar = st.selectbox("الجنس", ["ذكر", "أنثى"])
    gender = 'M' if gender_ar == "ذكر" else 'F'
    birth_date = st.date_input("تاريخ الميلاد:", value=datetime.date(1990, 1, 1),
                               min_value=datetime.date(1900, 1, 1), max_value=datetime.date.today())
    win_label = st.selectbox("نطاق الساعة (3 ساعات تحوي ساعة الميلاد الحقيقية)", list(WINDOWS.keys()), index=1)
    start_hour = WINDOWS[win_label]
    anchor = 'forward'
    if start_hour == 22:
        anchor_ar = st.radio("هذه النافذة تعبر منتصف الليل — ما معنى تاريخ الميلاد المُدخل؟",
                             ["22:00 في هذا التاريخ ← 01:00 صباح اليوم التالي",
                              "22:00 من اليوم السابق ← 01:00 صباح هذا التاريخ"])
        anchor = 'forward' if anchor_ar.startswith("22:00 في") else 'backward'

with col2:
    st.subheader("مكان الميلاد")
    selected_country = st.selectbox("بلد الميلاد", country_list,
                                    index=country_list.index("Egypt") if "Egypt" in country_list else 0)
    country_cities = cities_by_country.get(country_map[selected_country], [])
    city_names = [c["name"] for c in country_cities]
    manual = st.checkbox("إدخال الإحداثيات يدويًا (أدق — ستاديا ص71 يشدد على الإحداثيات الدقيقة)")
    if manual or not city_names:
        lat = st.number_input("خط العرض (شمال +)", value=30.0444, format="%.4f")
        lon = st.number_input("خط الطول (شرق +)", value=31.2357, format="%.4f")
    else:
        city = st.selectbox("مدينة الميلاد (مرتبة حسب الكثافة السكانية)", city_names)
        cd = next(c for c in country_cities if c["name"] == city)
        lat, lon = cd["latitude"], cd["longitude"]
    tz_default = tf.timezone_at(lng=lon, lat=lat) or "UTC"
    tz_str = st.text_input("المنطقة الزمنية (IANA)", tz_default)
    st.info(f"📍 عرض {lat:.4f} | طول {lon:.4f} | 🕒 {tz_str}")

st.divider()
st.subheader("أحداث الماضي")
st.caption("أضف كل حدث مؤرَّخ تعرفه (وفاة، ولادة، زواج، عملية، سفر…). كلما زاد العدد وقلّ الغموض ارتفعت الدقة: "
           "ستاديا يوصي بـ 14–16 حدثًا مهمًا لبحث 2–3 ساعات، وحدث واحد لا يكفي لتمييز وقت واحد عن غيره. "
           "ساعة الحدث اختيارية (إن تُركت فارغة تُستبعد عبورات القمر).")

kinds = list(E.EVENT_TYPES.keys())
if 'events_df' not in st.session_state:
    st.session_state['events_df'] = pd.DataFrame({
        "نوع الحدث": [kinds[0]],
        "التاريخ": [datetime.date(2025, 6, 1)],
        "الساعة (اختياري)": [None],
        "الوزن": [1.0],
    })

events_df = st.data_editor(
    st.session_state['events_df'], num_rows="dynamic", use_container_width=True, key="ev_editor",
    column_config={
        "نوع الحدث": st.column_config.SelectboxColumn(options=kinds, required=True),
        "التاريخ": st.column_config.DateColumn(min_value=datetime.date(1900, 1, 1), max_value=datetime.date.today()),
        "الساعة (اختياري)": st.column_config.TimeColumn(),
        "الوزن": st.column_config.NumberColumn(min_value=0.1, max_value=3.0, step=0.1, default=1.0,
                                               help="1 = عادي، 2 = حدث مؤكد التاريخ والأهمية"),
    },
)

st.divider()
c1, c2, c3 = st.columns(3)
with c1:
    step_s = st.select_slider("دقة المسح (ثانية بين كل مرشّح وآخر)", options=[4, 8, 12, 20, 30], value=8)
with c2:
    tech_labels = {"اتجاهات أولية (توبوسنتريك)": 'PD', "تسيير ثانوي (تقدمية)": 'SD',
                   "أقواس شمسية": 'SA', "عبور (مباشر وما قبل الولادة)": 'TR'}
    chosen = st.multiselect("الخرائط المستخدمة", list(tech_labels.keys()), default=list(tech_labels.keys()))
with c3:
    do_null = st.checkbox("اختبار الدلالة الإحصائية (أبطأ)", value=False,
                          help="يعيد الحساب بتواريخ أحداث مُزاحة عشوائيًا ليُظهر كم مرة يظهر تطابق بهذا الحجم بالصدفة")
    null_runs = st.slider("عدد المحاكاة", 10, 60, 20) if do_null else 0

if st.button("بدء التصحيح 🚀", type="primary"):
    rows = events_df.dropna(subset=["نوع الحدث", "التاريخ"])
    errors = []
    if rows.empty:
        errors.append("أضف حدثًا واحدًا على الأقل.")
    try:
        pytz.timezone(tz_str)
    except Exception:
        errors.append("المنطقة الزمنية غير صحيحة.")
    if not chosen:
        errors.append("اختر خريطة واحدة على الأقل.")
    to_utc = None
    events: List[E.Event] = []
    if not errors:
        to_utc = make_to_utc(tz_str)
        for _, r in rows.iterrows():
            d = r["التاريخ"]
            if isinstance(d, pd.Timestamp):
                d = d.date()
            elif isinstance(d, str):
                try:
                    d = pd.to_datetime(d).date()
                except Exception:
                    pass
            if d <= birth_date:
                errors.append(f"حدث «{r['نوع الحدث']}» بتاريخ {d} ليس بعد الميلاد.")
                continue

            # معالجة حقل الساعة وتحويل النصوص إلى datetime.time
            t = r["الساعة (اختياري)"]
            if t is None or (isinstance(t, float) and pd.isna(t)) or pd.isna(t):
                t = None
            elif isinstance(t, str):
                t_str = t.strip()
                if not t_str:
                    t = None
                else:
                    try:
                        t = datetime.time.fromisoformat(t_str)
                    except ValueError:
                        try:
                            t = pd.to_datetime(t_str).time()
                        except Exception:
                            t = None
            elif isinstance(t, (datetime.datetime, pd.Timestamp)):
                t = t.time()
            elif not isinstance(t, datetime.time):
                t = None

            w = r["الوزن"] if pd.notna(r["الوزن"]) else 1.0
            events.append(E.make_event(r["نوع الحدث"], d, t, to_utc, w))
    for e in errors:
        st.error("❌ " + e)

    if not errors:
        if len(events) < 3:
            st.warning("⚠️ عدد الأحداث قليل (أقل من 3). ستظهر نتائج لكن احتمال تطابقها بالصدفة مرتفع — "
                       "اعتبرها ترشيحًا لا تصحيحًا نهائيًا.")
        with st.spinner("جاري مسح النافذة وحساب الخرائط الأربع لكل مرشّح..."):
            res = E.rectify(get_eph(), birth_date, lat, lon, to_utc, events, gender, start_hour,
                            span_hours=3.0, step_s=step_s, anchor=anchor,
                            techniques=[tech_labels[c] for c in chosen], n_peaks=5, null_runs=null_runs)
        cands = res["candidates"]
        if not cands:
            st.warning("لم يُعثر على أي تطابق ضمن سماحيات الكتاب. راجع تواريخ الأحداث أو النافذة الزمنية.")
        else:
            top = cands[0]
            pts = top["points"]
            st.success("اكتمل التحليل ✅")
            st.markdown(f"### 🕒 أرجح وقت ميلاد محلي: **{top['time'].strftime('%H:%M:%S')}** "
                        f"({top['time'].strftime('%Y-%m-%d')})")
            m1, m2, m3 = st.columns(3)
            m1.metric("🎯 الطالع AS", E.describe_lon(pts["asc"]))
            m2.metric("⛰️ وتد السماء MC", E.describe_lon(pts["mc"]))
            m3.metric("🧭 النقطة الشرقية EP", E.describe_lon(pts["ep"]))
            st.caption(f"RAMC = {pts['ramc']:.4f}° ؛ RA(EP) = RAMC + 90° = {pts['ra_ep']:.4f}° "
                       f"(EP دالّة في RAMC وحده؛ كل 4 دقائق من الوقت ≈ 1° في EP والـMC، "
                       f"أما الطالع فيتغير بمعدل يعتمد على خط العرض والبرج).")

            if len(cands) > 1:
                ratio = top["score"] / max(cands[1]["score"], 1e-9)
                st.info(f"عرض هضبة التطابق حول الوقت الأول ≈ {top['plateau_s']} ثانية. "
                        f"نسبة نقاط الأول إلى الثاني = {ratio:.2f} "
                        f"({'تمييز جيد' if ratio >= 1.25 else 'تمييز ضعيف — أضف أحداثًا' if ratio < 1.1 else 'تمييز متوسط'}).")
            if res["null"]:
                n = res["null"]
                st.info(f"اختبار الصدفة ({n['runs']} محاكاة): أعلى نقاط حقيقية = {n['real']:.1f} مقابل "
                        f"متوسط {n['null_mean']:.1f} وأعلى 95٪ = {n['null_p95']:.1f} في الأحداث المُزاحة؛ "
                        f"القيمة التقريبية p ≈ {n['p']:.3f}.")

            st.subheader("المرشحون (مرتبون بالنقاط)")
            table = pd.DataFrame([{
                "الترتيب": i + 1, "الوقت المحلي": c["time"].strftime("%Y-%m-%d %H:%M:%S"),
                "النقاط": round(c["score"], 1), "الطالع": E.describe_lon(c["points"]["asc"]),
                "MC": E.describe_lon(c["points"]["mc"]), "EP": E.describe_lon(c["points"]["ep"]),
                "هضبة (ث)": c["plateau_s"],
            } for i, c in enumerate(cands)])
            st.dataframe(table, use_container_width=True, hide_index=True)

            st.subheader("تفصيل التطابقات للمرشح الأول")
            for ev, hits in top["detail"]:
                with st.expander(f"{ev.label} — {len(hits)} تطابق"):
                    if not hits:
                        st.write("لا تطابقات ضمن السماحيات لهذا الحدث عند هذا الوقت.")
                    for h in hits[:15]:
                        st.write(f"• [{h.tech}] {h.text} — فارق {h.orb:.1f}′ — {h.score:.1f} نقطة")

            st.caption("ملاحظات: الدقة تتحدد بعدد الأحداث وجودتها وصحة تاريخها، لا بالبرنامج وحده. "
                       "المنطقة الزمنية التاريخية (DST/LMT) قد تحمل خطأ في التواريخ القديمة. "
                       "المحرك مختبَر لنصف الكرة الشمالي.")
