from __future__ import annotations

import datetime as dt
import math
import os
import uuid
import random
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import geonamescache
import numpy as np
import pandas as pd
import pytz
import streamlit as st
import streamlit.components.v1 as components
from timezonefinder import TimezoneFinder
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


APP_TITLE = "استرو رادار لتصحيح ساعه الميلاد من ستة خرائط فلكية - تطوير الفلكي استرو رادار"
MAX_EVENT_AGE_YEARS = 20

# ==============================================================================
# 1. الثوابت الفلكية وجداول الرموز والدلالات (الغربية والعربية)
# ==============================================================================
NAIBOD_PER_DAY = 0.00269861      # مفتاح نايبود: 59'08.33"/سنة ÷ 365.2422
TROPICAL_YEAR = 365.2422
BASE_SCORE = 25.0

PLANETS = ['SUN', 'MOON', 'MER', 'VEN', 'MAR', 'JUP', 'SAT', 'URA', 'NEP', 'PLU', 'NN', 'SN']
PLANET_AR = {
    'SUN': 'الشمس', 'MOON': 'القمر', 'MER': 'عطارد', 'VEN': 'الزهرة', 'MAR': 'المريخ',
    'JUP': 'المشتري', 'SAT': 'زحل', 'URA': 'أورانوس', 'NEP': 'نبتون', 'PLU': 'بلوتو',
    'NN': 'العقدة الشمالية', 'SN': 'العقدة الجنوبية',
}
PLANET_GLYPH = {
    'SUN': '☉', 'MOON': '☽', 'MER': '☿', 'VEN': '♀', 'MAR': '♂',
    'JUP': '♃', 'SAT': '♄', 'URA': '♅', 'NEP': '♆', 'PLU': '♇',
    'NN': '☊', 'SN': '☋',
}
FACTOR_AR = {
    'AS': 'الطالع AS', 'MC': 'وتد السماء MC', 'DS': 'الغارب DS', 'IC': 'وتد الأرض IC',
    'EP': 'النقطة الشرقية EP', 'POF': 'سهم السعادة', 'POS': 'سهم الغيب',
    'H2': 'بيت 2', 'H3': 'بيت 3', 'H5': 'بيت 5', 'H6': 'بيت 6',
    'H8': 'بيت 8', 'H9': 'بيت 9', 'H11': 'بيت 11', 'H12': 'بيت 12',
}
SIGNS_AR = [
    "الحمل", "الثور", "الجوزاء", "السرطان", "الأسد", "العذراء",
    "الميزان", "العقرب", "القوس", "الجدي", "الدلو", "الحوت",
]
SIGN_GLYPHS = ['♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓']

# أرباب البروج التقليدية (التنجيم العربي والكلاسيكي)
SIGN_RULERS = ['MAR', 'VEN', 'MER', 'MOON', 'SUN', 'MER', 'VEN', 'MAR', 'JUP', 'SAT', 'SAT', 'JUP']

ASPECTS = (0, 30, 45, 60, 90, 120, 135, 150, 180)
MAJOR_ASPECTS = (0, 60, 90, 120, 180)
ASPECT_W = {
    0: 1.0, 180: 1.0, 90: 0.85, 120: 0.85, 60: 0.8,
    30: 0.4, 45: 0.45, 135: 0.45, 150: 0.45,
}

# السماحيات الدقيقة بالدقائق القوسية لتحقيق دقة الثانية الواحدة من حدث واحد
PD_ORB_MAJOR, PD_ORB_MINOR = 11.0, 6.0
SA_ORB_MAJOR, SA_ORB_MINOR = 12.0, 6.0
TR_ORB = 60.0
SR_ORB_MAJOR, SR_ORB_MINOR = 48.0, 24.0
AP_ORB_MAJOR, AP_ORB_MINOR = 30.0, 15.0
SEC_ORB = {
    'SUN': 11.0, 'MER': 11.0, 'VEN': 11.0, 'MAR': 11.0,
    'JUP': 8.0, 'SAT': 8.0, 'URA': 4.0, 'NEP': 4.0, 'PLU': 4.0,
    'NN': 4.0, 'SN': 4.0,
}
SEC_ORB_MOON = (32.0, 18.0)

TECH_CODES = ('PD', 'SA', 'SD', 'AP', 'TR', 'SR')
TECH_AR = {
    'PD': 'الاتجاهات الأولية',
    'SA': 'الأقواس الشمسية',
    'SD': 'التقدمية الثانوية',
    'AP': 'الانتهاء السنوي',
    'TR': 'العبور الكوكبي',
    'SR': 'العودة الشمسية',
}


def _ev(sig, pl, sig2=(), pl2=(), houses=()):
    return dict(sig=list(sig), pl=list(pl), sig2=list(sig2), pl2=list(pl2), houses=list(houses))


EVENT_TYPES: Dict[str, dict] = {
    "السفر": _ev(['H9', 'MC', 'AS'], ['MOON', 'MER', 'URA', 'JUP'], ['EP'], ['VEN', 'NEP', 'SUN', 'NN'], [9, 3, 1]),
    "سفر سلبي (طارئ/مشاكل)": _ev(['H9', 'MC', 'AS'], ['SAT', 'MAR', 'NEP', 'PLU', 'MER', 'URA'], ['H12'], [], [9, 12]),
    "موت الاب او الجد": _ev(['MC', 'AS', 'H8'], ['SAT', 'SUN', 'NEP', 'PLU', 'MAR', 'SN'], ['H12', 'IC'], ['MOON', 'URA'], [10, 4, 8]),
    "موت الام او الجدة": _ev(['IC', 'AS', 'H8'], ['MOON', 'VEN', 'SAT', 'NEP', 'PLU', 'SN', 'MAR'], ['H12', 'MC'], ['SUN', 'URA'], [4, 10, 8]),
    "موت الابن": _ev(['H5', 'IC', 'DS', 'H8'], ['MAR', 'SAT', 'NEP', 'PLU', 'SN'], ['H12'], ['SUN', 'MER', 'URA'], [5, 8]),
    "موت الابنة": _ev(['H5', 'IC', 'DS', 'H8'], ['VEN', 'MOON', 'NEP', 'PLU', 'SN'], ['H12'], ['MAR', 'URA', 'MER'], [5, 8]),
    "موت الزوج": _ev(['DS', 'IC', 'H8'], ['SAT', 'SUN', 'NEP', 'PLU', 'SN', 'MAR'], ['H12', 'H5'], ['URA'], [7, 8]),
    "موت الزوجة": _ev(['DS', 'IC', 'H8'], ['MOON', 'VEN', 'SAT', 'NEP', 'PLU', 'SN', 'MAR'], ['H12', 'H5'], ['URA'], [7, 8]),
    "موت أخ": _ev(['H3', 'AS', 'IC', 'H8'], ['MER', 'MAR', 'SAT', 'NEP', 'PLU', 'SN'], ['H12'], ['MOON', 'SUN'], [3, 8]),
    "موت أخت": _ev(['H3', 'AS', 'IC', 'H8'], ['MOON', 'MER', 'VEN', 'MAR', 'SAT', 'NEP', 'PLU', 'SN'], ['H12'], [], [3, 8]),
    "ولادة ابن": _ev(['H5', 'AS', 'IC'], ['MAR', 'SUN', 'JUP', 'NN'], ['MC'], ['PLU', 'URA', 'MOON', 'VEN', 'MER'], [5, 1]),
    "ولادة ابنة": _ev(['H5', 'AS', 'IC'], ['VEN', 'MOON', 'JUP', 'NN'], ['MC'], ['MAR', 'URA', 'PLU', 'SUN', 'MER'], [5, 1]),
    "ولادة أخ أصغر": _ev(['H3', 'IC', 'DS'], ['MER', 'JUP'], [], ['SUN', 'MOON', 'VEN', 'NN', 'URA', 'PLU'], [3]),
    "ولادة أخت صغرى": _ev(['H3', 'IC', 'DS'], ['MOON', 'MER', 'VEN'], [], ['SUN', 'JUP', 'NN', 'URA', 'PLU'], [3]),
    "تاريخ الزواج/عقد القران": {
        'M': _ev(['DS', 'MC', 'H5'], ['VEN', 'MOON', 'NN', 'JUP'], ['AS'], ['MER', 'URA', 'MAR', 'SUN'], [7, 10, 5]),
        'F': _ev(['DS', 'MC', 'H5'], ['SUN', 'JUP', 'MAR', 'NN'], ['AS'], ['MER', 'URA', 'VEN', 'MOON', 'PLU'], [7, 10, 5]),
    },
    "طلاق / انفصال": _ev(['DS', 'IC'], ['MAR', 'SAT', 'NEP', 'SN', 'PLU'], ['H12'], ['MER', 'URA', 'VEN', 'MOON'], [7, 4, 12]),
    "عملية جراحية بمشفى": _ev(['AS', 'H12', 'MC'], ['MAR', 'SAT', 'NEP'], ['H6', 'H8'], ['URA', 'PLU', 'MOON'], [1, 6, 12]),
    "حادث": _ev(['H3', 'MC', 'AS'], ['MAR', 'URA', 'SAT', 'MER'], ['H12', 'H8'], ['NEP', 'SN', 'PLU', 'MOON'], [1, 3, 12]),
    "نجاح / ترقية / انتخاب": _ev(['H3', 'MC', 'AS'], ['SUN', 'JUP', 'MOON', 'MER', 'URA', 'VEN'], ['H11', 'H2'], ['NN', 'PLU'], [10, 1, 11]),
    "فشل / استقالة / تقاعد": _ev(['H3', 'MC', 'AS'], ['SAT', 'SUN', 'NEP', 'MAR', 'SN'], ['H12'], ['URA', 'MOON', 'MER', 'PLU'], [10, 6, 12]),
    "تغيير مسكن": _ev(['H3', 'IC', 'AS'], ['MER', 'MOON', 'NN', 'JUP', 'VEN', 'SUN'], ['H9'], ['URA'], [4, 3]),
    "تخرج / نشر": _ev(['H3', 'MC', 'AS'], ['MER', 'MOON', 'JUP', 'SUN', 'URA', 'VEN'], ['H9'], ['NN'], [9, 3, 10]),
    "خسارة مالية": _ev(['H2', 'AS', 'MC'], ['NEP', 'URA', 'MER', 'MAR', 'SAT'], ['H8'], ['PLU', 'SN'], [2, 8]),
    "مكسب مالي / زيادة دخل": _ev(['H2', 'H5', 'AS', 'MC'], ['JUP', 'VEN', 'URA'], ['H11'], ['PLU'], [2, 5, 11]),
    "اعتقال / سجن": _ev(['H12', 'MC', 'AS'], ['SAT', 'URA', 'NEP', 'MAR', 'PLU', 'SN'], ['H3'], ['SUN', 'MER'], [12, 1]),
}


def resolve_spec(kind: str, gender: str) -> dict:
    s = EVENT_TYPES[kind]
    if 'M' in s and 'F' in s:
        return s['M'] if gender == 'M' else s['F']
    return s


def house_cusp_key(h_num: int) -> str:
    return {1: 'AS', 4: 'IC', 7: 'DS', 10: 'MC'}.get(h_num, f'H{h_num}')


def min_allowed_event_date(birth_date: dt.date, ref_today: Optional[dt.date] = None) -> dt.date:
    """أقدم تاريخ مقبول للحدث بحيث لا يتجاوز عمر الحدث 20 سنة لتفادي تشوّه القوس."""
    today = ref_today or dt.date.today()
    cutoff = today - dt.timedelta(days=int(round(MAX_EVENT_AGE_YEARS * TROPICAL_YEAR)))
    return max(birth_date + dt.timedelta(days=1), cutoff)


def validate_event_date(event_date: dt.date, birth_date: dt.date, kind: str,
                        ref_today: Optional[dt.date] = None) -> Optional[str]:
    today = ref_today or dt.date.today()
    if event_date <= birth_date:
        return f"حدث «{kind}» بتاريخ {event_date} ليس بعد تاريخ الميلاد ({birth_date})."
    if event_date > today:
        return f"حدث «{kind}» بتاريخ {event_date} يقع في المستقبل."
    age_years = (today - event_date).days / TROPICAL_YEAR
    if age_years > MAX_EVENT_AGE_YEARS:
        return (
            f"حدث «{kind}» بتاريخ {event_date} عمره {age_years:.1f} سنة، "
            f"والنظام يقبل فقط الأحداث التي لا يتجاوز عمرها {MAX_EVENT_AGE_YEARS} سنة لتفادي تشوّه القوس."
        )
    return None


# ==============================================================================
# 2. رياضيات الكرة السماوية والتسيير التوبوسنتريك (Estadella + Polich-Page)
# ==============================================================================
def _wrap180(x):
    return (np.asarray(x, float) + 180.0) % 360.0 - 180.0


def ra_of_lon(lam, eps_deg: float):
    lam_r = np.radians(lam)
    e = math.radians(eps_deg)
    return np.degrees(np.arctan2(math.cos(e) * np.sin(lam_r), np.cos(lam_r))) % 360.0


def dec_of_lon(lam, eps_deg: float):
    return np.degrees(np.arcsin(np.clip(math.sin(math.radians(eps_deg)) * np.sin(np.radians(lam)), -1.0, 1.0)))


def mc_from_ramc(ramc, eps_deg: float):
    r = np.radians(ramc)
    return np.degrees(np.arctan2(np.sin(r), np.cos(r) * math.cos(math.radians(eps_deg)))) % 360.0


def lam_from_oa(oa_deg, phi_rad, eps_rad):
    oa = np.asarray(oa_deg, float) % 360.0
    oa_r = np.radians(oa)
    x = np.sin(eps_rad) * np.tan(phi_rad) - np.cos(eps_rad) * np.cos(oa_r)
    y = np.sin(oa_r)
    y = np.where(np.abs(y) < 1e-12, 1e-12, y)
    lam = np.degrees(np.arctan(x / y)) + np.where(oa < 180.0, 90.0, 270.0)
    return lam % 360.0


def all_cusps(ramc, lat_deg: float, eps_deg: float) -> Dict[str, np.ndarray]:
    ramc = np.asarray(ramc, float)
    e = math.radians(eps_deg)
    t = math.tan(math.radians(lat_deg))
    out: Dict[str, np.ndarray] = {}
    for name, k, tp in (('H11', 1, t / 3.0), ('H12', 2, 2.0 * t / 3.0), ('AS', 3, t),
                        ('H2', 4, 2.0 * t / 3.0), ('H3', 5, t / 3.0)):
        out[name] = lam_from_oa(ramc + 30.0 * k, math.atan(tp), e)
    out['H5'] = (out['H11'] + 180.0) % 360.0
    out['H6'] = (out['H12'] + 180.0) % 360.0
    out['DS'] = (out['AS'] + 180.0) % 360.0
    out['H8'] = (out['H2'] + 180.0) % 360.0
    out['H9'] = (out['H3'] + 180.0) % 360.0
    mc = mc_from_ramc(ramc, eps_deg)
    out['MC'] = mc
    out['IC'] = (mc + 180.0) % 360.0
    out['EP'] = lam_from_oa(ramc + 90.0, 0.0, e)
    return out


def east_point(ramc, eps_deg: float):
    return lam_from_oa(np.asarray(ramc, float) + 90.0, 0.0, math.radians(eps_deg))


def compute_arabic_lots(asc, sun, moon):
    """حساب الحيّز (نهاري/ليلي) وسهم السعادة وسهم الغيب وفق الأصول العربية."""
    rel = (np.asarray(sun, float) - np.asarray(asc, float)) % 360.0
    is_day = rel >= 180.0
    pof = np.where(is_day, (asc + moon - sun) % 360.0, (asc + sun - moon) % 360.0)
    pos = np.where(is_day, (asc + sun - moon) % 360.0, (asc + moon - sun) % 360.0)
    return is_day, pof, pos


def planet_speculum(lam, ramc, lat_deg: float, eps_deg: float):
    lat = math.radians(lat_deg)
    lam = np.asarray(lam, float)
    ramc = np.asarray(ramc, float)
    ra = ra_of_lon(lam, eps_deg)
    dec = np.radians(dec_of_lon(lam, eps_deg))
    ad = np.arcsin(np.clip(math.tan(lat) * np.tan(dec), -1.0, 1.0))
    d_mc = _wrap180(ra - ramc)
    d_ic = _wrap180(ra - (ramc + 180.0))
    above = np.abs(d_mc) <= 90.0 + np.degrees(ad)
    md = np.where(above, np.abs(d_mc), np.abs(d_ic))
    sa = np.where(above, 90.0 + np.degrees(ad), 90.0 - np.degrees(ad))
    sa = np.where(np.abs(sa) < 1e-9, 1e-9, sa)
    phi_p = np.arctan(md / sa * math.tan(lat))
    adp = np.arcsin(np.clip(np.tan(phi_p) * np.tan(dec), -1.0, 1.0))
    is_oa = np.where(above, d_mc >= 0.0, d_ic < 0.0)
    oa_od = np.where(is_oa, ra - np.degrees(adp), ra + np.degrees(adp)) % 360.0
    return phi_p, oa_od, is_oa


def direct_planet(lam, ramc, lat_deg: float, eps_deg: float, arc):
    phi_p, oa_od, is_oa = planet_speculum(lam, ramc, lat_deg, eps_deg)
    e = math.radians(eps_deg)
    eps_signed = np.where(is_oa, e, -e)
    return lam_from_oa(oa_od + arc, phi_p, eps_signed)


# ==============================================================================
# 3. الأفيمريس (Swiss Ephemeris مع دعم Moshier التلقائي للنشر السحابي)
# ==============================================================================
def _interp_grid(raw: Callable[[float], Dict[str, float]], jd: np.ndarray) -> Dict[str, np.ndarray]:
    jd = np.atleast_1d(np.asarray(jd, float))
    lo, hi = float(jd.min()), float(jd.max())
    if jd.size <= 3 or hi - lo < 1e-9:
        vals = [raw(float(j)) for j in jd]
        return {k: np.array([v[k] for v in vals]) for k in vals[0]}
    n = int(min(max((hi - lo) * 144.0 + 2, 3), 800))
    grid = np.linspace(lo, hi, n)
    vals = [raw(float(j)) for j in grid]
    out = {}
    for k in vals[0]:
        a = np.degrees(np.unwrap(np.radians([v[k] for v in vals])))
        out[k] = np.interp(jd, grid, a) % 360.0
    return out


class Ephemeris:
    def lons(self, jd) -> Dict[str, np.ndarray]:
        raise NotImplementedError

    def sun_lon_scalar(self, jd: float) -> float:
        raise NotImplementedError

    def eps(self, jd: float) -> float:
        raise NotImplementedError

    def ramc(self, jd, lon: float) -> np.ndarray:
        raise NotImplementedError


class SwissEphemeris(Ephemeris):
    _IDS = {
        'SUN': 0, 'MOON': 1, 'MER': 2, 'VEN': 3, 'MAR': 4,
        'JUP': 5, 'SAT': 6, 'URA': 7, 'NEP': 8, 'PLU': 9,
    }

    def __init__(self, ephe_path: Optional[str] = None):
        import swisseph as swe
        self.swe = swe
        has_files = bool(
            ephe_path and os.path.isdir(ephe_path) and
            any(f.endswith('.se1') for f in os.listdir(ephe_path))
        )
        if has_files and ephe_path:
            swe.set_ephe_path(ephe_path)
        self.flags = swe.FLG_SWIEPH if has_files else swe.FLG_MOSEPH

    def _raw(self, jd: float) -> Dict[str, float]:
        swe = self.swe
        out = {k: swe.calc_ut(jd, i, self.flags)[0][0] for k, i in self._IDS.items()}
        out['NN'] = swe.calc_ut(jd, swe.MEAN_NODE, self.flags)[0][0]
        out['SN'] = (out['NN'] + 180.0) % 360.0
        return out

    def lons(self, jd):
        return _interp_grid(self._raw, jd)

    def sun_lon_scalar(self, jd: float) -> float:
        return float(self.swe.calc_ut(jd, 0, self.flags)[0][0])

    def eps(self, jd: float) -> float:
        return float(self.swe.calc_ut(jd, self.swe.ECL_NUT, self.flags)[0][0])

    def ramc(self, jd, lon: float):
        jd = np.atleast_1d(np.asarray(jd, float))
        st_arr = np.array([self.swe.sidtime(float(j)) for j in jd])
        return (st_arr * 15.0 + lon) % 360.0


# ==============================================================================
# 4. بناء الخريطة الفلكية الأساسية وحساب العودة الشمسية
# ==============================================================================
def jd_from_utc(d: dt.datetime) -> float:
    return (d - dt.datetime(1970, 1, 1)).total_seconds() / 86400.0 + 2440587.5


def make_candidates(birth_date: dt.date, start_hour: int, span_hours: float, step_s: int,
                    to_utc: Callable[[dt.datetime], dt.datetime], anchor: str = 'forward'):
    start = dt.datetime.combine(birth_date, dt.time(start_hour % 24))
    if start_hour == 22 and anchor == 'backward':
        start -= dt.timedelta(days=1)
    locs = [start + dt.timedelta(seconds=s) for s in range(0, int(span_hours * 3600), int(step_s))]
    jd = np.array([jd_from_utc(to_utc(x)) for x in locs])
    return locs, jd


@dataclass
class Natal:
    jd: np.ndarray
    ramc: np.ndarray
    eps: float
    lat: float
    lon: float
    pl: Dict[str, np.ndarray]
    cusps: Dict[str, np.ndarray]
    is_day: np.ndarray
    pof: np.ndarray
    pos: np.ndarray


def build_natal(eph: Ephemeris, jd, lat: float, lon: float) -> Natal:
    jd = np.atleast_1d(np.asarray(jd, float))
    eps = eph.eps(float(jd[jd.size // 2]))
    ramc = eph.ramc(jd, lon)
    pl = eph.lons(jd)
    cusps = all_cusps(ramc, lat, eps)
    is_day, pof, pos = compute_arabic_lots(cusps['AS'], pl['SUN'], pl['MOON'])
    cusps['POF'] = pof
    cusps['POS'] = pos
    return Natal(jd, ramc, eps, lat, lon, pl, cusps, is_day, pof, pos)


def chart_points(natal: Natal, i: int = 0) -> dict:
    asc = float(natal.cusps['AS'][i])
    mc = float(natal.cusps['MC'][i])
    ep = float(natal.cusps['EP'][i])
    pof = float(natal.pof[i])
    pos = float(natal.pos[i])
    is_day = bool(natal.is_day[i])
    asc_sign = int(asc // 30) % 12
    asc_ruler = SIGN_RULERS[asc_sign]
    return dict(
        ramc=float(natal.ramc[i]),
        asc=asc,
        mc=mc,
        ep=ep,
        pof=pof,
        pos=pos,
        is_day=is_day,
        asc_ruler=asc_ruler,
        ra_ep=float((natal.ramc[i] + 90.0) % 360.0),
        cusps={k: float(v[i]) for k, v in natal.cusps.items()},
        planets={k: float(v[i]) for k, v in natal.pl.items()},
    )


def solve_solar_return_jds(eph: Ephemeris, natal_sun: np.ndarray, approx_sr_jd: np.ndarray) -> np.ndarray:
    j0 = float(approx_sr_jd.mean()) - 1.5
    j1 = float(approx_sr_jd.mean()) + 1.5
    grid = np.linspace(j0, j1, 37)
    svals = np.array([eph.sun_lon_scalar(float(g)) for g in grid])
    svals_u = np.degrees(np.unwrap(np.radians(svals)))
    base_sun = svals_u[len(svals_u) // 2]
    target_u = base_sun + _wrap180(natal_sun - (base_sun % 360.0))
    jd_sr = np.interp(target_u, svals_u, grid)
    if jd_sr.size <= 32:
        for _ in range(2):
            cur = np.array([eph.sun_lon_scalar(float(j)) for j in jd_sr])
            diff = _wrap180(natal_sun - cur)
            jd_sr = jd_sr + diff / 0.985647
    else:
        cur = eph.lons(jd_sr)['SUN']
        diff = _wrap180(natal_sun - cur)
        jd_sr = jd_sr + diff / 0.985647
    return jd_sr


# ==============================================================================
# 5. الأحداث، الأرباب التقليدية، ومحرّك التقييم السداسي
# ==============================================================================
@dataclass
class Event:
    kind: str
    jd: float
    has_time: bool = False
    weight: float = 1.0
    label: str = ''


def make_event(kind: str, date: dt.date, time: Optional[dt.time], to_utc, weight: float = 1.0) -> Event:
    t = time if time is not None else dt.time(12, 0)
    jd = jd_from_utc(to_utc(dt.datetime.combine(date, t)))
    return Event(kind, jd, time is not None, float(weight), f"{kind} — {date.isoformat()}")


@dataclass
class Hit:
    tech_code: str
    tech: str
    text: str
    orb: float
    score: float


def _aspect_matrix(lam_a, lam_b, lim_major, lim_minor, aspects):
    d = np.atleast_1d((np.asarray(lam_a, float) - np.asarray(lam_b, float)) % 360.0)
    A = np.array(aspects, float)[:, None]
    o = np.minimum(np.abs(d[None, :] - A), np.abs(d[None, :] - (360.0 - A))) * 60.0
    lim = np.where(np.isin(A, (0.0, 60.0, 90.0, 120.0, 180.0)), lim_major, lim_minor)
    ratio = np.clip(1.0 - o / lim, 0.0, None)
    w = (ratio ** 1.35) * np.array([ASPECT_W[int(a)] for a in aspects])[:, None]
    return o, w


class _TechAcc:
    def __init__(self, n: int, explain: bool):
        self.by_tech: Dict[str, np.ndarray] = {t: np.zeros(n) for t in TECH_CODES}
        self.explain = explain
        self.hits: List[Hit] = []

    def add(self, tech_code: str, desc: Tuple[str, str], lam_a, lam_b,
            factor: float, tech_w: float, lim_maj: float, lim_min: float, aspects):
        o, w = _aspect_matrix(lam_a, lam_b, lim_maj, lim_min, aspects)
        exact_boost = np.where((o <= 3.0) & (w > 0), 1.35, 1.0)
        sc = BASE_SCORE * factor * tech_w * w * exact_boost
        self.by_tech[tech_code] += sc.sum(axis=0)
        if self.explain:
            t_ar = TECH_AR[tech_code]
            for i, a in enumerate(aspects):
                if sc[i, 0] > 0:
                    self.hits.append(Hit(tech_code, t_ar, f"{desc[0]}  {a}°  {desc[1]}",
                                         float(o[i, 0]), float(sc[i, 0])))


def _lists(spec):
    sigs = [(s, 1.0) for s in spec['sig']] + [(s, 0.55) for s in spec['sig2']]
    if 'EP' not in [x[0] for x in sigs]:
        sigs.append(('EP', 0.55))
    if 'POF' not in [x[0] for x in sigs]:
        sigs.append(('POF', 0.6))
    pls = [(p, 1.0) for p in spec['pl']] + [(p, 0.55) for p in spec['pl2']]
    return sigs, pls


def _run_pd(acc: _TechAcc, natal: Natal, spec: dict, days: np.ndarray):
    sigs, pls = _lists(spec)
    A = days * NAIBOD_PER_DAY
    for sgn, dlab in ((1, 'مباشر'), (-1, 'عكسي')):
        arc = sgn * A
        dc = all_cusps(natal.ramc + arc, natal.lat, natal.eps)
        dc['POF'] = (natal.pof + arc) % 360.0
        for s, fs in sigs:
            for p, fp in pls:
                acc.add('PD', (f"{FACTOR_AR.get(s, s)} ({dlab})", PLANET_AR[p]),
                        dc[s], natal.pl[p], fs * fp, 1.0, PD_ORB_MAJOR, PD_ORB_MINOR, ASPECTS)
        for p, fp in pls:
            ld = direct_planet(natal.pl[p], natal.ramc, natal.lat, natal.eps, arc)
            for s, fs in sigs:
                acc.add('PD', (f"{PLANET_AR[p]} ({dlab})", FACTOR_AR.get(s, s)),
                        ld, natal.cusps[s], fs * fp, 0.85, PD_ORB_MAJOR, PD_ORB_MINOR, ASPECTS)


def _run_sa(eph: Ephemeris, acc: _TechAcc, natal: Natal, spec: dict, days: np.ndarray):
    sigs, pls = _lists(spec)
    yrs = days / TROPICAL_YEAR
    sun_p = eph.lons(natal.jd + yrs)['SUN']
    sa_base = (sun_p - natal.pl['SUN']) % 360.0
    for sgn, dlab in ((1, '+قوس'), (-1, '-قوس')):
        sa = sgn * sa_base
        w_dir = 0.65 if sgn == 1 else 0.45
        for s, fs in sigs:
            for p, fp in pls:
                acc.add('SA', (f"{FACTOR_AR.get(s, s)} ({dlab})", PLANET_AR[p]),
                        natal.cusps[s] + sa, natal.pl[p], fs * fp, w_dir, SA_ORB_MAJOR, SA_ORB_MINOR, ASPECTS)
                acc.add('SA', (f"{PLANET_AR[p]} ({dlab})", FACTOR_AR.get(s, s)),
                        natal.pl[p] + sa, natal.cusps[s], fs * fp, w_dir * 0.85, SA_ORB_MAJOR, SA_ORB_MINOR, ASPECTS)


def _sec_limits(p: str) -> Tuple[float, float]:
    return SEC_ORB_MOON if p == 'MOON' else (SEC_ORB[p], SEC_ORB[p])


def _run_sd(eph: Ephemeris, acc: _TechAcc, natal: Natal, spec: dict, days: np.ndarray):
    sigs, pls = _lists(spec)
    yrs = days / TROPICAL_YEAR
    sun0 = ra_of_lon(natal.pl['SUN'], natal.eps)
    for jdx, lab, tw in ((natal.jd + yrs, 'تقدمي', 0.85), (natal.jd - yrs, 'تراجعي', 0.6)):
        pl = eph.lons(jdx)
        arc = _wrap180(ra_of_lon(pl['SUN'], natal.eps) - sun0)
        dc = all_cusps(natal.ramc + arc, natal.lat, natal.eps)
        _, pof_p, _ = compute_arabic_lots(dc['AS'], pl['SUN'], pl['MOON'])
        dc['POF'] = pof_p
        for p, fp in pls:
            lmj, lmn = _sec_limits(p)
            for s, fs in sigs:
                acc.add('SD', (f"{FACTOR_AR.get(s, s)} ({lab})", PLANET_AR[p]),
                        dc[s], natal.pl[p], fs * fp, tw, lmj, lmn, ASPECTS)
                acc.add('SD', (f"{PLANET_AR[p]} ({lab})", FACTOR_AR.get(s, s)),
                        pl[p], natal.cusps[s], fs * fp, tw * 0.9, lmj, lmn, ASPECTS)
        if 'MOON' not in [x[0] for x in pls]:
            for s, fs in sigs[:3]:
                acc.add('SD', (f"القمر التقدمي ({lab})", FACTOR_AR.get(s, s)),
                        pl['MOON'], natal.cusps[s], fs * 0.7, tw * 0.85, SEC_ORB_MOON[0], SEC_ORB_MOON[1], ASPECTS)


def _run_ap(eph: Ephemeris, acc: _TechAcc, natal: Natal, ev: Event, spec: dict, days: np.ndarray):
    sigs, pls = _lists(spec)
    years_exact = days / TROPICAL_YEAR
    age_int = np.floor(years_exact).astype(int)
    prof_arc_yr = (years_exact * 30.0) % 360.0
    frac_yr = years_exact - age_int
    prof_arc_mo = ((age_int * 30.0) + (frac_yr * 360.0)) % 360.0

    prof_as = (natal.cusps['AS'] + prof_arc_yr) % 360.0
    prof_mc = (natal.cusps['MC'] + prof_arc_yr) % 360.0
    prof_pof = (natal.pof + prof_arc_yr) % 360.0
    prof_as_mo = (natal.cusps['AS'] + prof_arc_mo) % 360.0

    pl_tr = eph.lons(np.array([ev.jd]))

    for p, fp in pls:
        acc.add('AP', ("انتهاء الطالع السنوي", f"{PLANET_AR[p]} أصلي"),
                prof_as, natal.pl[p], fp, 0.85, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
        acc.add('AP', ("انتهاء العاشر السنوي", f"{PLANET_AR[p]} أصلي"),
                prof_mc, natal.pl[p], fp, 0.75, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
        acc.add('AP', ("انتهاء سهم السعادة", f"{PLANET_AR[p]} أصلي"),
                prof_pof, natal.pl[p], fp, 0.65, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
        if not (p == 'MOON' and not ev.has_time):
            acc.add('AP', ("انتهاء الطالع السنوي", f"{PLANET_AR[p]} عابر"),
                    prof_as, pl_tr[p], fp, 0.7, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
            acc.add('AP', ("انتهاء الطالع الشهري", f"{PLANET_AR[p]} عابر"),
                    prof_as_mo, pl_tr[p], fp, 0.55, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)

    asc_signs = (np.floor(natal.cusps['AS'] / 30.0).astype(int)) % 12
    prof_signs = (asc_signs + age_int) % 12
    ev_houses = spec.get('houses', [1])
    h_key = house_cusp_key(ev_houses[0]) if ev_houses else 'AS'
    ev_house_signs = (np.floor(natal.cusps[h_key] / 30.0).astype(int)) % 12

    n = natal.jd.size
    lord_year_lon = np.zeros(n)
    lord_year_tr = np.zeros(n)
    lord_ev_lon = np.zeros(n)
    lord_ev_tr = np.zeros(n)

    for p_code in ['MAR', 'VEN', 'MER', 'MOON', 'SUN', 'JUP', 'SAT']:
        mask_y = np.array([SIGN_RULERS[int(s)] == p_code for s in prof_signs])
        if mask_y.any():
            lord_year_lon[mask_y] = natal.pl[p_code][mask_y]
            lord_year_tr[mask_y] = pl_tr[p_code][0]
        mask_e = np.array([SIGN_RULERS[int(s)] == p_code for s in ev_house_signs])
        if mask_e.any():
            lord_ev_lon[mask_e] = natal.pl[p_code][mask_e]
            lord_ev_tr[mask_e] = pl_tr[p_code][0]

    acc.add('AP', ("رب السنة عابر", "الطالع AS"), lord_year_tr, natal.cusps['AS'], 1.0, 0.85, TR_ORB, TR_ORB, MAJOR_ASPECTS)
    acc.add('AP', ("رب السنة عابر", "وتد السماء MC"), lord_year_tr, natal.cusps['MC'], 1.0, 0.75, TR_ORB, TR_ORB, MAJOR_ASPECTS)
    acc.add('AP', ("رب بيت الحدث عابر", "الطالع AS"), lord_ev_tr, natal.cusps['AS'], 1.0, 0.80, TR_ORB, TR_ORB, MAJOR_ASPECTS)
    acc.add('AP', ("رب بيت الحدث عابر", "وتد السماء MC"), lord_ev_tr, natal.cusps['MC'], 1.0, 0.70, TR_ORB, TR_ORB, MAJOR_ASPECTS)
    acc.add('AP', ("انتهاء الطالع السنوي", "رب السنة أصلي"), prof_as, lord_year_lon, 1.0, 0.90, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
    acc.add('AP', ("انتهاء الطالع السنوي", "رب بيت الحدث أصلي"), prof_as, lord_ev_lon, 1.0, 0.80, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)


def _run_tr(eph: Ephemeris, acc: _TechAcc, natal: Natal, ev: Event, spec: dict):
    sigs, pls = _lists(spec)
    pl_dir = eph.lons(np.array([ev.jd]))
    pl_pre = eph.lons(2.0 * natal.jd - ev.jd)
    for lab, pl, tw in (('مباشر', pl_dir, 0.65), ('ما قبل الولادة', pl_pre, 0.5)):
        for p, fp in pls:
            if p == 'MOON' and not ev.has_time:
                continue
            for s, fs in sigs:
                acc.add('TR', (f"{PLANET_AR[p]} عابر ({lab})", FACTOR_AR.get(s, s)),
                        pl[p], natal.cusps[s], fs * fp, tw, TR_ORB, TR_ORB, MAJOR_ASPECTS)


def _run_sr(eph: Ephemeris, acc: _TechAcc, natal: Natal, ev: Event, spec: dict):
    sigs, pls = _lists(spec)
    years = (ev.jd - natal.jd) / TROPICAL_YEAR
    sr_year = np.floor(years)
    approx_sr_jd = natal.jd + sr_year * TROPICAL_YEAR
    jd_sr = solve_solar_return_jds(eph, natal.pl['SUN'], approx_sr_jd)

    eps_sr = eph.eps(float(jd_sr[jd_sr.size // 2]))
    ramc_sr = eph.ramc(jd_sr, natal.lon)
    cusps_sr = all_cusps(ramc_sr, natal.lat, eps_sr)
    pl_sr = eph.lons(jd_sr)
    _, pof_sr, _ = compute_arabic_lots(cusps_sr['AS'], pl_sr['SUN'], pl_sr['MOON'])
    cusps_sr['POF'] = pof_sr

    for sr_ang in ('AS', 'MC', 'DS', 'IC', 'POF'):
        for nat_s, fs in sigs[:4]:
            acc.add('SR', (f"{FACTOR_AR[sr_ang]} عودة شمسية", f"{FACTOR_AR.get(nat_s, nat_s)} أصلي"),
                    cusps_sr[sr_ang], natal.cusps[nat_s], fs, 0.95, SR_ORB_MAJOR, SR_ORB_MINOR, MAJOR_ASPECTS)
        for p, fp in pls:
            acc.add('SR', (f"{FACTOR_AR[sr_ang]} عودة شمسية", f"{PLANET_AR[p]} أصلي"),
                    cusps_sr[sr_ang], natal.pl[p], fp, 0.85, SR_ORB_MAJOR, SR_ORB_MINOR, ASPECTS)

    for p, fp in pls:
        for nat_s, fs in sigs[:4]:
            acc.add('SR', (f"{PLANET_AR[p]} في العودة", f"{FACTOR_AR.get(nat_s, nat_s)} أصلي"),
                    pl_sr[p], natal.cusps[nat_s], fs * fp, 0.75, SR_ORB_MAJOR, SR_ORB_MINOR, MAJOR_ASPECTS)
    if 'MOON' not in [x[0] for x in pls]:
        for nat_s, fs in sigs[:3]:
            acc.add('SR', ("قمر العودة الشمسية", f"{FACTOR_AR.get(nat_s, nat_s)} أصلي"),
                    pl_sr['MOON'], natal.cusps[nat_s], fs * 0.7, 0.7, SR_ORB_MAJOR, SR_ORB_MINOR, MAJOR_ASPECTS)


def score_events(eph: Ephemeris, natal: Natal, events: Sequence[Event], gender: str,
                 explain: bool = False, techniques: Sequence[str] = TECH_CODES):
    n = natal.jd.size
    total = np.zeros(n)
    tech_totals: Dict[str, np.ndarray] = {t: np.zeros(n) for t in TECH_CODES}
    detail = []

    for ev in events:
        spec = resolve_spec(ev.kind, gender)
        acc = _TechAcc(n, explain)
        days = ev.jd - natal.jd
        if 'PD' in techniques:
            _run_pd(acc, natal, spec, days)
        if 'SA' in techniques:
            _run_sa(eph, acc, natal, spec, days)
        if 'SD' in techniques:
            _run_sd(eph, acc, natal, spec, days)
        if 'AP' in techniques:
            _run_ap(eph, acc, natal, ev, spec, days)
        if 'TR' in techniques:
            _run_tr(eph, acc, natal, ev, spec)
        if 'SR' in techniques:
            _run_sr(eph, acc, natal, ev, spec)

        raw_ev = np.zeros(n)
        active_count = np.zeros(n)
        for t in techniques:
            t_sc = acc.by_tech[t]
            raw_ev += t_sc
            tech_totals[t] += ev.weight * t_sc
            active_count += (t_sc >= 2.0).astype(float)

        convergence_mult = 1.0 + 0.22 * np.maximum(0.0, active_count - 1.0)
        total += ev.weight * raw_ev * convergence_mult

        if explain:
            detail.append((ev, sorted(acc.hits, key=lambda h: -h.score)))

    return total, detail, tech_totals


# ==============================================================================
# 6. البحث متعدد المراحل بدقة 1 ثانية (Coarse-to-Fine Rectification)
# ==============================================================================
def _peaks(score: np.ndarray, step_s: int, n: int, exclusion_s: int = 150):
    s = score.copy()
    ex = max(1, int(exclusion_s / step_s))
    out = []
    for _ in range(n):
        i = int(np.argmax(s))
        if s[i] <= 0:
            break
        out.append(i)
        s[max(0, i - ex): i + ex + 1] = -1.0
    return out


def _plateau_s(score: np.ndarray, i: int, step_s: int, frac: float = 0.90) -> int:
    thr = score[i] * frac
    l = r = i
    while l > 0 and score[l - 1] >= thr:
        l -= 1
    while r < len(score) - 1 and score[r + 1] >= thr:
        r += 1
    return (r - l + 1) * step_s


def format_lon_short(lam: float) -> str:
    lam = lam % 360.0
    deg = lam % 30.0
    d = int(deg)
    m = int((deg - d) * 60)
    if m == 60:
        m = 0
        d += 1
    return f"{d}°{m:02d}′"


def describe_lon(lam: float) -> str:
    lam = lam % 360.0
    sign_idx = int(lam // 30) % 12
    deg = lam % 30.0
    d = int(deg)
    m = int((deg - d) * 60)
    s = int(round(((deg - d) * 60 - m) * 60))
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    if d >= 30:
        d = 0
        sign_idx = (sign_idx + 1) % 12
    return f"{d}°{m:02d}′{s:02d}″ {SIGNS_AR[sign_idx]}"


def rectify(eph: Ephemeris, birth_date: dt.date, lat: float, lon: float,
            to_utc: Callable[[dt.datetime], dt.datetime], events: Sequence[Event], gender: str,
            start_hour: int, span_hours: float = 3.0, step_s: int = 6, anchor: str = 'forward',
            techniques: Sequence[str] = TECH_CODES, n_peaks: int = 5,
            null_runs: int = 0, seed: int = 7) -> dict:
    locs, jd = make_candidates(birth_date, start_hour, span_hours, step_s, to_utc, anchor)
    natal = build_natal(eph, jd, lat, lon)
    score, _, tech_totals = score_events(eph, natal, events, gender, False, techniques)
    coarse_peaks = _peaks(score, step_s, max(n_peaks * 2, 10))

    results = []
    seen_times = set()
    for i in coarse_peaks:
        half_win = max(step_s * 2, 16)
        fl = [locs[i] + dt.timedelta(seconds=k) for k in range(-half_win, half_win + 1)]
        fjd = np.array([jd_from_utc(to_utc(x)) for x in fl])
        fn = build_natal(eph, fjd, lat, lon)
        fs_, _, _ = score_events(eph, fn, events, gender, False, techniques)
        j = int(np.argmax(fs_))
        best_time = fl[j]
        if any(abs((best_time - st_t).total_seconds()) < 90 for st_t in seen_times):
            continue
        seen_times.add(best_time)

        plateau = _plateau_s(fs_, j, 1, frac=0.90)
        n1 = build_natal(eph, fjd[j:j + 1], lat, lon)
        _, detail, t1 = score_events(eph, n1, events, gender, True, techniques)
        pts = chart_points(n1)

        tech_breakdown = {t: float(t1[t][0]) for t in techniques}
        active_techs = sum(1 for v in tech_breakdown.values() if v >= 2.0)

        first_ev_yrs = (events[0].jd - float(fjd[j])) / TROPICAL_YEAR
        asc_sign = int(pts['asc'] // 30) % 12
        prof_sign = (asc_sign + int(math.floor(first_ev_yrs))) % 12
        lord_of_year = SIGN_RULERS[prof_sign]

        results.append(dict(
            time=best_time,
            jd=float(fjd[j]),
            score=float(fs_[j]),
            plateau_s=plateau,
            points=pts,
            detail=detail,
            tech_breakdown=tech_breakdown,
            active_techs=active_techs,
            total_techs=len(techniques),
            prof_sign=SIGNS_AR[prof_sign],
            lord_of_year=PLANET_AR[lord_of_year],
        ))

    results.sort(key=lambda r: -r['score'])
    results = results[:n_peaks]

    out = dict(
        candidates=results,
        n_candidates=len(locs),
        step_s=step_s,
        scores=score,
        times=locs,
        tech_totals=tech_totals,
        null=None,
    )

    if null_runs > 0 and results:
        rng = random.Random(seed)
        real_max = float(score.max())
        null_max = []
        for _ in range(null_runs):
            shifted = []
            for ev in events:
                off = rng.choice((-1, 1)) * rng.uniform(1.5, 7.0) * TROPICAL_YEAR
                if ev.jd + off - float(jd.max()) < 365.0:
                    off = abs(off)
                shifted.append(replace(ev, jd=ev.jd + off))
            sc, _, _ = score_events(eph, natal, shifted, gender, False, techniques)
            null_max.append(float(sc.max()))
        p = (1 + sum(m >= real_max for m in null_max)) / (null_runs + 1)
        out['null'] = dict(
            p=p, real=real_max,
            null_mean=float(np.mean(null_max)),
            null_p95=float(np.percentile(null_max, 95)),
            runs=null_runs,
        )
    return out


# ==============================================================================
# 7. مولّد رسم دائرة الزودياك الاحترافي الدقيق (SVG) والتقرير المطبوع
# ==============================================================================
def build_zodiac_svg(pts: dict, birth_time: dt.datetime, name: str,
                     city_str: str, selected_country: str) -> str:
    """
    توليد رسم فلكي متجهي (SVG) عالي الدقة لدائرة الزودياك:
    - البروج الاثني عشر بتدريجات كل 5° و 10° وأسماء البروج ورموزها
    - الأوتاد والبيوت التوبوسنتريك الاثني عشر مع درجاتها الدقيقة
    - الطالع الفلكي الحقيقي (AS) ودرجته بالثانية ووتد السماء (MC)
    - الكواكب الاثني عشر + النقطة الشرقية (EP) + سهم السعادة (POF) + سهم الغيب (POS)
    """
    size = 760
    cx = cy = size / 2.0
    r_outer = 340.0
    r_ticks = 322.0
    r_zodiac = 286.0
    r_planet_lbl = 248.0
    r_planet_glyph = 220.0
    r_houses = 188.0
    r_cusp_lbl = 166.0
    r_inner = 104.0

    asc = float(pts["asc"])
    mc = float(pts["mc"])
    cusps = pts["cusps"]
    planets = pts["planets"]

    def svg_rad(ecl_lon: float) -> float:
        deg_from_asc = (ecl_lon - asc) % 360.0
        return math.radians(180.0 + deg_from_asc)

    def polar(r: float, rad: float) -> Tuple[float, float]:
        return cx + r * math.cos(rad), cy - r * math.sin(rad)

    parts: List[str] = [
        f'<svg viewBox="0 0 {size} {size}" width="100%" style="max-width:740px; height:auto; display:block; margin:auto;" xmlns="http://www.w3.org/2000/svg">',
        '<defs>',
        '<radialGradient id="chartBg" cx="50%" cy="50%" r="50%">',
        '<stop offset="0%" stop-color="#0f172a"/>',
        '<stop offset="100%" stop-color="#050811"/>',
        '</radialGradient>',
        '</defs>',
        f'<rect x="0" y="0" width="{size}" height="{size}" rx="16" fill="url(#chartBg)"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="#070b14" stroke="#334155" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r_ticks}" fill="none" stroke="#1e293b" stroke-width="1"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r_zodiac}" fill="none" stroke="#475569" stroke-width="1.6"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r_houses}" fill="none" stroke="#1e293b" stroke-width="1.2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="#0b1120" stroke="#475569" stroke-width="1.5"/>',
    ]

    # تدريجات البروج كل 5 درجات
    for deg in range(0, 360, 5):
        rad = svg_rad(deg)
        is_sign = (deg % 30 == 0)
        is_ten = (deg % 10 == 0)
        r_start = r_zodiac if is_sign else (r_ticks if is_ten else r_ticks + 8)
        r_end = r_outer if is_sign else r_outer
        x1, y1 = polar(r_start, rad)
        x2, y2 = polar(r_end, rad)
        stroke = "#64748b" if is_sign else ("#475569" if is_ten else "#1e293b")
        sw = "1.5" if is_sign else "0.9"
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"/>')

    # أسماء البروج ورموزها
    for idx, s_name in enumerate(SIGNS_AR):
        mid_rad = svg_rad(idx * 30.0 + 15.0)
        gx, gy = polar((r_zodiac + r_ticks) / 2.0 - 2.0, mid_rad)
        nx, ny = polar((r_outer + r_ticks) / 2.0, mid_rad)
        parts.append(
            f'<text x="{gx:.1f}" y="{gy + 5:.1f}" text-anchor="middle" fill="#f8fafc" font-size="16" font-weight="700">{SIGN_GLYPHS[idx]}</text>'
        )
        parts.append(
            f'<text x="{nx:.1f}" y="{ny + 3.5:.1f}" text-anchor="middle" fill="#94a3b8" font-size="9.5" font-weight="600">{s_name}</text>'
        )

    # خطوط البيوت الاثني عشر ودرجاتها الدقيقة
    cusp_defs = [
        ('AS', 'I · الطالع', True), ('H2', 'II', False), ('H3', 'III', False),
        ('IC', 'IV · وتد الأرض', True), ('H5', 'V', False), ('H6', 'VI', False),
        ('DS', 'VII · الغارب', True), ('H8', 'VIII', False), ('H9', 'IX', False),
        ('MC', 'X · السماء', True), ('H11', 'XI', False), ('H12', 'XII', False),
    ]
    for key, lbl, major in cusp_defs:
        lon = float(cusps[key])
        rad = svg_rad(lon)
        x1, y1 = polar(r_inner, rad)
        x2, y2 = polar(r_zodiac, rad)
        color = "#f59e0b" if major else "#334155"
        sw = "2.2" if major else "1.0"
        dash = "" if major else 'stroke-dasharray="3 3"'
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{sw}" {dash}/>')

        # تسمية البيت والدرجة
        lx, ly = polar(r_cusp_lbl, rad + 0.085)
        deg_txt = format_lon_short(lon)
        tcol = "#fcd34d" if major else "#94a3b8"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" fill="{tcol}" font-size="9.5" font-weight="700">{lbl}</text>'
        )
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + 11:.1f}" text-anchor="middle" fill="#cbd5e1" font-size="8.5" font-family="monospace">{deg_txt}</text>'
        )

    # سهم بارز على خط الطالع الحقيقي
    ax1, ay1 = polar(r_zodiac + 4, svg_rad(asc))
    ax2, ay2 = polar(r_zodiac - 18, svg_rad(asc))
    parts.append(f'<circle cx="{ax1:.1f}" cy="{ay1:.1f}" r="5" fill="#f59e0b"/>')
    parts.append(f'<line x1="{ax1:.1f}" y1="{ay1:.1f}" x2="{ax2:.1f}" y2="{ay2:.1f}" stroke="#fbbf24" stroke-width="3"/>')

    # الكواكب + النقطة الشرقية + سهم السعادة مع منع التداخل
    bodies: List[Tuple[str, float, str, str]] = [
        (PLANET_GLYPH[p], float(planets[p]), format_lon_short(planets[p]), "#38bdf8") for p in PLANETS
    ]
    bodies.append(("EP", float(pts["ep"]), format_lon_short(pts["ep"]), "#a78bfa"))
    bodies.append(("⊗", float(pts["pof"]), format_lon_short(pts["pof"]), "#34d399"))
    bodies.append(("◈", float(pts["pos"]), format_lon_short(pts["pos"]), "#f472b6"))

    bodies.sort(key=lambda item: item[1])
    disp_angles: List[float] = []
    for idx, (_, lon, _, _) in enumerate(bodies):
        d = lon
        if idx > 0 and (d - disp_angles[-1]) < 9.5:
            d = disp_angles[-1] + 9.5
        disp_angles.append(d)

    for (glyph, true_lon, deg_str, col), disp_lon in zip(bodies, disp_angles):
        t_rad = svg_rad(true_lon)
        d_rad = svg_rad(disp_lon)
        tx1, ty1 = polar(r_zodiac, t_rad)
        tx2, ty2 = polar(r_zodiac - 9, t_rad)
        gx, gy = polar(r_planet_glyph, d_rad)
        dx, dy = polar(r_planet_lbl, d_rad)
        parts.append(f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="{col}" stroke-width="1.6"/>')
        parts.append(f'<line x1="{tx2:.1f}" y1="{ty2:.1f}" x2="{gx:.1f}" y2="{gy:.1f}" stroke="{col}" stroke-opacity="0.35" stroke-width="0.9"/>')
        parts.append(f'<text x="{gx:.1f}" y="{gy + 5:.1f}" text-anchor="middle" fill="{col}" font-size="16" font-weight="700">{glyph}</text>')
        parts.append(f'<text x="{dx:.1f}" y="{dy + 3:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="8.5" font-family="monospace">{deg_str}</text>')

    # المركز: ساعة الميلاد بالثانية والطالع الحقيقي والدرجة بدقة
    asc_str = describe_lon(asc)
    mc_str = describe_lon(mc)
    sect_txt = "نهاري" if pts["is_day"] else "ليلي"
    parts.extend([
        f'<text x="{cx}" y="{cy - 44}" text-anchor="middle" fill="#94a3b8" font-size="10.5" font-weight="600">{name} · {selected_country} / {city_str}</text>',
        f'<text x="{cx}" y="{cy - 22}" text-anchor="middle" fill="#cbd5e1" font-size="11" font-family="monospace">{birth_time.strftime("%Y-%m-%d")}</text>',
        f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" fill="#fbbf24" font-size="22" font-weight="800" font-family="monospace">{birth_time.strftime("%H:%M:%S")}</text>',
        f'<text x="{cx}" y="{cy + 25}" text-anchor="middle" fill="#fde68a" font-size="10.5" font-weight="700">الطالع: {asc_str}</text>',
        f'<text x="{cx}" y="{cy + 42}" text-anchor="middle" fill="#67e8f9" font-size="10" font-weight="600">MC: {mc_str}</text>',
        f'<text x="{cx}" y="{cy + 59}" text-anchor="middle" fill="#94a3b8" font-size="9.5">الحيّز: {sect_txt} · RAMC {pts["ramc"]:.2f}°</text>',
        '</svg>',
    ])
    return "\n".join(parts)


def generate_html_report(name: str, gender_ar: str, birth_date: dt.date,
                         win_label: str, selected_country: str, city_str: str,
                         lat: float, lon: float, tz_str: str,
                         events_rows: pd.DataFrame, res: dict, cands: list) -> str:
    top = cands[0]
    pts = top["points"]
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sect_ar = "نهاري" if pts["is_day"] else "ليلي"
    zodiac_svg = build_zodiac_svg(pts, top["time"], name, city_str, selected_country)

    cands_rows_html = ""
    for i, c in enumerate(cands):
        cands_rows_html += f"""
        <tr>
            <td style="text-align:center; font-weight:bold;">{i + 1}</td>
            <td style="text-align:center; direction:ltr; font-family:monospace;">{c['time'].strftime('%Y-%m-%d %H:%M:%S')}</td>
            <td style="text-align:center; font-weight:bold;">{round(c['score'], 1)}</td>
            <td style="text-align:center;">{c['active_techs']} / {c['total_techs']}</td>
            <td style="text-align:center;">{describe_lon(c['points']['asc'])}</td>
            <td style="text-align:center;">{describe_lon(c['points']['mc'])}</td>
            <td style="text-align:center;">{describe_lon(c['points']['pof'])}</td>
            <td style="text-align:center;">{c['plateau_s']} ث</td>
        </tr>
        """

    tech_rows_html = ""
    for tc, val in top["tech_breakdown"].items():
        tech_rows_html += f"""
        <tr>
            <td style="font-weight:bold;">{TECH_AR.get(tc, tc)}</td>
            <td style="text-align:center; font-weight:bold;">{val:.1f}</td>
        </tr>
        """

    planets_rows_html = ""
    for p in PLANETS:
        planets_rows_html += f"""
        <tr>
            <td><b>{PLANET_GLYPH[p]} {PLANET_AR[p]}</b></td>
            <td style="text-align:center; direction:ltr; font-family:monospace;">{describe_lon(pts['planets'][p])}</td>
        </tr>
        """

    ev_rows_html = ""
    for _, r in events_rows.iterrows():
        d_val = r["التاريخ"].strftime("%Y-%m-%d") if hasattr(r["التاريخ"], "strftime") else str(r["التاريخ"])
        t_val = str(r["الساعة (اختياري)"]) if pd.notna(r["الساعة (اختياري)"]) else "غير محدد"
        w_val = r["الوزن"] if pd.notna(r["الوزن"]) else 1.0
        ev_rows_html += f"""
        <tr>
            <td style="font-weight:bold;">{r['نوع الحدث']}</td>
            <td style="text-align:center;">{d_val}</td>
            <td style="text-align:center;">{t_val}</td>
            <td style="text-align:center;">{w_val}</td>
        </tr>
        """

    detail_html = ""
    for ev, hits in top["detail"]:
        detail_html += f"""
        <div style="margin-top:15px; border:1px solid #dcdcdc; border-radius:8px; padding:12px; background:#fafafa; page-break-inside:avoid;">
            <h4 style="margin:0 0 8px 0; color:#111;">{ev.label} — ({len(hits)} تطابق عبر الخرائط الست)</h4>
        """
        if not hits:
            detail_html += "<p style='color:#777; margin:4px 0;'>لا تطابقات ضمن السماحيات لهذا الحدث عند هذا الوقت.</p>"
        else:
            detail_html += "<ul style='margin:4px 0; padding-right:20px;'>"
            for h in hits[:24]:
                detail_html += f"<li><b>[{h.tech}]</b> {h.text} — فارق: <b>{h.orb:.1f}′</b> — نقاط: <b>{h.score:.1f}</b></li>"
            detail_html += "</ul>"
        detail_html += "</div>"

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>{APP_TITLE} - {name}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
        body {{ font-family: 'Cairo', Tahoma, sans-serif; background:#f1f5f9; color:#0f172a; padding:24px; direction:rtl; text-align:right; }}
        .card {{ max-width:980px; margin:auto; background:#fff; padding:34px; border-radius:14px; border:1px solid #cbd5e1; }}
        .header {{ border-bottom:3px solid #0f172a; padding-bottom:14px; margin-bottom:22px; display:flex; justify-content:space-between; align-items:center; gap:16px; }}
        .btn-print {{ background:#0f172a; color:#fff; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-family:'Cairo', sans-serif; font-weight:700; }}
        table {{ width:100%; border-collapse:collapse; margin:12px 0 22px 0; font-size:14px; }}
        th, td {{ border:1px solid #cbd5e1; padding:9px 11px; }}
        th {{ background:#0f172a; color:#fff; }}
        .box {{ background:#0f172a; color:#fff; padding:22px; border-radius:10px; text-align:center; margin:18px 0; }}
        .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:14px; }}
        .cell {{ background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.22); border-radius:8px; padding:10px; }}
        .wheel-wrap {{ margin:20px 0; text-align:center; page-break-inside:avoid; }}
        @media print {{
            body {{ background:#fff; padding:0; }}
            .card {{ border:none; padding:0; max-width:100%; }}
            .no-print {{ display:none !important; }}
            th {{ background:#0f172a !important; color:#fff !important; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
        }}
    </style>
</head>
<body>
<div class="card">
    <div class="header">
        <div>
            <h1 style="margin:0; font-size:22px;">{APP_TITLE}</h1>
            <p style="margin:6px 0 0 0; color:#475569; font-size:13px;">تاريخ التقرير: {now_str} | التوافق السداسي: <b>{top['active_techs']} / {top['total_techs']} خرائط</b></p>
        </div>
        <div class="no-print">
            <button onclick="window.print()" class="btn-print">طباعة / حفظ PDF</button>
        </div>
    </div>

    <div class="box">
        <div style="font-size:14px; color:#cbd5e1;">ساعة الميلاد المصححة (بالساعة والدقيقة والثانية)</div>
        <h2 style="margin:6px 0; font-size:32px; direction:ltr; font-family:monospace; color:#fbbf24;">{top['time'].strftime('%H:%M:%S')}</h2>
        <div style="font-size:14px; color:#e2e8f0; direction:ltr;">{top['time'].strftime('%Y-%m-%d')}</div>
        <div class="grid">
            <div class="cell"><div style="font-size:12px;color:#cbd5e1;">الطالع الفلكي الحقيقي</div><div><b>{describe_lon(pts['asc'])}</b></div></div>
            <div class="cell"><div style="font-size:12px;color:#cbd5e1;">وتد السماء MC</div><div><b>{describe_lon(pts['mc'])}</b></div></div>
            <div class="cell"><div style="font-size:12px;color:#cbd5e1;">النقطة الشرقية EP</div><div><b>{describe_lon(pts['ep'])}</b></div></div>
            <div class="cell"><div style="font-size:12px;color:#cbd5e1;">سهم السعادة · رب السنة</div><div><b>{describe_lon(pts['pof'])} · {top['lord_of_year']}</b></div></div>
        </div>
    </div>

    <h3>بيانات الميلاد المُدخلة</h3>
    <table>
        <tr><th style="width:22%;">الاسم</th><td>{name}</td><th style="width:22%;">الجنس</th><td>{gender_ar}</td></tr>
        <tr><th>تاريخ الميلاد</th><td>{birth_date}</td><th>النطاق الزمني التقريبي</th><td>{win_label}</td></tr>
        <tr><th>الدولة</th><td>{selected_country}</td><th>المدينة</th><td>{city_str}</td></tr>
        <tr><th>المنطقة الزمنية</th><td>{tz_str}</td><th>الإحداثيات الجغرافية</th><td>خط العرض {lat:.4f} | خط الطول {lon:.4f}</td></tr>
        <tr><th>الحيّز الفلكي</th><td>{sect_ar}</td><th>رب الطالع وبرج الانتهاء</th><td>{PLANET_AR[pts['asc_ruler']]} · {top['prof_sign']}</td></tr>
    </table>

    <div class="wheel-wrap">
        <h3 style="text-align:right;">رسم دائرة الزودياك والبيوت التوبوسنتريك الدقيقة</h3>
        {zodiac_svg}
    </div>

    <h3>مواضع الكواكب والنقاط الفلكية لوقت الميلاد المصحح</h3>
    <table><thead><tr><th>الكوكب / النقطة</th><th>الدرجة والبرج</th></tr></thead><tbody>{planets_rows_html}</tbody></table>

    <h3>الحدث الماضي المعتمد (حدث واحد فقط — بحد أقصى 20 سنة)</h3>
    <table><thead><tr><th>نوع الحدث</th><th>التاريخ</th><th>الساعة</th><th>الوزن</th></tr></thead><tbody>{ev_rows_html}</tbody></table>

    <h3>توزيع نقاط الخرائط الست للمرشح الأول</h3>
    <table><thead><tr><th>الخريطة الفلكية</th><th>النقاط</th></tr></thead><tbody>{tech_rows_html}</tbody></table>

    <h3>قائمة المرشحين الأعلى توافقًا (مصقولون بدقة 1 ثانية)</h3>
    <table><thead><tr><th>الترتيب</th><th>الوقت المحلي</th><th>النقاط</th><th>التوافق</th><th>الطالع</th><th>MC</th><th>سهم السعادة</th><th>الهضبة</th></tr></thead><tbody>{cands_rows_html}</tbody></table>

    <h3>تفصيل التطابقات الفلكية للمرشح الأول</h3>
    {detail_html}
</div>
</body>
</html>"""


# ==============================================================================
# 8. تطبيق Streamlit الموحّد الجاهز للنشر على Streamlit Community Cloud
# ==============================================================================
CUSTOM_UI_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap');
html, body, .stApp {
    font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif !important;
    background-color: #07090E !important;
    color: #F1F5F9 !important;
    direction: rtl;
    text-align: right;
}
h1, h2, h3, h4 {
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    color: #F8FAFC !important;
}
[data-testid="stMetric"] {
    background: #0F172A !important;
    border: 1px solid #1E293B !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    text-align: center !important;
}
[data-testid="stMetricValue"] {
    color: #FBBF24 !important;
    font-weight: 800 !important;
}
</style>
"""

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


def run_app():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.markdown(CUSTOM_UI_STYLE, unsafe_allow_html=True)

    ephe_path = "./ephe"
    try:
        os.makedirs(ephe_path, exist_ok=True)
    except OSError:
        ephe_path = ""

    @st.cache_resource
    def get_eph() -> SwissEphemeris:
        return SwissEphemeris(ephe_path)

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
            cities_by_country[c_code] = sorted(
                c_cities, key=lambda x: int(x.get("population") or 0), reverse=True
            )
        return country_map, sorted_countries, cities_by_country

    @st.cache_resource
    def get_tz_finder() -> TimezoneFinder:
        return TimezoneFinder()

    def make_to_utc(tz_str: str):
        tz = pytz.timezone(tz_str)
        def f(naive: dt.datetime) -> dt.datetime:
            return tz.localize(naive, is_dst=False).astimezone(pytz.utc).replace(tzinfo=None)
        return f

    country_map, country_list, cities_by_country = load_geo_data()
    tf = get_tz_finder()

    st.title(APP_TITLE)
    st.write(
        "الاتجاهات الأولية التوبوسنتريك + الأقواس الشمسية + التقدمية الثانوية + الانتهاء السنوي والشهري + العبور + العودة الشمسية"
    )
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("بيانات المولود")
        name = st.text_input("اسم الشخص:", "أحمد")
        gender_ar = st.selectbox("الجنس", ["ذكر", "أنثى"])
        gender = 'M' if gender_ar == "ذكر" else 'F'
        birth_date = st.date_input(
            "تاريخ الميلاد:", value=dt.date(1990, 5, 15),
            min_value=dt.date(1900, 1, 1), max_value=dt.date.today()
        )
        win_label = st.selectbox("النطاق الزمني لوقت الميلاد التقريبي (3 ساعات)", list(WINDOWS.keys()), index=1)
        start_hour = WINDOWS[win_label]
        anchor = 'forward'
        if start_hour == 22:
            anchor_ar = st.radio(
                "هذه النافذة تعبر منتصف الليل — ما معنى تاريخ الميلاد المُدخل؟",
                ["22:00 في هذا التاريخ ← 01:00 صباح اليوم التالي",
                 "22:00 من اليوم السابق ← 01:00 صباح هذا التاريخ"]
            )
            anchor = 'forward' if anchor_ar.startswith("22:00 في") else 'backward'

    with col2:
        st.subheader("مكان الميلاد (الدولة ثم المدينة)")
        selected_country = st.selectbox(
            "الدولة",
            country_list,
            index=None,
            placeholder="اختر الدولة...",
            key="country_select",
        )
        country_cities = (
            cities_by_country.get(country_map[selected_country], [])
            if selected_country
            else []
        )
        manual = st.checkbox("إدخال الإحداثيات يدويًا (أدق)")

        selected_city_obj: Optional[Dict[str, Any]] = None
        city_display = ""
        lat: Optional[float] = None
        lon: Optional[float] = None

        if manual:
            city_input = st.text_input(
                "اسم المدينة (للعرض في التقرير):",
                value="",
                placeholder="اكتب اسم المدينة...",
            )
            lat = st.number_input("خط العرض (شمال +)", value=0.0, format="%.4f")
            lon = st.number_input("خط الطول (شرق +)", value=0.0, format="%.4f")
            city_display = city_input.strip()
        else:
            selected_city_obj = st.selectbox(
                "المدينة (مرتبة حسب الأكثر تعدادًا للسكان)",
                country_cities,
                index=None,
                key=f"city_select_{selected_country or 'none'}",
                placeholder="اختر المدينة..." if selected_country else "اختر الدولة أولاً...",
                disabled=(selected_country is None or len(country_cities) == 0),
                format_func=lambda c: (
                    f"{c['name']} ({int(c.get('population') or 0):,} نسمة)"
                    if c.get("population")
                    else c["name"]
                ),
            )
            if selected_city_obj is not None:
                lat = float(selected_city_obj["latitude"])
                lon = float(selected_city_obj["longitude"])
                city_display = str(selected_city_obj["name"])

        if lat is not None and lon is not None and (manual or selected_city_obj is not None):
            tz_default = tf.timezone_at(lng=lon, lat=lat) or "UTC"
            tz_str = st.text_input("المنطقة الزمنية (IANA)", tz_default)
            st.info(
                f"الدولة: {selected_country or 'غير محددة'} | المدينة: {city_display or 'غير محددة'} | "
                f"خط العرض: {lat:.4f} | خط الطول: {lon:.4f} | المنطقة الزمنية: {tz_str}"
            )
        else:
            tz_str = st.text_input("المنطقة الزمنية (IANA)", value="", placeholder="تُحدد تلقائيًا بعد اختيار المدينة...")
            st.caption("اختر الدولة أولاً ثم اختر المدينة من القائمة المرتبة حسب التعداد السكاني.")

    st.divider()
    st.subheader("الحدث الماضي المعتمد (حدث واحد فقط — بحد أقصى 20 سنة)")
    today = dt.date.today()
    min_ev_date = min_allowed_event_date(birth_date, today)
    default_ev_date = max(min_ev_date, min(today, dt.date(2025, 6, 1)))

    st.caption(
        f"هدف البرنامج تصحيح الطالع بدقة الثانية من حدث ماضٍ واحد فقط (يقبل حدثًا لا يتجاوز عمره {MAX_EVENT_AGE_YEARS} سنة "
        f"من {min_ev_date.isoformat()} إلى {today.isoformat()} لتفادي تشوّه القوس، ويمكنك تغيير نوع الحدث أو تاريخه كما تشاء)."
    )

    kinds = list(EVENT_TYPES.keys())
    ev_c1, ev_c2, ev_c3 = st.columns([2, 1.2, 1.2])
    with ev_c1:
        ev_kind = st.selectbox("نوع الحدث الماضي (حدث واحد فقط)", kinds, key="single_ev_kind")
    with ev_c2:
        ev_date = st.date_input(
            "تاريخ الحدث",
            value=default_ev_date,
            min_value=min_ev_date,
            max_value=today,
            key="single_ev_date",
        )
    with ev_c3:
        use_ev_time = st.checkbox("تحديد ساعة الحدث (اختياري)", value=False, key="single_ev_use_time")
        ev_time = st.time_input(
            "ساعة الحدث",
            value=dt.time(12, 0),
            disabled=not use_ev_time,
            key="single_ev_time",
        )

    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1:
        step_s = st.select_slider("دقة المسح الأولي (ثانية؛ الصقل النهائي 1 ثانية)", options=[4, 6, 8, 12, 20], value=6)
    with c2:
        tech_labels = {
            "1. الاتجاهات الأولية (توبوسنتريك)": 'PD',
            "2. الأقواس الشمسية": 'SA',
            "3. التقدمية الثانوية": 'SD',
            "4. الانتهاء السنوي والشهري": 'AP',
            "5. العبور (مباشر وما قبل الولادة)": 'TR',
            "6. العودة الشمسية": 'SR',
        }
        chosen = st.multiselect("الخرائط الست المستخدمة", list(tech_labels.keys()), default=list(tech_labels.keys()))
    with c3:
        do_null = st.checkbox("اختبار الدلالة الإحصائية (أبطأ)", value=False)
        null_runs = st.slider("عدد المحاكاة", 10, 60, 20) if do_null else 0

    if st.button("بدء التصحيح السداسي", type="primary"):
        errors = []
        if not selected_country:
            errors.append("يرجى اختيار الدولة أولاً.")
        if not manual and selected_city_obj is None:
            errors.append("يرجى اختيار المدينة من قائمة مدن الدولة المختارة.")
        if manual and not city_display:
            errors.append("يرجى إدخال اسم المدينة مع الإحداثيات اليدوية.")
        if lat is None or lon is None:
            errors.append("يرجى تحديد موقع الميلاد (الدولة والمدينة) لعرض الإحداثيات.")
        if not tz_str.strip():
            errors.append("المنطقة الزمنية غير محددة.")
        else:
            try:
                pytz.timezone(tz_str)
            except Exception:
                errors.append("المنطقة الزمنية غير صحيحة.")
        if not chosen:
            errors.append("اختر خريطة واحدة على الأقل.")

        ev_err = validate_event_date(ev_date, birth_date, ev_kind, today)
        if ev_err:
            errors.append(ev_err)

        for e in errors:
            st.error(e)

        if not errors and lat is not None and lon is not None and selected_country:
            to_utc = make_to_utc(tz_str)
            chosen_time = ev_time if use_ev_time else None
            events: List[Event] = [make_event(ev_kind, ev_date, chosen_time, to_utc, 1.0)]
            rows = pd.DataFrame([{
                "نوع الحدث": ev_kind,
                "التاريخ": ev_date,
                "الساعة (اختياري)": chosen_time.strftime("%H:%M") if chosen_time else None,
                "الوزن": 1.0,
            }])
            with st.spinner("جاري مسح النافذة وحساب الخرائط الست وصقل الثواني..."):
                res = rectify(
                    get_eph(), birth_date, lat, lon, to_utc, events, gender, start_hour,
                    span_hours=3.0, step_s=step_s, anchor=anchor,
                    techniques=[tech_labels[c] for c in chosen], n_peaks=5, null_runs=null_runs
                )
            cands = res["candidates"]
            if not cands:
                st.warning("لم يُعثر على تطابق ضمن سماحيات الخرائط الست. راجع تاريخ الحدث أو النافذة.")
            else:
                top = cands[0]
                pts = top["points"]
                st.success(f"اكتمل التحليل السداسي — توافق {top['active_techs']} من {top['total_techs']} خرائط")
                st.markdown(
                    f"### ساعة الميلاد المصححة: **{top['time'].strftime('%H:%M:%S')}** "
                    f"({top['time'].strftime('%Y-%m-%d')}) — {selected_country} / {city_display}"
                )
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("الطالع الفلكي الحقيقي AS", describe_lon(pts["asc"]))
                m2.metric("وتد السماء MC", describe_lon(pts["mc"]))
                m3.metric("النقطة الشرقية EP", describe_lon(pts["ep"]))
                m4.metric("سهم السعادة POF", describe_lon(pts["pof"]))

                sect_label = "خريطة نهارية" if pts["is_day"] else "خريطة ليلية"
                st.caption(
                    f"الدولة: {selected_country} | المدينة: {city_display} | النطاق: {win_label} | "
                    f"RAMC = {pts['ramc']:.4f}° | {sect_label} | رب الطالع: {PLANET_AR[pts['asc_ruler']]} | "
                    f"برج الانتهاء السنوي: {top['prof_sign']} (رب السنة: {top['lord_of_year']})"
                )

                st.subheader("دائرة الزودياك للوقت المصحح")
                zodiac_svg = build_zodiac_svg(pts, top["time"], name, city_display, selected_country)
                components.html(
                    f'<div style="background:#07090E;padding:8px;border-radius:12px;">{zodiac_svg}</div>',
                    height=780,
                )

                html_report = generate_html_report(
                    name=name, gender_ar=gender_ar, birth_date=birth_date,
                    win_label=win_label, selected_country=selected_country,
                    city_str=city_display, lat=lat, lon=lon, tz_str=tz_str,
                    events_rows=rows, res=res, cands=cands
                )
                st.download_button(
                    label="تحميل التقرير النهائي الكامل مع دائرة الزودياك (HTML جاهز للطباعة)",
                    data=html_report.encode("utf-8"),
                    file_name=f"تقرير_استرو_رادار_{name}_{birth_date}.html",
                    mime="text/html",
                )

                st.subheader("المرشحون الأعلى نقاطًا (بدقة الثانية)")
                table = pd.DataFrame([{
                    "الترتيب": i + 1,
                    "الوقت المحلي": c["time"].strftime("%Y-%m-%d %H:%M:%S"),
                    "النقاط": round(c["score"], 1),
                    "توافق الخرائط": f"{c['active_techs']}/{c['total_techs']}",
                    "الطالع": describe_lon(c["points"]["asc"]),
                    "MC": describe_lon(c["points"]["mc"]),
                    "سهم السعادة": describe_lon(c["points"]["pof"]),
                    "هضبة (ث)": c["plateau_s"],
                } for i, c in enumerate(cands)])
                st.dataframe(table, use_container_width=True, hide_index=True)

                st.subheader("توزيع نقاط الخرائط الست للمرشح الأول")
                tb_df = pd.DataFrame([{
                    "الخريطة": TECH_AR[k],
                    "النقاط": round(v, 1),
                } for k, v in top["tech_breakdown"].items()])
                st.dataframe(tb_df, use_container_width=True, hide_index=True)

                st.subheader("تفصيل التطابقات للمرشح الأول")
                for ev, hits in top["detail"]:
                    with st.expander(f"{ev.label} — {len(hits)} تطابق"):
                        if not hits:
                            st.write("لا تطابقات ضمن السماحيات لهذا الحدث عند هذا الوقت.")
                        for h in hits[:24]:
                            st.write(f"• [{h.tech}] {h.text} — فارق {h.orb:.1f}′ — {h.score:.1f} نقطة")


if __name__ == "__main__":
    run_app()
