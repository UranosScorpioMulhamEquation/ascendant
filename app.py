from __future__ import annotations

import datetime as dt
import hashlib
import html as html_lib
import math
import os
import uuid
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import geonamescache
import numpy as np
import pandas as pd
import pytz
import streamlit as st
from timezonefinder import TimezoneFinder

# ==================== إعدادات الأمان ونظام الترخيص ====================
KEY_FILE = "license.key"


def get_machine_id() -> str:
    return hex(uuid.getnode())


def generate_password(mid: str) -> str:
    digits = ''.join(filter(str.isdigit, mid))
    if not digits:
        try:
            digits = str(int(mid, 16))
        except Exception:
            return "Error"
    num = int(digits)
    result = round(abs(num / 2 * 3.14))
    return str(result)[:6]


if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = os.path.exists(KEY_FILE)

if not st.session_state['authenticated']:
    st.set_page_config(page_title="نظام الأمان والتحقق", layout="centered")
    st.title("🛡️ تفعيل نظام الأمان الفلكي")
    st.warning("الرجاء إرسال معرف الجهاز (Machine ID) للمطور للتفعيل: mulham81ahmed@gmail.com")

    mid = get_machine_id()
    st.info(f"Machine ID: {mid}")
    pwd = st.text_input("أدخل مفتاح التفعيل:", type="password")

    if st.button("تفعيل النظام"):
        if pwd == generate_password(mid):
            with open(KEY_FILE, "w") as f:
                f.write(pwd)
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.error("مفتاح التفعيل غير صحيح.")

    st.stop()

APP_TITLE = "تصحيح الطالع ودرجته من ست خرائط فلكية (تطوير استرو رادار)"
THRESHOLD_PERCENT = 60.0
SPAN_HOURS = 3.0
SCAN_STEP_SECONDS = 4
HOUSE_SYSTEM = "topocentric"

# ==============================================================================
# 1. الثوابت الفلكية العالمية وجداول الرموز والأحداث الحاسمة المعتمدة
# ==============================================================================
TROPICAL_YEAR = 365.2421904
NAIBOD_PER_DAY = 360.0 / TROPICAL_YEAR / TROPICAL_YEAR  # ~0.002698613 deg/day (59'08.33"/yr)
BASE_SCORE = 25.0

PLANETS = ["SUN", "MOON", "MER", "VEN", "MAR", "JUP", "SAT", "URA", "NEP", "PLU", "NN", "SN"]
PLANET_AR = {
    "SUN": "الشمس", "MOON": "القمر", "MER": "عطارد", "VEN": "الزهرة", "MAR": "المريخ",
    "JUP": "المشتري", "SAT": "زحل", "URA": "أورانوس", "NEP": "نبتون", "PLU": "بلوتو",
    "NN": "العقدة الشمالية", "SN": "العقدة الجنوبية",
}
PLANET_GLYPH = {
    "SUN": "☉", "MOON": "☽", "MER": "☿", "VEN": "♀", "MAR": "♂",
    "JUP": "♃", "SAT": "♄", "URA": "♅", "NEP": "♆", "PLU": "♇",
    "NN": "☊", "SN": "☋",
}
FACTOR_AR = {
    "AS": "الطالع AS", "MC": "وتد السماء MC", "DS": "الغارب DS", "IC": "وتد الأرض IC",
    "EP": "النقطة الشرقية EP", "POF": "سهم السعادة POF", "POS": "سهم الغيب POS",
    "H2": "البيت 2", "H3": "البيت 3", "H5": "البيت 5", "H6": "البيت 6",
    "H8": "البيت 8", "H9": "البيت 9", "H11": "البيت 11", "H12": "البيت 12",
}
SIGNS_AR = [
    "الحمل", "الثور", "الجوزاء", "السرطان", "الأسد", "العذراء",
    "الميزان", "العقرب", "القوس", "الجدي", "الدلو", "الحوت",
]
SIGN_GLYPHS = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
SIGN_RULERS = ["MAR", "VEN", "MER", "MOON", "SUN", "MER", "VEN", "MAR", "JUP", "SAT", "SAT", "JUP"]

ASPECTS = (0, 30, 45, 60, 90, 120, 135, 150, 180)
MAJOR_ASPECTS = (0, 60, 90, 120, 180)
ASPECT_W = {
    0: 1.0, 180: 1.0, 90: 0.85, 120: 0.85, 60: 0.8,
    30: 0.4, 45: 0.45, 135: 0.45, 150: 0.45,
}
ASPECT_AR = {
    0: "اقتران", 30: "نصف تسديس", 45: "نصف تربيع", 60: "تسديس",
    90: "تربيع", 120: "تثليث", 135: "تربيع ونصف", 150: "مقارنة ساقطة", 180: "مقابلة",
}

# السماحيات العالمية بالدقائق القوسية (arcminutes)
PD_ORB_MAJOR, PD_ORB_MINOR = 12.0, 6.0
SA_ORB_MAJOR, SA_ORB_MINOR = 14.0, 7.0
TR_ORB = 60.0
SR_ORB_MAJOR, SR_ORB_MINOR = 50.0, 25.0
AP_ORB_MAJOR, AP_ORB_MINOR = 35.0, 18.0
SEC_ORB = {
    "SUN": 12.0, "MOON": 36.0, "MER": 12.0, "VEN": 12.0, "MAR": 12.0,
    "JUP": 9.0, "SAT": 9.0, "URA": 5.0, "NEP": 5.0, "PLU": 5.0,
    "NN": 5.0, "SN": 5.0,
}
SEC_ORB_MOON = (36.0, 20.0)

TECH_CODES = ("PD", "SA", "SD", "AP", "TR", "SR")
TECH_AR = {
    "PD": "1. الاتجاهات الأولية (PD)",
    "SA": "2. الأقواس الشمسية (SA)",
    "SD": "3. التقدمية الثانوية (SD)",
    "AP": "4. الانتهاء السنوي والشهري (AP)",
    "TR": "5. العبور الكوكبي (TR)",
    "SR": "6. العودة الشمسية (SR)",
}


def _ev(sig, pl, sig2=(), pl2=(), houses=()):
    return dict(sig=list(sig), pl=list(pl), sig2=list(sig2), pl2=list(pl2), houses=list(houses))


# الأحداث الحاسمة المعتمدة حصرًا في تصحيح الطالع (19 حدثًا عالي الحسم)
EVENT_TYPES: Dict[str, dict] = {
    # أحداث الوفاة
    "موت الأب أو الجد": _ev(["MC", "AS", "H8"], ["SAT", "SUN", "NEP", "PLU", "MAR", "SN"], ["H12", "IC"], ["MOON", "URA"], [10, 4, 8]),
    "موت الأم أو الجدة": _ev(["IC", "AS", "H8"], ["MOON", "VEN", "SAT", "NEP", "PLU", "SN", "MAR"], ["H12", "MC"], ["SUN", "URA"], [4, 10, 8]),
    "موت الابن": _ev(["H5", "IC", "DS", "H8"], ["MAR", "SAT", "NEP", "PLU", "SN"], ["H12"], ["SUN", "MER", "URA"], [5, 8]),
    "موت الابنة": _ev(["H5", "IC", "DS", "H8"], ["VEN", "MOON", "NEP", "PLU", "SN"], ["H12"], ["MAR", "URA", "MER"], [5, 8]),
    "موت الزوج": _ev(["DS", "IC", "H8"], ["SAT", "SUN", "NEP", "PLU", "SN", "MAR"], ["H12", "H5"], ["URA"], [7, 8]),
    "موت الزوجة": _ev(["DS", "IC", "H8"], ["MOON", "VEN", "SAT", "NEP", "PLU", "SN", "MAR"], ["H12", "H5"], ["URA"], [7, 8]),
    "موت أخ": _ev(["H3", "AS", "IC", "H8"], ["MER", "MAR", "SAT", "NEP", "PLU", "SN"], ["H12"], ["MOON", "SUN"], [3, 8]),
    "موت أخت": _ev(["H3", "AS", "IC", "H8"], ["MOON", "MER", "VEN", "MAR", "SAT", "NEP", "PLU", "SN"], ["H12"], [], [3, 8]),

    # أحداث الولادة
    "ولادة ابن": _ev(["H5", "AS", "IC"], ["MAR", "SUN", "JUP", "NN"], ["MC"], ["PLU", "URA", "MOON", "VEN", "MER"], [5, 1]),
    "ولادة ابنة": _ev(["H5", "AS", "IC"], ["VEN", "MOON", "JUP", "NN"], ["MC"], ["MAR", "URA", "PLU", "SUN", "MER"], [5, 1]),
    "ولادة أخ أصغر": _ev(["H3", "IC", "DS"], ["MER", "JUP"], [], ["SUN", "MOON", "VEN", "NN", "URA", "PLU"], [3]),
    "ولادة أخت صغرى": _ev(["H3", "IC", "DS"], ["MOON", "MER", "VEN"], [], ["SUN", "JUP", "NN", "URA", "PLU"], [3]),

    # أحداث المشفى والعمليات والحوادث الطارئة
    "دخول المشفى (عملية جراحية)": _ev(["AS", "H12", "MC"], ["MAR", "SAT", "NEP"], ["H6", "H8"], ["URA", "PLU", "MOON"], [1, 6, 12]),
    "دخول المشفى (علاج طبي)": _ev(["H6", "H12", "AS"], ["SAT", "NEP", "JUP", "MAR"], ["MC", "H8"], ["MOON", "MER", "PLU"], [6, 12, 1]),
    "دخول المشفى (عملية تجميل)": _ev(["AS", "H12", "H5"], ["VEN", "MAR", "URA", "PLU"], ["MC", "H6"], ["SUN", "MOON", "NEP"], [1, 6, 12]),
    "حادث طارئ / دخول إسعاف": _ev(["AS", "H3", "MC"], ["MAR", "URA", "SAT", "MER"], ["H12", "H8"], ["NEP", "SN", "PLU", "MOON"], [1, 3, 12]),

    # أحداث الزواج (عقد قران منفصل / حفلة زفاف رسمية / كلاهما في نفس اليوم)
    "تاريخ عقد القران (بدون حفلة زفاف / منفصل)": {
        "M": _ev(["DS", "H9", "MC"], ["VEN", "MER", "JUP", "NN"], ["AS", "H3"], ["MOON", "SUN", "URA"], [7, 9, 3]),
        "F": _ev(["DS", "H9", "MC"], ["SUN", "JUP", "MER", "NN"], ["AS", "H3"], ["VEN", "MOON", "URA"], [7, 9, 3]),
    },
    "تاريخ حفلة الزفاف الرسمية": {
        "M": _ev(["DS", "MC", "H5"], ["VEN", "MOON", "JUP", "NN"], ["AS"], ["SUN", "URA", "MAR", "MER"], [7, 10, 5]),
        "F": _ev(["DS", "MC", "H5"], ["SUN", "JUP", "MAR", "NN"], ["AS"], ["VEN", "MOON", "URA", "PLU"], [7, 10, 5]),
    },
    "عقد القران وحفلة الزفاف في نفس اليوم": {
        "M": _ev(["DS", "MC", "H5", "AS"], ["VEN", "MOON", "NN", "JUP", "MER"], ["H9"], ["SUN", "URA", "MAR"], [7, 10, 5, 9]),
        "F": _ev(["DS", "MC", "H5", "AS"], ["SUN", "JUP", "MAR", "NN", "MER"], ["H9"], ["VEN", "MOON", "URA", "PLU"], [7, 10, 5, 9]),
    },
}

THREE_HOUR_WINDOWS = [
    ("00:00 ← 03:00 (بعد منتصف الليل)", 0, 0),
    ("01:00 ← 04:00 (فجرًا)", 1, 0),
    ("04:00 ← 07:00 (فجرًا إلى الصباح)", 4, 0),
    ("07:00 ← 10:00 (صباحًا)", 7, 0),
    ("10:00 ← 13:00 (الضحى إلى الظهر)", 10, 0),
    ("13:00 ← 16:00 (بعد الظهر)", 13, 0),
    ("16:00 ← 19:00 (العصر إلى المساء)", 16, 0),
    ("19:00 ← 22:00 (المساء)", 19, 0),
    ("22:00 ← 01:00 (عبور منتصف الليل)", 22, 0),
]


def resolve_spec(kind: str, gender: str) -> dict:
    s = EVENT_TYPES.get(kind, EVENT_TYPES["عقد القران وحفلة الزفاف في نفس اليوم"])
    if "M" in s and "F" in s:
        return s["M"] if gender == "M" else s["F"]
    return s


def house_cusp_key(h_num: int) -> str:
    return {1: "AS", 4: "IC", 7: "DS", 10: "MC"}.get(h_num, f"H{h_num}")


# ==============================================================================
# 2. رياضيات الكرة السماوية المصححة + نظام البيوت التوبوسنتريك (Polich-Page)
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
    """تصحيح معادلة المطالع البلدية باستخدام atan2 المستمر لتلافي انقطاع 0° و 180°."""
    oa_r = np.radians(np.asarray(oa_deg, float) % 360.0)
    num = np.sin(oa_r)
    den = np.cos(oa_r) * np.cos(eps_rad) - np.tan(phi_rad) * np.sin(eps_rad)
    return np.degrees(np.arctan2(num, den)) % 360.0


def asc_from_ramc(ramc, lat_deg: float, eps_deg: float):
    r = np.radians(ramc)
    phi = math.radians(lat_deg)
    e = math.radians(eps_deg)
    num = np.cos(r)
    den = -(np.sin(r) * math.cos(e) + math.tan(phi) * math.sin(e))
    return np.degrees(np.arctan2(num, den)) % 360.0


def all_cusps_topocentric(ramc, lat_deg: float, eps_deg: float) -> Dict[str, np.ndarray]:
    """حساب البيوت بنظام التوبوسنتريك فقط (Polich-Page) المعتمد عالميًا في التسيير."""
    ramc = np.atleast_1d(np.asarray(ramc, float))
    e = math.radians(eps_deg)
    t = math.tan(math.radians(lat_deg))
    out: Dict[str, np.ndarray] = {}
    for name, k, tp in (
        ("H11", 1, t / 3.0),
        ("H12", 2, 2.0 * t / 3.0),
        ("H2", 4, 2.0 * t / 3.0),
        ("H3", 5, t / 3.0),
    ):
        out[name] = lam_from_oa(ramc + 30.0 * k, math.atan(tp), e)

    out["AS"] = asc_from_ramc(ramc, lat_deg, eps_deg)
    out["H5"] = (out["H11"] + 180.0) % 360.0
    out["H6"] = (out["H12"] + 180.0) % 360.0
    out["DS"] = (out["AS"] + 180.0) % 360.0
    out["H8"] = (out["H2"] + 180.0) % 360.0
    out["H9"] = (out["H3"] + 180.0) % 360.0
    mc = mc_from_ramc(ramc, eps_deg)
    out["MC"] = mc
    out["IC"] = (mc + 180.0) % 360.0
    out["EP"] = lam_from_oa(ramc + 90.0, 0.0, e)
    return out


def compute_arabic_lots(asc, sun, moon):
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
    """تصحيح قطبية القطب الفلكي للغارب (OD) باستخدام -phi_p مع ثبات +eps."""
    phi_p, oa_od, is_oa = planet_speculum(lam, ramc, lat_deg, eps_deg)
    e = math.radians(eps_deg)
    eff_phi = np.where(is_oa, phi_p, -phi_p)
    return lam_from_oa(oa_od + arc, eff_phi, e)


# ==============================================================================
# 3. الأفيمريس (Swiss Ephemeris مع دعم Moshier التلقائي لبيئة Streamlit Cloud)
# ==============================================================================
class SwissEphemeris:
    _IDS = {
        "SUN": 0, "MOON": 1, "MER": 2, "VEN": 3, "MAR": 4,
        "JUP": 5, "SAT": 6, "URA": 7, "NEP": 8, "PLU": 9,
    }

    def __init__(self, ephe_path: Optional[str] = None):
        import swisseph as swe
        self.swe = swe
        has_files = bool(
            ephe_path and os.path.isdir(ephe_path) and any(f.endswith(".se1") for f in os.listdir(ephe_path))
        )
        if has_files and ephe_path:
            swe.set_ephe_path(ephe_path)
        self.flags = swe.FLG_SWIEPH if has_files else swe.FLG_MOSEPH

    def _raw(self, jd: float) -> Dict[str, float]:
        out = {k: self.swe.calc_ut(jd, i, self.flags)[0][0] for k, i in self._IDS.items()}
        out["NN"] = self.swe.calc_ut(jd, self.swe.MEAN_NODE, self.flags)[0][0]
        out["SN"] = (out["NN"] + 180.0) % 360.0
        return out

    def lons(self, jd) -> Dict[str, np.ndarray]:
        jd = np.atleast_1d(np.asarray(jd, float))
        lo, hi = float(jd.min()), float(jd.max())
        if jd.size <= 3 or hi - lo < 1e-9:
            vals = [self._raw(float(j)) for j in jd]
            return {k: np.array([v[k] for v in vals]) for k in vals[0]}
        n = int(min(max((hi - lo) * 144.0 + 2, 3), 800))
        grid = np.linspace(lo, hi, n)
        vals = [self._raw(float(j)) for j in grid]
        out = {}
        for k in vals[0]:
            a = np.degrees(np.unwrap(np.radians([v[k] for v in vals])))
            out[k] = np.interp(jd, grid, a) % 360.0
        return out

    def sun_lon_scalar(self, jd: float) -> float:
        return float(self.swe.calc_ut(jd, 0, self.flags)[0][0])

    def eps(self, jd: float) -> float:
        return float(self.swe.calc_ut(jd, self.swe.ECL_NUT, self.flags)[0][0])

    def ramc(self, jd, lon: float) -> np.ndarray:
        jd = np.atleast_1d(np.asarray(jd, float))
        st_arr = np.array([self.swe.sidtime(float(j)) for j in jd])
        return (st_arr * 15.0 + lon) % 360.0


def solve_solar_return_jds(eph: SwissEphemeris, target_sun: np.ndarray, approx_jd: np.ndarray) -> np.ndarray:
    approx_jd = np.asarray(approx_jd, float)
    mid_idx = approx_jd.size // 2
    jd_ref = float(approx_jd[mid_idx])
    sun_mid = float(target_sun[mid_idx])
    for _ in range(5):
        s_now = eph.sun_lon_scalar(jd_ref)
        diff = float(_wrap180(sun_mid - s_now))
        if abs(diff) < 1e-5:
            break
        jd_ref += diff / 0.985647
    sun_diffs = _wrap180(target_sun - sun_mid)
    jds = jd_ref + sun_diffs / 0.985647
    s_chk = eph.lons(jds)["SUN"]
    return jds + _wrap180(target_sun - s_chk) / 0.985647


# ==============================================================================
# 4. أدوات الزمان والمكان والمسح التسلسلي كل 4 ثوانٍ
# ==============================================================================
def jd_from_utc(d: dt.datetime) -> float:
    return (d - dt.datetime(1970, 1, 1)).total_seconds() / 86400.0 + 2440587.5


def make_candidates_sequential(
    birth_date: dt.date,
    start_hour: int,
    start_minute: int,
    span_hours: float,
    step_s: int,
    to_utc: Callable[[dt.datetime], dt.datetime],
):
    """مسح تسلسلي شامل من بداية نطاق الـ 3 ساعات إلى نهايته كل 4 ثوانٍ."""
    start = dt.datetime.combine(birth_date, dt.time(start_hour % 24, start_minute % 60))
    total_s = int(round(span_hours * 3600))
    offsets = list(range(0, total_s + 1, int(step_s)))
    if offsets[-1] != total_s:
        offsets.append(total_s)
    locs = [start + dt.timedelta(seconds=s) for s in offsets]
    jd = np.array([jd_from_utc(to_utc(x)) for x in locs])
    return locs, jd, offsets


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


def build_natal(eph: SwissEphemeris, jd, lat: float, lon: float) -> Natal:
    jd = np.atleast_1d(np.asarray(jd, float))
    eps = eph.eps(float(jd[jd.size // 2]))
    ramc = eph.ramc(jd, lon)
    pl = eph.lons(jd)
    cusps = all_cusps_topocentric(ramc, lat, eps)
    is_day, pof, pos = compute_arabic_lots(cusps["AS"], pl["SUN"], pl["MOON"])
    cusps["POF"] = pof
    cusps["POS"] = pos
    return Natal(jd, ramc, eps, lat, lon, pl, cusps, is_day, pof, pos)


class _NormalizedTechAcc:
    """تقييم الخرائط الست (0%-100%) وفق أقوى 3 تطابقات غير مكررة بتناقص حدي."""

    def __init__(self, n: int, explain: bool):
        self.n = n
        self.explain = explain
        self.h1: Dict[str, np.ndarray] = {t: np.zeros(n) for t in TECH_CODES}
        self.h2: Dict[str, np.ndarray] = {t: np.zeros(n) for t in TECH_CODES}
        self.h3: Dict[str, np.ndarray] = {t: np.zeros(n) for t in TECH_CODES}
        self.hits: List[Tuple[str, str, str, str, int, str, float, float]] = []

    def _push_strengths(self, tech_code: str, strengths_row: np.ndarray):
        # Update top-3 vectorized across all candidates
        h1 = self.h1[tech_code]
        h2 = self.h2[tech_code]
        h3 = self.h3[tech_code]

        m1 = strengths_row >= h1
        h3 = np.where(m1, h2, h3)
        h2 = np.where(m1, h1, h2)
        h1 = np.where(m1, strengths_row, h1)

        m2 = (~m1) & (strengths_row >= h2)
        h3 = np.where(m2, h2, h3)
        h2 = np.where(m2, strengths_row, h2)

        m3 = (~m1) & (~m2) & (strengths_row > h3)
        h3 = np.where(m3, strengths_row, h3)

        self.h1[tech_code] = h1
        self.h2[tech_code] = h2
        self.h3[tech_code] = h3

    def add(
        self,
        tech_code: str,
        desc: Tuple[str, str],
        lam_a,
        lam_b,
        factor: float,
        sub_w: float,
        lim_maj: float,
        lim_min: float,
        aspects: Sequence[int],
    ):
        d = np.atleast_1d((np.asarray(lam_a, float) - np.asarray(lam_b, float)) % 360.0)
        A = np.array(aspects, float)[:, None]
        o = np.minimum(np.abs(d[None, :] - A), np.abs(d[None, :] - (360.0 - A))) * 60.0
        lim = np.where(np.isin(A, (0.0, 60.0, 90.0, 120.0, 180.0)), lim_maj, lim_min)
        valid = o < lim
        closeness = np.where(valid, np.clip(1.0 - o / lim, 0.0, None) ** 1.25, 0.0)
        exact_boost = np.where(o <= 3.0, 1.30, np.where(o <= 8.0, 1.12, 1.0))
        asp_w = np.array([ASPECT_W[int(a)] for a in aspects])[:, None]
        strength = np.where(valid, factor * sub_w * asp_w * closeness * exact_boost, 0.0)

        for i, a in enumerate(aspects):
            row = strength[i]
            if np.any(row > 0):
                self._push_strengths(tech_code, row)
                if self.explain and row[0] > 0:
                    self.hits.append((
                        tech_code,
                        TECH_AR[tech_code],
                        desc[0],
                        desc[1],
                        int(a),
                        ASPECT_AR.get(int(a), f"{a}°"),
                        float(o[i, 0]),
                        float(BASE_SCORE * row[0]),
                    ))

    def percentages(self, techniques: Sequence[str]) -> Tuple[Dict[str, np.ndarray], np.ndarray]:
        pcts: Dict[str, np.ndarray] = {}
        total = np.zeros(self.n)
        for t in techniques:
            eff = self.h1[t] + 0.30 * (self.h2[t] + self.h3[t])
            pct = np.clip(100.0 * (1.0 - np.exp(-1.1 * eff)), 0.0, 100.0)
            pcts[t] = pct
            total += pct
        avg_pct = total / max(1, len(techniques))
        return pcts, avg_pct


def _get_lists(spec: dict):
    sigs = [(s, 1.0) for s in spec["sig"]] + [(s, 0.55) for s in spec["sig2"]]
    if "EP" not in [x[0] for x in sigs]:
        sigs.append(("EP", 0.55))
    if "POF" not in [x[0] for x in sigs]:
        sigs.append(("POF", 0.65))
    pls = [(p, 1.0) for p in spec["pl"]] + [(p, 0.55) for p in spec["pl2"]]
    return sigs, pls


def _run_pd(acc: _NormalizedTechAcc, natal: Natal, spec: dict, days: np.ndarray):
    sigs, pls = _get_lists(spec)
    A = days * NAIBOD_PER_DAY
    for sgn, dlab, tw_cusp in ((1, "مباشر", 1.05), (-1, "عكسي", 0.85)):
        arc = sgn * A
        dc = all_cusps_topocentric(natal.ramc + arc, natal.lat, natal.eps)
        dc["POF"] = (natal.pof + arc) % 360.0
        for s, fs in sigs:
            for p, fp in pls:
                acc.add("PD", (f"{FACTOR_AR.get(s, s)} ({dlab})", f"{PLANET_AR[p]} أصلي"),
                        dc[s], natal.pl[p], fs * fp, tw_cusp, PD_ORB_MAJOR, PD_ORB_MINOR, ASPECTS)
        prom_lab = "عكسي فلكي" if sgn == 1 else "مباشر فلكي"
        for p, fp in pls:
            ld = direct_planet(natal.pl[p], natal.ramc, natal.lat, natal.eps, arc)
            for s, fs in sigs:
                acc.add("PD", (f"{PLANET_AR[p]} ({prom_lab})", f"{FACTOR_AR.get(s, s)} أصلي"),
                        ld, natal.cusps[s], fs * fp, 0.9, PD_ORB_MAJOR, PD_ORB_MINOR, ASPECTS)


def _run_sa(eph: SwissEphemeris, acc: _NormalizedTechAcc, natal: Natal, spec: dict, days: np.ndarray):
    sigs, pls = _get_lists(spec)
    yrs = days / TROPICAL_YEAR
    sun_p = eph.lons(natal.jd + yrs)["SUN"]
    sa_base = (sun_p - natal.pl["SUN"]) % 360.0
    for sgn, dlab, w_dir in ((1, "+قوس شمسي", 0.9), (-1, "-قوس عكسي", 0.65)):
        sa = sgn * sa_base
        for s, fs in sigs:
            for p, fp in pls:
                acc.add("SA", (f"{FACTOR_AR.get(s, s)} ({dlab})", f"{PLANET_AR[p]} أصلي"),
                        natal.cusps[s] + sa, natal.pl[p], fs * fp, w_dir, SA_ORB_MAJOR, SA_ORB_MINOR, ASPECTS)
                acc.add("SA", (f"{PLANET_AR[p]} ({dlab})", f"{FACTOR_AR.get(s, s)} أصلي"),
                        natal.pl[p] + sa, natal.cusps[s], fs * fp, w_dir * 0.9, SA_ORB_MAJOR, SA_ORB_MINOR, ASPECTS)


def _run_sd(eph: SwissEphemeris, acc: _NormalizedTechAcc, natal: Natal, spec: dict, days: np.ndarray):
    sigs, pls = _get_lists(spec)
    yrs = days / TROPICAL_YEAR
    sun0 = ra_of_lon(natal.pl["SUN"], natal.eps)
    for jdx, lab, tw in ((natal.jd + yrs, "تقدمي", 0.95), (natal.jd - yrs, "تراجعي", 0.7)):
        pl = eph.lons(jdx)
        arc = _wrap180(ra_of_lon(pl["SUN"], natal.eps) - sun0)
        dc = all_cusps_topocentric(natal.ramc + arc, natal.lat, natal.eps)
        _, pof_p, _ = compute_arabic_lots(dc["AS"], pl["SUN"], pl["MOON"])
        dc["POF"] = pof_p
        for p, fp in pls:
            lmj, lmn = SEC_ORB_MOON if p == "MOON" else (SEC_ORB[p], SEC_ORB[p])
            for s, fs in sigs:
                acc.add("SD", (f"{FACTOR_AR.get(s, s)} ({lab})", f"{PLANET_AR[p]} أصلي"),
                        dc[s], natal.pl[p], fs * fp, tw, lmj, lmn, ASPECTS)
                acc.add("SD", (f"{PLANET_AR[p]} ({lab})", f"{FACTOR_AR.get(s, s)} أصلي"),
                        pl[p], natal.cusps[s], fs * fp, tw * 0.95, lmj, lmn, ASPECTS)
        if "MOON" not in [x[0] for x in pls]:
            for s, fs in sigs[:3]:
                acc.add("SD", (f"القمر التقدمي ({lab})", f"{FACTOR_AR.get(s, s)} أصلي"),
                        pl["MOON"], natal.cusps[s], fs * 0.75, tw * 0.9, SEC_ORB_MOON[0], SEC_ORB_MOON[1], ASPECTS)


def _run_ap(eph: SwissEphemeris, acc: _NormalizedTechAcc, natal: Natal, ev_jd: float,
            pl_tr: Dict[str, np.ndarray], spec: dict, days: np.ndarray):
    _, pls = _get_lists(spec)
    years_exact = days / TROPICAL_YEAR
    age_int = np.floor(years_exact).astype(int)
    frac_yr = years_exact - age_int
    prof_arc_yr = (years_exact * 30.0) % 360.0
    prof_arc_mo = ((age_int * 30.0) + (frac_yr * 360.0)) % 360.0

    prof_as = (natal.cusps["AS"] + prof_arc_yr) % 360.0
    prof_mc = (natal.cusps["MC"] + prof_arc_yr) % 360.0
    prof_pof = (natal.pof + prof_arc_yr) % 360.0
    prof_as_mo = (natal.cusps["AS"] + prof_arc_mo) % 360.0

    for p, fp in pls:
        acc.add("AP", ("انتهاء الطالع السنوي", f"{PLANET_AR[p]} أصلي"),
                prof_as, natal.pl[p], fp, 0.95, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
        acc.add("AP", ("انتهاء العاشر السنوي", f"{PLANET_AR[p]} أصلي"),
                prof_mc, natal.pl[p], fp, 0.85, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
        acc.add("AP", ("انتهاء سهم السعادة", f"{PLANET_AR[p]} أصلي"),
                prof_pof, natal.pl[p], fp, 0.75, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
        # خيار وقت الحدث يقتصر على صباحًا/مساءً لذا نستبعد عبور القمر الدقيق غير المحدد بالساعة
        if p != "MOON":
            acc.add("AP", ("انتهاء الطالع السنوي", f"{PLANET_AR[p]} عابر"),
                    prof_as, pl_tr[p], fp, 0.80, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
            acc.add("AP", ("انتهاء الطالع الشهري", f"{PLANET_AR[p]} عابر"),
                    prof_as_mo, pl_tr[p], fp, 0.65, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)

    asc_signs = (np.floor(natal.cusps["AS"] / 30.0).astype(int)) % 12
    prof_signs = (asc_signs + age_int) % 12
    ev_houses = spec.get("houses", [1])
    h_key = house_cusp_key(ev_houses[0]) if ev_houses else "AS"
    ev_house_signs = (np.floor(natal.cusps[h_key] / 30.0).astype(int)) % 12

    n = natal.jd.size
    lord_year_lon = np.zeros(n)
    lord_year_tr = np.zeros(n)
    lord_ev_lon = np.zeros(n)
    lord_ev_tr = np.zeros(n)

    for p_code in ("MAR", "VEN", "MER", "MOON", "SUN", "JUP", "SAT"):
        mask_y = np.array([SIGN_RULERS[int(s)] == p_code for s in prof_signs])
        if mask_y.any():
            lord_year_lon[mask_y] = natal.pl[p_code][mask_y]
            lord_year_tr[mask_y] = pl_tr[p_code][0]
        mask_e = np.array([SIGN_RULERS[int(s)] == p_code for s in ev_house_signs])
        if mask_e.any():
            lord_ev_lon[mask_e] = natal.pl[p_code][mask_e]
            lord_ev_tr[mask_e] = pl_tr[p_code][0]

    acc.add("AP", ("رب السنة عابر", "الطالع AS أصلي"), lord_year_tr, natal.cusps["AS"], 1.0, 0.95, TR_ORB, TR_ORB, MAJOR_ASPECTS)
    acc.add("AP", ("رب السنة عابر", "وتد السماء MC أصلي"), lord_year_tr, natal.cusps["MC"], 1.0, 0.85, TR_ORB, TR_ORB, MAJOR_ASPECTS)
    acc.add("AP", ("رب بيت الحدث عابر", "الطالع AS أصلي"), lord_ev_tr, natal.cusps["AS"], 1.0, 0.90, TR_ORB, TR_ORB, MAJOR_ASPECTS)
    acc.add("AP", ("رب بيت الحدث عابر", "وتد السماء MC أصلي"), lord_ev_tr, natal.cusps["MC"], 1.0, 0.80, TR_ORB, TR_ORB, MAJOR_ASPECTS)
    acc.add("AP", ("انتهاء الطالع السنوي", "رب السنة أصلي"), prof_as, lord_year_lon, 1.0, 1.00, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)
    acc.add("AP", ("انتهاء الطالع السنوي", "رب بيت الحدث أصلي"), prof_as, lord_ev_lon, 1.0, 0.90, AP_ORB_MAJOR, AP_ORB_MINOR, MAJOR_ASPECTS)


def _run_tr(eph: SwissEphemeris, acc: _NormalizedTechAcc, natal: Natal, ev_jd: float,
            pl_dir: Dict[str, np.ndarray], spec: dict):
    sigs, pls = _get_lists(spec)
    pl_pre = eph.lons(2.0 * natal.jd - ev_jd)
    for lab, pl, tw in (("مباشر", pl_dir, 0.90), ("ما قبل الولادة", pl_pre, 0.65)):
        for p, fp in pls:
            if p == "MOON":
                continue
            for s, fs in sigs:
                acc.add("TR", (f"{PLANET_AR[p]} عابر ({lab})", f"{FACTOR_AR.get(s, s)} أصلي"),
                        pl[p], natal.cusps[s], fs * fp, tw, TR_ORB, TR_ORB, MAJOR_ASPECTS)


def _run_sr(eph: SwissEphemeris, acc: _NormalizedTechAcc, natal: Natal, ev_jd: float, spec: dict):
    sigs, pls = _get_lists(spec)
    years = (ev_jd - natal.jd) / TROPICAL_YEAR
    sr_year = np.floor(years)
    approx_sr_jd = natal.jd + sr_year * TROPICAL_YEAR
    jd_sr = solve_solar_return_jds(eph, natal.pl["SUN"], approx_sr_jd)

    eps_sr = eph.eps(float(jd_sr[jd_sr.size // 2]))
    ramc_sr = eph.ramc(jd_sr, natal.lon)
    cusps_sr = all_cusps_topocentric(ramc_sr, natal.lat, eps_sr)
    pl_sr = eph.lons(jd_sr)
    _, pof_sr, _ = compute_arabic_lots(cusps_sr["AS"], pl_sr["SUN"], pl_sr["MOON"])
    cusps_sr["POF"] = pof_sr

    for sr_ang in ("AS", "MC", "DS", "IC", "POF"):
        for nat_s, fs in sigs[:4]:
            acc.add("SR", (f"{FACTOR_AR[sr_ang]} عودة شمسية", f"{FACTOR_AR.get(nat_s, nat_s)} أصلي"),
                    cusps_sr[sr_ang], natal.cusps[nat_s], fs, 1.00, SR_ORB_MAJOR, SR_ORB_MINOR, MAJOR_ASPECTS)
        for p, fp in pls:
            acc.add("SR", (f"{FACTOR_AR[sr_ang]} عودة شمسية", f"{PLANET_AR[p]} أصلي"),
                    cusps_sr[sr_ang], natal.pl[p], fp, 0.90, SR_ORB_MAJOR, SR_ORB_MINOR, ASPECTS)

    for p, fp in pls:
        for nat_s, fs in sigs[:4]:
            acc.add("SR", (f"{PLANET_AR[p]} في العودة الشمسية", f"{FACTOR_AR.get(nat_s, nat_s)} أصلي"),
                    pl_sr[p], natal.cusps[nat_s], fs * fp, 0.80, SR_ORB_MAJOR, SR_ORB_MINOR, MAJOR_ASPECTS)
    if "MOON" not in [x[0] for x in pls]:
        for nat_s, fs in sigs[:3]:
            acc.add("SR", ("قمر العودة الشمسية", f"{FACTOR_AR.get(nat_s, nat_s)} أصلي"),
                    pl_sr["MOON"], natal.cusps[nat_s], fs * 0.75, 0.75, SR_ORB_MAJOR, SR_ORB_MINOR, MAJOR_ASPECTS)


def evaluate_all_six_charts(
    eph: SwissEphemeris,
    natal: Natal,
    ev_jd: float,
    pl_tr: Dict[str, np.ndarray],
    spec: dict,
    techniques: Sequence[str] = TECH_CODES,
    explain: bool = False,
):
    acc = _NormalizedTechAcc(natal.jd.size, explain)
    days = ev_jd - natal.jd
    if "PD" in techniques:
        _run_pd(acc, natal, spec, days)
    if "SA" in techniques:
        _run_sa(eph, acc, natal, spec, days)
    if "SD" in techniques:
        _run_sd(eph, acc, natal, spec, days)
    if "AP" in techniques:
        _run_ap(eph, acc, natal, ev_jd, pl_tr, spec, days)
    if "TR" in techniques:
        _run_tr(eph, acc, natal, ev_jd, pl_tr, spec)
    if "SR" in techniques:
        _run_sr(eph, acc, natal, ev_jd, spec)

    pcts, avg_pct = acc.percentages(techniques)
    return pcts, avg_pct, sorted(acc.hits, key=lambda h: -h[7])


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


# ==============================================================================
# 5. خوارزمية التصحيح الكاملة (مسح كل 4 ثوانٍ + صقل 1 ثانية + عتبة 60%)
# ==============================================================================
def rectify_birth_time(
    eph: SwissEphemeris,
    birth_date: dt.date,
    lat: float,
    lon: float,
    to_utc: Callable[[dt.datetime], dt.datetime],
    event_kind: str,
    event_date: dt.date,
    event_period: str,  # "AM" (صباحًا) | "PM" (مساءً)
    gender: str,
    start_hour: int,
    start_minute: int = 0,
    span_hours: float = SPAN_HOURS,
    step_s: int = SCAN_STEP_SECONDS,
    techniques: Sequence[str] = TECH_CODES,
    threshold_pct: float = THRESHOLD_PERCENT,
) -> dict:
    locs, jd, offsets = make_candidates_sequential(
        birth_date, start_hour, start_minute, span_hours, step_s, to_utc
    )
    ev_hour = 9 if event_period == "AM" else 20
    ev_utc = to_utc(dt.datetime.combine(event_date, dt.time(ev_hour, 0)))
    ev_jd = jd_from_utc(ev_utc)
    pl_tr = eph.lons(np.array([ev_jd]))
    spec = resolve_spec(event_kind, gender)

    natal = build_natal(eph, jd, lat, lon)
    pcts, avg_pct, _ = evaluate_all_six_charts(eph, natal, ev_jd, pl_tr, spec, techniques, explain=False)

    # استخراج الذروات المحلية وفحصها بدقة 1 ثانية
    local_max = []
    for i in range(len(avg_pct)):
        cur = float(avg_pct[i])
        prv = float(avg_pct[i - 1]) if i > 0 else -1.0
        nxt = float(avg_pct[i + 1]) if i < len(avg_pct) - 1 else -1.0
        if cur >= prv and cur >= nxt:
            local_max.append((cur, i))
    local_max.sort(reverse=True)

    excl = max(1, int(round(90 / step_s)))
    seeds: List[int] = []
    for sc, i in local_max:
        if len(seeds) >= 12 and sc < threshold_pct - 6.0:
            break
        if len(seeds) >= 20:
            break
        if all(abs(i - s) > excl for s in seeds):
            seeds.append(i)

    half_win = max(step_s * 2, 20)
    span_sec = int(round(span_hours * 3600))
    refined: List[dict] = []

    for idx in sorted(seeds):
        center_off = offsets[idx]
        lo = max(0, center_off - half_win)
        hi = min(span_sec, center_off + half_win)
        fine_offs = list(range(lo, hi + 1))
        fine_locs = [locs[0] + dt.timedelta(seconds=s) for s in fine_offs]
        fine_jds = np.array([jd_from_utc(to_utc(x)) for x in fine_locs])
        fine_natal = build_natal(eph, fine_jds, lat, lon)
        _, f_avg, _ = evaluate_all_six_charts(eph, fine_natal, ev_jd, pl_tr, spec, techniques, explain=False)

        best_k = int(np.argmax(f_avg))
        best_off = fine_offs[best_k]
        if any(abs(r["offset_sec"] - best_off) < 75 for r in refined):
            continue

        # نقطة التفاصيل الدقيقة (1 ثانية)
        one_natal = build_natal(eph, np.array([fine_jds[best_k]]), lat, lon)
        one_pcts, one_avg, one_hits = evaluate_all_six_charts(
            eph, one_natal, ev_jd, pl_tr, spec, techniques, explain=True
        )
        avg_val = float(one_avg[0])
        tech_dict = {t: float(one_pcts[t][0]) for t in TECH_CODES}

        years = (ev_jd - float(fine_jds[best_k])) / TROPICAL_YEAR
        asc_sign_idx = int(one_natal.cusps["AS"][0] // 30) % 12
        prof_sign_idx = (asc_sign_idx + int(math.floor(years))) % 12

        refined.append({
            "offset_sec": best_off,
            "local_dt": fine_locs[best_k],
            "avg_percent": avg_val,
            "above_threshold": avg_val >= threshold_pct,
            "tech_percents": tech_dict,
            "asc_lon": float(one_natal.cusps["AS"][0]),
            "mc_lon": float(one_natal.cusps["MC"][0]),
            "pof_lon": float(one_natal.pof[0]),
            "asc_ruler": SIGN_RULERS[asc_sign_idx],
            "prof_sign_ar": SIGNS_AR[prof_sign_idx],
            "lord_of_year_ar": PLANET_AR[SIGN_RULERS[prof_sign_idx]],
            "natal": one_natal,
            "hits": one_hits,
        })

    qualified = sorted([r for r in refined if r["above_threshold"]], key=lambda x: -x["avg_percent"])
    diagnostic = sorted(refined, key=lambda x: -x["avg_percent"])[:5]

    return {
        "has_above_threshold": len(qualified) > 0,
        "threshold_percent": threshold_pct,
        "qualified": qualified,
        "diagnostic": diagnostic,
        "timeline_df": pd.DataFrame({
            "الوقت المحلي": [l.strftime("%H:%M:%S") for l in locs],
            "متوسط الخرائط الست (%)": np.round(avg_pct, 2),
            "درجة الطالع": [describe_lon(float(a)) for a in natal.cusps["AS"]],
        }),
        "max_avg_percent": float(np.max(avg_pct)),
        "start_dt": locs[0],
        "end_dt": locs[-1],
        "coarse_count": len(locs),
        # حقول إضافية تُستخدم في التقرير القابل للطباعة (لا تؤثر على الحساب)
        "all_candidates": sorted(refined, key=lambda x: -x["avg_percent"]),
        "ev_jd": float(ev_jd),
        "event_hour_assumed": int(ev_hour),
        "event_planets": {k: float(v[0]) for k, v in pl_tr.items()},
    }


# ==============================================================================
# 6. دائرة الزودياك SVG + تقرير HTML
# ==============================================================================
def render_zodiac_svg(natal: Natal, birth_str: str, name: str, avg_pct: float) -> str:
    cx, cy = 220, 220
    r_out, r_sign, r_in = 195, 165, 95
    asc = float(natal.cusps["AS"][0])

    def xy(lon: float, r: float):
        ang = math.radians(180.0 - ((lon - asc) % 360.0))
        return cx + r * math.cos(ang), cy + r * math.sin(ang)

    parts = [
        '<div dir="ltr" style="display:flex;justify-content:center;">',
        '<svg viewBox="0 0 440 440" width="420" height="420" style="background:#07090E;border-radius:12px;border:1px solid #1E293B;">',
        f'<circle cx="{cx}" cy="{cy}" r="{r_out}" fill="none" stroke="#334155" stroke-width="1.5"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r_sign}" fill="none" stroke="#334155" stroke-width="1"/>',
        f'<circle cx="{cx}" cy="{cy}" r="{r_in}" fill="#0B101B" stroke="#475569" stroke-width="1.5"/>',
    ]
    for i in range(12):
        x1, y1 = xy(i * 30.0, r_sign)
        x2, y2 = xy(i * 30.0, r_out)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155"/>')
        tx, ty = xy(i * 30.0 + 15.0, (r_out + r_sign) / 2.0)
        parts.append(f'<text x="{tx:.1f}" y="{ty+5:.1f}" text-anchor="middle" fill="#FBBF24" font-size="14">{SIGN_GLYPHS[i]}</text>')

    for h in ("AS", "H2", "H3", "IC", "H5", "H6", "DS", "H8", "H9", "MC", "H11", "H12"):
        lam = float(natal.cusps[h][0])
        is_ang = h in ("AS", "DS", "MC", "IC")
        x1, y1 = xy(lam, r_in)
        x2, y2 = xy(lam, r_sign)
        col = "#F59E0B" if is_ang else "#334155"
        w = "2" if is_ang else "1"
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{w}"/>')

    for p in PLANETS:
        lam = float(natal.pl[p][0])
        px, py = xy(lam, 132)
        parts.append(f'<text x="{px:.1f}" y="{py+5:.1f}" text-anchor="middle" fill="#38BDF8" font-size="14">{PLANET_GLYPH[p]}</text>')

    parts.append(f'<text x="{cx}" y="{cy-12}" text-anchor="middle" fill="#F8FAFC" font-size="12" font-weight="bold">{name}</text>')
    parts.append(f'<text x="{cx}" y="{cy+8}" text-anchor="middle" fill="#FBBF24" font-size="13" font-family="monospace">{birth_str}</text>')
    parts.append(f'<text x="{cx}" y="{cy+26}" text-anchor="middle" fill="#34D399" font-size="11">{avg_pct:.1f}%</text>')
    parts.append("</svg></div>")
    return "".join(parts)


# ==============================================================================
# 6-ب. دائرة الزودياك الاحترافية + منحنى المسح + التقرير القابل للطباعة (A4)
#      (إضافات جديدة بالكامل — لا تغيّر أي دالة حسابية أو تقييمية سابقة)
# ==============================================================================
HOUSE_ORDER = ("AS", "H2", "H3", "IC", "H5", "H6", "DS", "H8", "H9", "MC", "H11", "H12")
SYMBOL_FONTS = "'Segoe UI Symbol','Noto Sans Symbols 2','Noto Sans Symbols','Apple Symbols','DejaVu Sans',sans-serif"
TEXT_FONTS = "'Cairo','Tajawal','Segoe UI',Tahoma,sans-serif"
TECH_COLORS = {
    "PD": "#6366F1", "SA": "#0EA5E9", "SD": "#14B8A6",
    "AP": "#F59E0B", "TR": "#EC4899", "SR": "#8B5CF6",
}
TECH_DESC = {
    "PD": "تحريك الأوتاد والكواكب بقوس نيبود (≈ 59′08″ للسنة) في الاتجاهين المباشر والعكسي مع جدول الحركة (Speculum) على نظام توبوسنتريك.",
    "SA": "قوس = تقدّم الشمس الثانوية المقابلة لعمر الحدث؛ يُضاف إلى الأوتاد والكواكب الأصلية (بالقوس الموجب والعكسي).",
    "SD": "يوم مقابل سنة: مواقع الكواكب المتقدمة والمتراجعة وأوتاد الطالع المتقدمة بقوس المطالع المستقيمة للشمس.",
    "AP": "30° للسنة و30°/12 للشهر على الطالع والعاشر وسهم السعادة، مع رب السنة ورب بيت الحدث والعبور.",
    "TR": "مواقع الكواكب وقت الحدث (مباشرة وما قبل الولادة) مقارنةً بالأوتاد والبيوت الأصلية.",
    "SR": "خريطة العودة الشمسية لسنة الحدث (أوتادها وكواكبها وسهمها) مقارنةً بالخريطة الأصلية.",
}
TECH_ORB_TEXT = {
    "PD": f"±{PD_ORB_MAJOR:.0f}′ رئيسية / ±{PD_ORB_MINOR:.0f}′ ثانوية",
    "SA": f"±{SA_ORB_MAJOR:.0f}′ رئيسية / ±{SA_ORB_MINOR:.0f}′ ثانوية",
    "SD": "حسب الكوكب: القمر 36′/20′ · الشمس وعطارد والزهرة والمريخ 12′ · المشتري وزحل 9′ · الخارجية والعقدتان 5′",
    "AP": f"±{AP_ORB_MAJOR:.0f}′ رئيسية / ±{AP_ORB_MINOR:.0f}′ ثانوية · العبور ±{TR_ORB:.0f}′",
    "TR": f"±{TR_ORB:.0f}′ (زوايا رئيسية فقط)",
    "SR": f"±{SR_ORB_MAJOR:.0f}′ رئيسية / ±{SR_ORB_MINOR:.0f}′ ثانوية",
}

WHEEL_THEMES: Dict[str, Dict[str, str]] = {
    "dark": dict(
        bg="#070B16", ring="#334155", ring2="#475569", inner="#0B1224", sign="#FBBF24",
        text="#F8FAFC", muted="#94A3B8", planet="#7DD3FC", angle="#F59E0B", house="#243049",
        good="#34D399", hard="#F87171", band_op="0.13",
    ),
    "light": dict(
        bg="#FFFFFF", ring="#94A3B8", ring2="#64748B", inner="#F8FAFC", sign="#B45309",
        text="#0F172A", muted="#64748B", planet="#1D4ED8", angle="#B45309", house="#CBD5E1",
        good="#059669", hard="#DC2626", band_op="0.16",
    ),
}
ELEMENT_COLORS = ("#F97316", "#84CC16", "#38BDF8", "#A78BFA")  # نار · تراب · هواء · ماء (i % 4)


class _Raw(str):
    """نص HTML جاهز لا يُهرَّب عند وضعه داخل الجداول."""


def esc(x: Any) -> str:
    return html_lib.escape(str(x), quote=True)


def fmt_lon(lam: float) -> str:
    """نفس describe_lon لكن مع عزل اتجاهي (LTR) للأرقام كي لا تنقلب علامات ° ′ ″ داخل النص العربي."""
    num, sign = describe_lon(lam).split(" ", 1)
    return "\u2066" + num + "\u2069 " + sign


def sign_glyph_of(lam: float) -> str:
    return SIGN_GLYPHS[int((float(lam) % 360.0) // 30) % 12] + "︎"


def sign_name_of(lam: float) -> str:
    return SIGNS_AR[int((float(lam) % 360.0) // 30) % 12]


def planet_glyph_text(code: str) -> str:
    return PLANET_GLYPH.get(code, "") + "︎"


def natal_cusp_list(natal: Natal, idx: int = 0) -> List[float]:
    return [float(natal.cusps[k][idx]) for k in HOUSE_ORDER]


def house_of(lon: float, cusp_list: Sequence[float]) -> int:
    """رقم البيت (1-12) الذي يقع فيه خط الطول وفق رؤوس البيوت المحسوبة."""
    lon = float(lon) % 360.0
    for i in range(12):
        a = cusp_list[i]
        b = cusp_list[(i + 1) % 12]
        span = (b - a) % 360.0
        if span > 0 and (lon - a) % 360.0 < span:
            return i + 1
    return 1


def natal_aspects(lons: Dict[str, float], orb: float = 6.0,
                  aspects: Sequence[int] = (0, 60, 90, 120, 180)) -> List[Tuple[str, str, int, float]]:
    """الزوايا بين كواكب الخريطة (بدون عقدة جنوبية) مرتبة بالأضيق سماحًا."""
    codes = [p for p in PLANETS if p != "SN" and p in lons]
    out: List[Tuple[str, str, int, float]] = []
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            d = abs(lons[codes[i]] - lons[codes[j]]) % 360.0
            d = min(d, 360.0 - d)
            for a in aspects:
                o = abs(d - a)
                if o <= orb:
                    out.append((codes[i], codes[j], int(a), float(o)))
    out.sort(key=lambda t: t[3])
    return out


def _spread_longitudes(lons: Dict[str, float], min_sep: float = 9.0, iters: int = 120) -> Dict[str, float]:
    """تباعد مواضع رموز الكواكب المتقاربة على الدائرة حتى لا تتراكب."""
    items = sorted(((k, float(v) % 360.0) for k, v in lons.items()), key=lambda kv: kv[1])
    n = len(items)
    if n < 2:
        return {k: v for k, v in items}
    pos = [v for _, v in items]
    for _ in range(iters):
        moved = False
        for i in range(n):
            j = (i + 1) % n
            gap = (pos[j] - pos[i]) % 360.0
            if gap < min_sep:
                push = (min_sep - gap) / 2.0 + 0.01
                pos[i] = (pos[i] - push) % 360.0
                pos[j] = (pos[j] + push) % 360.0
                moved = True
        if not moved:
            break
    return {items[i][0]: pos[i] for i in range(n)}


def _deg_label(lam: float) -> str:
    lam = float(lam) % 30.0
    d = int(lam)
    m = int((lam - d) * 60)
    return f"{d}°{m:02d}′"


def render_zodiac_svg_pro(natal: Natal, birth_str: str, name: str, avg_pct: float,
                          theme: str = "dark", size: int = 560) -> str:
    """دائرة زودياك احترافية: عناصر الأبراج، تدريج الدرجات، أرقام البيوت، الزوايا بين الكواكب، الدرجات."""
    th = WHEEL_THEMES.get(theme, WHEEL_THEMES["dark"])
    cx = cy = 320.0
    r_out, r_sign, r_pl, r_deg, r_hn, r_in = 262.0, 222.0, 184.0, 158.0, 132.0, 118.0
    asc = float(natal.cusps["AS"][0])

    def xy(lon: float, r: float) -> Tuple[float, float]:
        ang = math.radians(180.0 - ((lon - asc) % 360.0))
        return cx + r * math.cos(ang), cy + r * math.sin(ang)

    def sector(a0: float, a1: float, r1: float, r2: float) -> str:
        x0, y0 = xy(a0, r2)
        x1, y1 = xy(a1, r2)
        x2, y2 = xy(a1, r1)
        x3, y3 = xy(a0, r1)
        return (f"M{x0:.1f},{y0:.1f} A{r2:.0f},{r2:.0f} 0 0 0 {x1:.1f},{y1:.1f} "
                f"L{x2:.1f},{y2:.1f} A{r1:.0f},{r1:.0f} 0 0 1 {x3:.1f},{y3:.1f} Z")

    p: List[str] = [
        '<div dir="ltr" style="display:flex;justify-content:center;">',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" width="{size}" height="{size}" '
        f'role="img" aria-label="دائرة الزودياك" '
        f'style="max-width:100%;height:auto;background:{th["bg"]};border-radius:14px;border:1px solid {th["ring"]};">',
    ]

    # حلقة الأبراج ملوّنة بحسب العنصر
    for i in range(12):
        p.append(
            f'<path d="{sector(i * 30.0, (i + 1) * 30.0, r_sign, r_out)}" fill="{ELEMENT_COLORS[i % 4]}" '
            f'fill-opacity="{th["band_op"]}" stroke="{th["ring"]}" stroke-width="1"/>'
        )
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r_out}" fill="none" stroke="{th["ring2"]}" stroke-width="1.6"/>')
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r_sign}" fill="none" stroke="{th["ring2"]}" stroke-width="1.2"/>')
    p.append(f'<circle cx="{cx}" cy="{cy}" r="{r_in}" fill="{th["inner"]}" stroke="{th["ring2"]}" stroke-width="1.4"/>')

    # رموز الأبراج
    for i in range(12):
        tx, ty = xy(i * 30.0 + 15.0, (r_out + r_sign) / 2.0)
        p.append(
            f'<text x="{tx:.1f}" y="{ty + 7:.1f}" text-anchor="middle" fill="{th["sign"]}" font-size="22" '
            f'font-family="{SYMBOL_FONTS}">{SIGN_GLYPHS[i]}&#xFE0E;</text>'
        )

    # تدريج الدرجات
    ticks = [f'<g stroke="{th["ring2"]}" stroke-width="0.8">']
    for d in range(360):
        ln = 10.0 if d % 10 == 0 else (6.0 if d % 5 == 0 else 3.0)
        x1, y1 = xy(float(d), r_sign)
        x2, y2 = xy(float(d), r_sign - ln)
        ticks.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    ticks.append("</g>")
    p.append("".join(ticks))

    # رؤوس البيوت وأرقامها
    cusp_vals = natal_cusp_list(natal)
    for i, h in enumerate(HOUSE_ORDER):
        lam = cusp_vals[i]
        is_ang = h in ("AS", "DS", "MC", "IC")
        x1, y1 = xy(lam, r_in)
        x2, y2 = xy(lam, r_out + (12.0 if is_ang else 0.0))
        p.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{th["angle"] if is_ang else th["house"]}" stroke-width="{2.2 if is_ang else 1}"/>'
        )
        nxt = cusp_vals[(i + 1) % 12]
        mid = lam + ((nxt - lam) % 360.0) / 2.0
        hx, hy = xy(mid, r_hn)
        p.append(
            f'<text x="{hx:.1f}" y="{hy + 4:.1f}" text-anchor="middle" fill="{th["muted"]}" '
            f'font-size="11" font-family="{TEXT_FONTS}">{i + 1}</text>'
        )
    for key, lab in (("AS", "AS"), ("DS", "DS"), ("MC", "MC"), ("IC", "IC")):
        lx, ly = xy(float(natal.cusps[key][0]), r_out + 26.0)
        p.append(
            f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="middle" fill="{th["angle"]}" '
            f'font-size="13" font-weight="bold" font-family="{TEXT_FONTS}">{lab}</text>'
        )

    # الزوايا بين الكواكب داخل الدائرة
    lons = {c: float(natal.pl[c][0]) for c in PLANETS}
    for a, b, asp, _o in natal_aspects(lons, orb=6.0, aspects=(60, 90, 120, 180)):
        x1, y1 = xy(lons[a], r_in - 1.0)
        x2, y2 = xy(lons[b], r_in - 1.0)
        col = th["good"] if asp in (60, 120) else th["hard"]
        p.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" '
            f'stroke-width="1" stroke-opacity="0.6"/>'
        )

    # الكواكب
    spread = _spread_longitudes(lons, 11.5)
    for c in PLANETS:
        tl = lons[c]
        sl = spread[c]
        tx1, ty1 = xy(tl, r_sign - 10.0)
        tx2, ty2 = xy(sl, r_pl + 14.0)
        p.append(
            f'<line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="{th["muted"]}" '
            f'stroke-width="0.6" stroke-opacity="0.7"/>'
        )
        dx, dy = xy(tl, r_in)
        p.append(f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="2.4" fill="{th["planet"]}"/>')
        gx, gy = xy(sl, r_pl)
        p.append(
            f'<text x="{gx:.1f}" y="{gy + 6:.1f}" text-anchor="middle" fill="{th["planet"]}" font-size="20" '
            f'font-family="{SYMBOL_FONTS}">{PLANET_GLYPH[c]}&#xFE0E;</text>'
        )
        lx, ly = xy(sl, r_deg)
        p.append(
            f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="middle" fill="{th["muted"]}" font-size="9.5" '
            f'font-family="{TEXT_FONTS}">{_deg_label(tl)}</text>'
        )

    # المركز
    short_name = name if len(name) <= 14 else name[:13] + "…"
    p.append(f'<circle cx="{cx}" cy="{cy}" r="52" fill="{th["inner"]}" fill-opacity="0.94" stroke="{th["ring"]}" stroke-width="1"/>')
    p.append(f'<text x="{cx}" y="{cy - 14}" text-anchor="middle" fill="{th["text"]}" font-size="12.5" font-weight="bold" font-family="{TEXT_FONTS}">{esc(short_name)}</text>')
    p.append(f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" fill="{th["sign"]}" font-size="14" font-family="monospace">{esc(birth_str)}</text>')
    p.append(f'<text x="{cx}" y="{cy + 24}" text-anchor="middle" fill="{th["good"]}" font-size="12" font-weight="bold" font-family="{TEXT_FONTS}">{avg_pct:.1f}%</text>')
    p.append("</svg></div>")
    return "".join(p)


def render_timeline_svg(avg_vals: Sequence[float], step_s: int, span_sec: int, start_dt: dt.datetime,
                        threshold: float, markers: Sequence[Tuple[int, float, str, bool]],
                        theme: str = "light", width: int = 760, height: int = 270) -> str:
    """منحنى متوسط الخرائط الست عبر نطاق الـ 3 ساعات مع خط العتبة وعلامات المرشحين."""
    th = WHEEL_THEMES.get(theme, WHEEL_THEMES["light"])
    pl_, pr_, pt_, pb_ = 44.0, 16.0, 16.0, 34.0
    w_in, h_in = width - pl_ - pr_, height - pt_ - pb_
    n = len(avg_vals)
    span = max(1, int(span_sec))

    def X(off: float) -> float:
        return pl_ + (off / span) * w_in

    def Y(v: float) -> float:
        return pt_ + (1.0 - max(0.0, min(100.0, v)) / 100.0) * h_in

    pts = " ".join(f"{X(min(i * step_s, span)):.1f},{Y(float(v)):.1f}" for i, v in enumerate(avg_vals))
    area = f"{X(0):.1f},{Y(0):.1f} " + pts + f" {X(span):.1f},{Y(0):.1f}"
    s: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
        f'style="max-width:100%;height:auto;direction:ltr" role="img" aria-label="منحنى المسح التسلسلي">',
        '<defs><linearGradient id="tlgrad" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#6366F1" stop-opacity="0.35"/>'
        '<stop offset="100%" stop-color="#6366F1" stop-opacity="0.02"/></linearGradient></defs>',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{th["bg"]}" rx="8"/>',
    ]
    for v in range(0, 101, 20):
        s.append(f'<line x1="{pl_}" y1="{Y(v):.1f}" x2="{width - pr_}" y2="{Y(v):.1f}" stroke="{th["house"]}" stroke-width="0.8"/>')
        s.append(f'<text x="{pl_ - 6}" y="{Y(v) + 3.5:.1f}" text-anchor="end" font-size="10" fill="{th["muted"]}" font-family="{TEXT_FONTS}">{v}%</text>')
    for k in range(7):
        off = span * k / 6.0
        t_lab = (start_dt + dt.timedelta(seconds=off)).strftime("%H:%M")
        s.append(f'<line x1="{X(off):.1f}" y1="{pt_}" x2="{X(off):.1f}" y2="{pt_ + h_in}" stroke="{th["house"]}" stroke-width="0.5" stroke-dasharray="2 3"/>')
        s.append(f'<text x="{X(off):.1f}" y="{height - 12}" text-anchor="middle" font-size="10" fill="{th["muted"]}" font-family="{TEXT_FONTS}">{t_lab}</text>')
    s.append(f'<polygon points="{area}" fill="url(#tlgrad)"/>')
    s.append(f'<polyline points="{pts}" fill="none" stroke="#4F46E5" stroke-width="1.4" stroke-linejoin="round"/>')
    s.append(f'<line x1="{pl_}" y1="{Y(threshold):.1f}" x2="{width - pr_}" y2="{Y(threshold):.1f}" stroke="{th["hard"]}" stroke-width="1.2" stroke-dasharray="6 4"/>')
    s.append(f'<text x="{pl_ + 6}" y="{Y(threshold) - 5:.1f}" text-anchor="start" font-size="10.5" font-weight="bold" fill="{th["hard"]}" font-family="{TEXT_FONTS}">{threshold:.0f}%</text>')
    s.append(f'<text x="{pl_ + 36}" y="{Y(threshold) - 5:.1f}" text-anchor="start" font-size="10.5" font-weight="bold" fill="{th["hard"]}" font-family="{TEXT_FONTS}">عتبة القبول</text>')
    for off, v, lab, ok in markers:
        col = th["good"] if ok else th["muted"]
        s.append(f'<circle cx="{X(off):.1f}" cy="{Y(v):.1f}" r="4.2" fill="{col}" stroke="{th["bg"]}" stroke-width="1.5"/>')
        s.append(f'<text x="{X(off):.1f}" y="{Y(v) - 8:.1f}" text-anchor="middle" font-size="10" font-weight="bold" fill="{col}" font-family="{TEXT_FONTS}">{esc(lab)}</text>')
    s.append("</svg>")
    return "".join(s)


def _candidate_list(res: dict) -> List[dict]:
    """كل المرشحين المصقولين (أو المعتمدين + التشخيصيين عند غياب القائمة الكاملة) دون تكرار."""
    base = res.get("all_candidates") or (list(res.get("qualified", [])) + list(res.get("diagnostic", [])))
    seen: List[int] = []
    out: List[dict] = []
    for c in sorted(base, key=lambda x: -x["avg_percent"]):
        if c["offset_sec"] in seen:
            continue
        seen.append(c["offset_sec"])
        out.append(c)
    return out


def hits_rows(hits: Sequence[tuple]) -> List[dict]:
    return [
        {
            "الخريطة": h[1],
            "الدليل الموجه": h[2],
            "الزاوية": f"{h[5]} ({h[4]}°)",
            "النقطة الأصلية": h[3],
            "الفارق (دقيقة قوسية)": round(h[6], 2),
            "القوة": round(h[7], 2),
        }
        for h in hits
    ]


def planets_rows(natal: Natal, cusp_list: Sequence[float]) -> List[dict]:
    rows = []
    for c in PLANETS:
        lam = float(natal.pl[c][0])
        rows.append({
            "الرمز": planet_glyph_text(c),
            "الكوكب": PLANET_AR[c],
            "الموضع": fmt_lon(lam),
            "البرج": sign_name_of(lam),
            "حاكم البرج": PLANET_AR[SIGN_RULERS[int(lam // 30) % 12]],
            "البيت": house_of(lam, cusp_list),
            "الطول الكامل (°)": round(lam, 4),
        })
    return rows


def houses_rows(natal: Natal) -> List[dict]:
    rows = []
    for i, k in enumerate(HOUSE_ORDER):
        lam = float(natal.cusps[k][0])
        rows.append({
            "البيت": i + 1,
            "الرأس": FACTOR_AR.get(k, k),
            "الموضع": fmt_lon(lam),
            "البرج": sign_name_of(lam),
            "حاكم البرج": PLANET_AR[SIGN_RULERS[int(lam // 30) % 12]],
            "الطول الكامل (°)": round(lam, 4),
        })
    return rows


def points_rows(natal: Natal) -> List[dict]:
    rows = []
    for k in ("EP", "POF", "POS"):
        lam = float(natal.cusps[k][0])
        rows.append({
            "النقطة": FACTOR_AR.get(k, k),
            "الموضع": fmt_lon(lam),
            "البرج": sign_name_of(lam),
            "الطول الكامل (°)": round(lam, 4),
        })
    return rows


def candidates_rows(res: dict) -> List[dict]:
    rows = []
    for i, c in enumerate(_candidate_list(res), 1):
        row = {
            "#": i,
            "الوقت المحلي": c["local_dt"].strftime("%H:%M:%S"),
            "الطالع": fmt_lon(c["asc_lon"]),
            "وتد السماء MC": fmt_lon(c["mc_lon"]),
            "المتوسط (%)": round(c["avg_percent"], 1),
            "الحالة": "معتمد" if c["above_threshold"] else "غير معتمد",
        }
        for t in TECH_CODES:
            row[t] = round(c["tech_percents"][t], 1)
        rows.append(row)
    return rows


# ------------------------------------------------------------------------------
# التقرير القابل للطباعة
# ------------------------------------------------------------------------------
REPORT_CSS = """
@page{size:A4;margin:11mm 10mm 15mm;@bottom-center{content:"صفحة " counter(page) " من " counter(pages);font-size:9px;color:#64748B}}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#E6EAF2;color:#0F172A;font-family:'Cairo','Tajawal','Segoe UI',Tahoma,sans-serif;font-size:13px;line-height:1.7;direction:rtl}
.toolbar{position:sticky;top:0;z-index:30;display:flex;flex-wrap:wrap;gap:10px;justify-content:center;align-items:center;padding:10px 12px;background:rgba(11,17,36,.94);backdrop-filter:blur(6px)}
.toolbar button{font-family:inherit;font-weight:800;font-size:13px;border:0;border-radius:10px;padding:9px 20px;cursor:pointer;background:linear-gradient(135deg,#FBD38D,#F5B942 55%,#F59E0B);color:#1B1300;box-shadow:0 4px 14px rgba(245,185,66,.35)}
.toolbar button:hover{filter:brightness(1.06)}
.toolbar .hint{color:#B6C2DC;font-size:12px}
.paper{width:210mm;max-width:100%;margin:18px auto 30px;background:#fff;padding:12mm 12mm 12mm;box-shadow:0 14px 44px rgba(15,23,42,.20);border-radius:8px}
.rp-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 18px;border-radius:12px;color:#fff;background:linear-gradient(120deg,#0B1124 0%,#1B1F4B 55%,#2B2A6B 100%);position:relative;overflow:hidden}
.rp-head:after{content:"";position:absolute;inset:0;background:radial-gradient(260px 120px at 12% 0%,rgba(245,185,66,.28),transparent 70%)}
.rp-head>*{position:relative;z-index:1}
.rp-brand{display:flex;align-items:center;gap:10px}
.rp-brand .logo{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-size:22px;color:#1B1300;background:linear-gradient(135deg,#FBD38D,#F59E0B)}
.rp-brand .b1{font-weight:800;font-size:15px;line-height:1.2}
.rp-brand .b2{font-size:10px;letter-spacing:.22em;color:#C7D2FE}
.rp-title{text-align:center;flex:1}
.rp-title h1{margin:0;font-size:21px;font-weight:800;letter-spacing:.2px}
.rp-title p{margin:2px 0 0;font-size:11px;color:#C7D2FE}
.rp-meta{font-size:11px;color:#C7D2FE;text-align:left;direction:ltr;line-height:1.55}
.rp-meta b{color:#FBD38D;font-weight:700}
.verdict{margin:14px 0 6px;padding:14px 18px;border-radius:12px;display:flex;align-items:center;justify-content:space-between;gap:14px;border:1px solid}
.verdict.ok{background:#ECFDF5;border-color:#6EE7B7}
.verdict.bad{background:#FEF2F2;border-color:#FCA5A5}
.verdict .vt{font-weight:800;font-size:15px}
.verdict.ok .vt{color:#047857}
.verdict.bad .vt{color:#B91C1C}
.verdict .vs{font-size:12px;color:#475569}
.verdict .big{font-family:'DejaVu Sans Mono',Consolas,monospace;font-weight:800;font-size:30px;letter-spacing:1px;direction:ltr;color:#0F172A}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px 0 4px}
.kpi{border:1px solid #E2E8F0;border-radius:10px;padding:9px 12px;background:#F8FAFC;break-inside:avoid}
.kpi .l{font-size:10.5px;color:#64748B}
.kpi .v{font-weight:800;font-size:14.5px;color:#0F172A}
.sec{margin-top:16px}
.sec h2{display:flex;align-items:center;gap:9px;margin:0 0 8px;font-size:15.5px;font-weight:800;color:#1E1B4B;padding-bottom:6px;border-bottom:2px solid #E0E7FF;break-after:avoid}
.sec h2 .n{display:inline-grid;place-items:center;min-width:24px;height:24px;border-radius:7px;font-size:12px;color:#fff;background:linear-gradient(135deg,#4F46E5,#7C3AED)}
.sec h3{margin:12px 0 6px;font-size:13px;font-weight:800;color:#334155;break-after:avoid}
.sec p.note{margin:4px 0 8px;color:#475569;font-size:12px}
.pb{break-before:page}
.kv{display:grid;grid-template-columns:repeat(2,1fr);gap:0 18px}
.kv .r{display:flex;justify-content:space-between;gap:10px;padding:6px 2px;border-bottom:1px dashed #E2E8F0;break-inside:avoid}
.kv .r span{color:#64748B}
.kv .r b{font-weight:700;color:#0F172A;text-align:left}
.tbl{width:100%;border-collapse:collapse;font-size:11.5px}
.tbl th{background:#EEF2FF;color:#312E81;font-weight:800;padding:6px 8px;border:1px solid #E0E7FF;text-align:right;white-space:nowrap}
.tbl td{padding:5px 8px;border:1px solid #E5E9F2;text-align:right;vertical-align:middle}
.tbl tbody tr:nth-child(even) td{background:#F8FAFC}
.tbl thead{display:table-header-group}
.tbl tr{break-inside:avoid}
.tbl .g{font-family:'Segoe UI Symbol','Noto Sans Symbols 2','Noto Sans Symbols','DejaVu Sans',sans-serif;font-size:15px;color:#1D4ED8;text-align:center}
.tbl .nw{white-space:nowrap}
.tbl.sm{font-size:10.5px}
.tbl.sm th,.tbl.sm td{padding:4px 5px}
.tbl .num{font-family:'DejaVu Sans Mono',Consolas,monospace;direction:ltr;text-align:left}
.tbl tr.best td{background:#ECFDF5!important;font-weight:700}
.badge{white-space:nowrap;display:inline-block;padding:1px 9px;border-radius:99px;font-size:10.5px;font-weight:800}
.badge.ok{background:#D1FAE5;color:#047857}
.badge.bad{background:#FEE2E2;color:#B91C1C}
.bars .row{display:grid;grid-template-columns:230px 1fr 58px;align-items:center;gap:10px;margin:7px 0;break-inside:avoid}
.bars .lab{font-weight:700;font-size:12px}
.bars .trk{height:13px;border-radius:99px;background:#EEF2FF;position:relative;overflow:hidden}
.bars .fil{height:100%;border-radius:99px}
.bars .thr{position:absolute;top:-2px;bottom:-2px;width:2px;background:#DC2626}
.bars .pct{font-weight:800;font-family:'DejaVu Sans Mono',Consolas,monospace;direction:ltr;text-align:left}
.bars .row.avg .lab{color:#312E81}
.bars .row.avg .trk{height:17px}
.keep,.twocol{break-inside:avoid}
.twocol{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:16px;align-items:start}
.card{border:1px solid #E2E8F0;border-radius:12px;padding:10px 12px;background:#fff;break-inside:avoid}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:11px;color:#475569;margin-top:6px}
.legend i{display:inline-block;width:18px;height:3px;border-radius:2px;vertical-align:middle;margin-left:5px}
.legend .el{display:inline-block;width:10px;height:10px;border-radius:3px;margin-left:5px;vertical-align:middle}
.method{display:grid;grid-template-columns:1fr;gap:6px}
.disclaimer{margin-top:14px;padding:10px 14px;border-radius:10px;background:#FFFBEB;border:1px solid #FDE68A;color:#92400E;font-size:11.5px;break-inside:avoid}
.rp-foot{margin-top:16px;padding-top:8px;border-top:1px solid #E2E8F0;display:flex;justify-content:space-between;font-size:10.5px;color:#64748B}
@media print{
 body{background:#fff}
 .toolbar{display:none!important}
 .paper{width:auto;margin:0;padding:0;box-shadow:none;border-radius:0}
}
@media (max-width:760px){
 .paper{padding:12px}
 .kpis{grid-template-columns:repeat(2,1fr)}
 .twocol,.kv{grid-template-columns:1fr}
 .bars .row{grid-template-columns:1fr 50px}
 .bars .lab{grid-column:1/-1}
 .rp-head{flex-direction:column;text-align:center}
 .rp-meta{text-align:center}
 .verdict{flex-direction:column;text-align:center}
}
"""


def _html_table(headers: Sequence[str], rows: Sequence[Sequence[Any]], cls: str = "tbl",
                col_cls: Optional[Sequence[str]] = None, row_cls: Optional[Sequence[str]] = None) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body: List[str] = []
    for ri, row in enumerate(rows):
        tds = []
        for ci, c in enumerate(row):
            cc = f' class="{col_cls[ci]}"' if col_cls and col_cls[ci] else ""
            tds.append(f"<td{cc}>{c if isinstance(c, _Raw) else esc(c)}</td>")
        rc = f' class="{row_cls[ri]}"' if row_cls and row_cls[ri] else ""
        body.append(f"<tr{rc}>" + "".join(tds) + "</tr>")
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def _bar_row(label: str, pct: float, color: str, thr: Optional[float] = None, extra_cls: str = "") -> str:
    thr_html = f'<div class="thr" style="right:calc({thr:.1f}% - 1px)"></div>' if thr is not None else ""
    return (
        f'<div class="row {extra_cls}"><div class="lab">{esc(label)}</div>'
        f'<div class="trk"><div class="fil" style="width:{max(0.0, min(100.0, pct)):.1f}%;background:{color}"></div>{thr_html}</div>'
        f'<div class="pct">{pct:.1f}%</div></div>'
    )


def build_printable_report_html(res: dict, meta: Optional[dict] = None) -> str:
    """تقرير HTML مستقل (A4) جاهز للطباعة أو الحفظ PDF ويحوي كل مخرجات التصحيح."""
    meta = dict(meta or {})
    accepted = bool(res.get("has_above_threshold"))
    best = res["qualified"][0] if accepted else (res["diagnostic"][0] if res.get("diagnostic") else None)
    if best is None:
        return "<!doctype html><meta charset='utf-8'><body dir='rtl'>لا توجد نتائج لعرضها.</body>"

    natal: Natal = best["natal"]
    cusp_list = natal_cusp_list(natal)
    thr = float(res.get("threshold_percent", THRESHOLD_PERCENT))
    name = str(meta.get("name", "—"))
    best_time = best["local_dt"].strftime("%H:%M:%S")
    gender_code = meta.get("gender", "M")
    event_kind = meta.get("event_kind", "—")
    now_utc = dt.datetime.now(dt.timezone.utc)
    rid = hashlib.sha1(
        (repr(sorted((k, str(v)) for k, v in meta.items())) + best_time).encode("utf-8")
    ).hexdigest()[:8].upper()
    step_s = int(meta.get("step_s", SCAN_STEP_SECONDS))
    span_sec = int(round((res["end_dt"] - res["start_dt"]).total_seconds()))

    age_txt = "—"
    if res.get("ev_jd") is not None:
        age = (float(res["ev_jd"]) - float(natal.jd[0])) / TROPICAL_YEAR
        age_txt = f"{int(age)} سنة و {int((age % 1.0) * 12)} شهرًا ({age:.2f} سنة)"

    cands = _candidate_list(res)
    qualified = res.get("qualified", [])
    hits = list(best.get("hits", []))
    counter = {"n": 0}

    def section(title: str, body: str, page_break: bool = False) -> str:
        counter["n"] += 1
        cls = "sec pb" if page_break else "sec"
        return f'<section class="{cls}"><h2><span class="n">{counter["n"]}</span>{esc(title)}</h2>{body}</section>'

    parts: List[str] = []

    # ---------------- الترويسة + الحكم ----------------
    parts.append(
        '<header class="rp-head">'
        '<div class="rp-brand"><div class="logo">✦</div><div><div class="b1">أسترو رادار</div><div class="b2">ASTRO RADAR</div></div></div>'
        f'<div class="rp-title"><h1>تقرير تصحيح الطالع ودرجته</h1><p>{esc(APP_TITLE)}</p></div>'
        f'<div class="rp-meta">REPORT <b>#{rid}</b><br>{now_utc:%Y-%m-%d %H:%M} UTC<br>v2.0</div>'
        "</header>"
    )
    if accepted:
        narrative = (
            f"تم قبول الحدث «{esc(event_kind)}» بعد مسح تسلسلي لنطاق {res['start_dt']:%H:%M:%S} ← {res['end_dt']:%H:%M:%S}. "
            f"عدد المرشحين المعتمدين: {len(qualified)}."
        )
        if len(qualified) > 1:
            gap = qualified[0]["avg_percent"] - qualified[1]["avg_percent"]
            narrative += f" الفارق بين أول مرشحين {gap:.1f} نقطة مئوية؛ يُنصح بحدث إضافي للتأكيد."
        parts.append(
            '<div class="verdict ok"><div>'
            '<div class="vt">✔ تم قبول الحدث وتحديد ساعة الميلاد</div>'
            f'<div class="vs">{narrative}</div></div>'
            f'<div class="big">{best_time}</div></div>'
        )
    else:
        parts.append(
            '<div class="verdict bad"><div>'
            '<div class="vt">✖ تم رفض الحدث — النتيجة تشخيصية وغير معتمدة</div>'
            f'<div class="vs">أعلى متوسط للخرائط الست بلغ {res.get("max_avg_percent", 0):.1f}% وهو أقل من عتبة القبول '
            f'({thr:.1f}%). يُرجى إدخال حدث حاسم آخر. أقرب ذروة تشخيصية موضّحة أدناه.</div></div>'
            f'<div class="big">{best_time}</div></div>'
        )
    parts.append(
        '<div class="kpis">'
        f'<div class="kpi"><div class="l">الطالع AS</div><div class="v">{esc(fmt_lon(best["asc_lon"]))}</div></div>'
        f'<div class="kpi"><div class="l">وتد السماء MC</div><div class="v">{esc(fmt_lon(best["mc_lon"]))}</div></div>'
        f'<div class="kpi"><div class="l">سهم السعادة POF</div><div class="v">{esc(fmt_lon(best["pof_lon"]))}</div></div>'
        f'<div class="kpi"><div class="l">متوسط الخرائط الست</div><div class="v">{best["avg_percent"]:.1f}%</div></div>'
        "</div>"
    )

    # ---------------- 1. معطيات الإدخال ----------------
    def kv(items: Sequence[Tuple[str, Any]]) -> str:
        return '<div class="kv">' + "".join(f'<div class="r"><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in items) + "</div>"

    bd = meta.get("birth_date")
    ed = meta.get("event_date")
    inputs_html = kv([
        ("اسم المولود", name),
        ("الجنس", meta.get("gender_ar", "—")),
        ("تاريخ الميلاد", bd.strftime("%Y-%m-%d") if hasattr(bd, "strftime") else "—"),
        ("نطاق البحث (3 ساعات)", f"{res['start_dt']:%H:%M:%S} ← {res['end_dt']:%H:%M:%S}"),
        ("مكان الميلاد", meta.get("loc_label", "—")),
        ("الإحداثيات", f"{float(meta.get('lat', 0)):.4f}° ، {float(meta.get('lon', 0)):.4f}°"),
        ("المنطقة الزمنية", meta.get("tz_name", "—")),
        ("نوع الحدث الحاسم", event_kind),
        ("تاريخ الحدث", ed.strftime("%Y-%m-%d") if hasattr(ed, "strftime") else "—"),
        ("فترة الحدث", meta.get("event_period_ar", "—")),
        ("العمر عند الحدث", age_txt),
        ("ساعة الحدث المعتمدة حسابيًا", f"{int(res.get('event_hour_assumed', 9)):02d}:00 محلي"),
    ])
    settings_html = kv([
        ("نظام البيوت", "توبوسنتريك (Polich-Page)"),
        ("دقة المسح الأولي", f"كل {step_s} ثوانٍ ({res.get('coarse_count', len(res['timeline_df']))} نقطة)"),
        ("الصقل الدقيق", "1 ثانية حول كل ذروة"),
        ("عتبة قبول الحدث", f"≥ {thr:.1f}%"),
        ("الأفيمريس", meta.get("eph_mode", "Swiss Ephemeris")),
        ("زمن المعالجة", f"{meta['elapsed']:.1f} ثانية" if meta.get("elapsed") is not None else "—"),
    ])
    parts.append(section("معطيات الإدخال وإعدادات الخوارزمية", inputs_html + '<h3>إعدادات المسح</h3>' + settings_html))

    # ---------------- 2. نتيجة الخرائط الست ----------------
    bars = "".join(
        _bar_row(TECH_AR[t], best["tech_percents"][t], TECH_COLORS[t], thr) for t in TECH_CODES
    ) + _bar_row("المتوسط العام للخرائط الست", best["avg_percent"], "linear-gradient(90deg,#4F46E5,#7C3AED)", thr, "avg")
    n_by_t = {t: sum(1 for h in hits if h[0] == t) for t in TECH_CODES}
    top_by_t: Dict[str, tuple] = {}
    for h in hits:  # مرتبة تنازليًا بالقوة
        top_by_t.setdefault(h[0], h)
    rows = []
    for t in TECH_CODES:
        th_ = top_by_t.get(t)
        rows.append([
            TECH_AR[t], f"{best['tech_percents'][t]:.1f}%", n_by_t[t],
            f"{th_[2]} ⟷ {th_[3]} ({th_[5]}، {th_[6]:.2f}′)" if th_ else "—",
        ])
    tech_tbl = _html_table(["الخريطة", "النسبة", "عدد التطابقات", "أقوى تطابق"], rows, col_cls=["", "num", "num", ""])
    parts.append(section(
        "نتيجة الخرائط الست",
        f'<p class="note">الخط الأحمر في الأشرطة يمثل عتبة القبول ({thr:.0f}%).</p><div class="bars">{bars}</div>'
        f'<h3>ملخص التطابقات لكل خريطة</h3>{tech_tbl}',
    ))

    # ---------------- 3. دائرة الزودياك ----------------
    wheel = render_zodiac_svg_pro(natal, best_time, name, best["avg_percent"], theme="light", size=470)
    ang_rows = []
    for k in ("AS", "DS", "MC", "IC"):
        lam = float(natal.cusps[k][0])
        ang_rows.append([FACTOR_AR[k], _Raw(f'<span class="g">{sign_glyph_of(lam)}</span> {esc(fmt_lon(lam))}')])
    side = (
        '<div class="card"><h3 style="margin-top:0">الأوتاد</h3>'
        + _html_table(["الوتد", "الموضع"], ang_rows)
        + "</div>"
        '<div class="card" style="margin-top:10px">'
        + kv([
            ("حاكم الطالع", PLANET_AR[best["asc_ruler"]]),
            ("برج الانتهاء السنوي", best["prof_sign_ar"]),
            ("رب السنة", best["lord_of_year_ar"]),
            ("ساعة الميلاد", best_time),
            ("الطالع", sign_name_of(best["asc_lon"])),
            ("وضع النهار/الليل", "نهاري" if bool(natal.is_day[0]) else "ليلي"),
        ]).replace('class="kv"', 'class="kv" style="grid-template-columns:1fr"')
        + "</div>"
        '<div class="legend">'
        f'<span><i style="background:{WHEEL_THEMES["light"]["good"]}"></i>تسديس / تثليث</span>'
        f'<span><i style="background:{WHEEL_THEMES["light"]["hard"]}"></i>تربيع / مقابلة</span>'
        f'<span><b class="el" style="background:{ELEMENT_COLORS[0]}"></b>نار</span>'
        f'<span><b class="el" style="background:{ELEMENT_COLORS[1]}"></b>تراب</span>'
        f'<span><b class="el" style="background:{ELEMENT_COLORS[2]}"></b>هواء</span>'
        f'<span><b class="el" style="background:{ELEMENT_COLORS[3]}"></b>ماء</span></div>'
    )
    parts.append(section("دائرة الزودياك (الخريطة الأصلية المصححة)", f'<div class="twocol"><div>{wheel}</div><div>{side}</div></div>'))

    # ---------------- 4. مواقع الكواكب ----------------
    p_rows = planets_rows(natal, cusp_list)
    parts.append(section(
        "مواقع الكواكب في الخريطة الأصلية",
        _html_table(
            ["", "الكوكب", "الموضع", "البرج", "حاكم البرج", "البيت", "الطول الكامل (°)"],
            [[r["الرمز"], r["الكوكب"], r["الموضع"], r["البرج"], r["حاكم البرج"], r["البيت"], f"{r['الطول الكامل (°)']:.4f}"] for r in p_rows],
            col_cls=["g", "", "", "", "", "num", "num"],
        ),
    ))

    # ---------------- 5. البيوت والأسهم ----------------
    h_rows = houses_rows(natal)
    pt_rows = points_rows(natal)
    parts.append(section(
        "رؤوس البيوت (توبوسنتريك) والنقاط الحساسة",
        _html_table(
            ["البيت", "الرأس", "الموضع", "البرج", "حاكم البرج", "الطول الكامل (°)"],
            [[r["البيت"], r["الرأس"], r["الموضع"], r["البرج"], r["حاكم البرج"], f"{r['الطول الكامل (°)']:.4f}"] for r in h_rows],
            col_cls=["num", "", "", "", "", "num"],
        )
        + "<h3>النقطة الشرقية والسهام العربية</h3>"
        + _html_table(
            ["النقطة", "الموضع", "البرج", "الطول الكامل (°)"],
            [[r["النقطة"], r["الموضع"], r["البرج"], f"{r['الطول الكامل (°)']:.4f}"] for r in pt_rows],
            col_cls=["", "", "", "num"],
        ),
    ))

    # ---------------- 6. الزوايا الميلادية ----------------
    lons_n = {c: float(natal.pl[c][0]) for c in PLANETS}
    na = natal_aspects(lons_n, orb=6.0)
    na_rows = [
        [f"{planet_glyph_text(a)} {PLANET_AR[a]}", ASPECT_AR.get(asp, f"{asp}°") + f" ({asp}°)", f"{planet_glyph_text(b)} {PLANET_AR[b]}", f"{o:.2f}°"]
        for a, b, asp, o in na
    ]
    parts.append(section(
        "الزوايا بين الكواكب في الخريطة الأصلية",
        (_html_table(["الكوكب الأول", "الزاوية", "الكوكب الثاني", "السماحية"], na_rows, col_cls=["", "", "", "num"])
         if na_rows else '<p class="note">لا توجد زوايا رئيسية ضمن 6° في هذه الخريطة.</p>')
        + '<p class="note">الزوايا المعروضة: اقتران، تسديس، تربيع، تثليث، مقابلة (سماحية حتى 6°).</p>',
    ))

    # ---------------- 7. الكواكب العابرة وقت الحدث ----------------
    ev_pl = res.get("event_planets") or {}
    if ev_pl:
        tr_rows = []
        for c in PLANETS:
            if c in ev_pl:
                lam = float(ev_pl[c])
                tr_rows.append([planet_glyph_text(c), PLANET_AR[c], fmt_lon(lam), sign_name_of(lam), house_of(lam, cusp_list)])
        parts.append(section(
            "مواقع الكواكب العابرة وقت الحدث",
            '<p class="note">البيت محسوب على رؤوس بيوت الخريطة المصححة.</p>'
            + _html_table(["", "الكوكب", "الموضع", "البرج", "البيت"], tr_rows, col_cls=["g", "", "", "", "num"]),
        ))

    # ---------------- 8. دلائل الحدث المعتمدة ----------------
    spec = resolve_spec(event_kind, gender_code)
    sigs_l, pls_l = _get_lists(spec)
    sig_rows = [[FACTOR_AR.get(s, s), f"{w:.2f}"] for s, w in sigs_l]
    pl_rows_ = [[f"{planet_glyph_text(p_)} {PLANET_AR[p_]}", f"{w:.2f}"] for p_, w in pls_l]
    parts.append(section(
        "دلائل الحدث المعتمدة في الحساب",
        f'<p class="note">الحدث: <b>{esc(event_kind)}</b> — الجنس: {esc(meta.get("gender_ar", "—"))}. '
        "يُضاف تلقائيًا EP (0.55) وPOF (0.65) إن لم يكونا ضمن القائمة.</p>"
        '<div class="twocol"><div>'
        + _html_table(["المؤشر (الوتد/البيت/النقطة)", "الوزن"], sig_rows, col_cls=["", "num"])
        + "</div><div>"
        + _html_table(["الكوكب الدليل", "الوزن"], pl_rows_, col_cls=["", "num"])
        + "</div></div>"
        + (f'<p class="note">بيوت الحدث: {" ، ".join(str(x) for x in spec.get("houses", []))}</p>'),
    ))

    # ---------------- 9. منحنى المسح ----------------
    avg_vals = [float(v) for v in res["timeline_df"]["متوسط الخرائط الست (%)"].tolist()]
    markers = [
        (int(c["offset_sec"]), float(c["avg_percent"]), str(i), bool(c["above_threshold"]))
        for i, c in enumerate(cands, 1)
    ]
    tl_svg = render_timeline_svg(avg_vals, step_s, span_sec, res["start_dt"], thr, markers, theme="light")
    parts.append(section(
        "منحنى المسح التسلسلي",
        f'<p class="note">متوسط الخرائط الست لكل لحظة ميلاد مرشحة (كل {step_s} ثوانٍ). الدوائر المرقمة تمثل المرشحين المصقولين '
        f'(الخضراء = معتمد). أعلى متوسط بلغ {res.get("max_avg_percent", 0):.1f}%.</p><div class="keep">{tl_svg}</div>',
    ))

    # ---------------- 10. المرشحون ----------------
    c_rows: List[List[Any]] = []
    c_cls: List[str] = []
    for i, c in enumerate(cands, 1):
        status = _Raw('<span class="badge ok">معتمد</span>') if c["above_threshold"] else _Raw('<span class="badge bad">غير معتمد</span>')
        c_rows.append([
            i, c["local_dt"].strftime("%H:%M:%S"), fmt_lon(c["asc_lon"]), fmt_lon(c["mc_lon"]),
            f"{c['avg_percent']:.1f}%", status,
        ] + [f"{c['tech_percents'][t]:.1f}" for t in TECH_CODES])
        c_cls.append("best" if c is best else "")
    parts.append(section(
        "المرشحون بعد الصقل الدقيق (1 ثانية)",
        _html_table(
            ["#", "الوقت المحلي", "الطالع", "MC", "المتوسط", "الحالة"] + list(TECH_CODES),
            c_rows, cls="tbl sm", col_cls=["num", "num", "nw", "nw", "num", "nw", "num", "num", "num", "num", "num", "num"], row_cls=c_cls,
        ) + '<p class="note">الصف المظلل هو المرشح الأفضل المعتمد في هذا التقرير.</p>',
    ))

    # ---------------- 11. كل التطابقات ----------------
    if hits:
        hb: List[str] = [f'<p class="note">إجمالي التطابقات للمرشح الأفضل: <b>{len(hits)}</b> (مرتبة بالقوة داخل كل خريطة).</p>']
        for t in TECH_CODES:
            hs = [h for h in hits if h[0] == t]
            if not hs:
                continue
            hb.append(f'<h3 style="color:{TECH_COLORS[t]}">{esc(TECH_AR[t])} — {len(hs)} تطابقًا</h3>')
            hb.append(_html_table(
                ["#", "الدليل الموجه", "الزاوية", "النقطة الأصلية", "الفارق (′)", "القوة"],
                [[i, h[2], f"{h[5]} ({h[4]}°)", h[3], f"{h[6]:.2f}", f"{h[7]:.2f}"] for i, h in enumerate(hs, 1)],
                col_cls=["num", "", "", "", "num", "num"],
            ))
        parts.append(section("تفاصيل التطابقات الفلكية الكاملة", "".join(hb), page_break=True))
    else:
        parts.append(section("تفاصيل التطابقات الفلكية الكاملة", '<p class="note">لا توجد تطابقات ضمن السماحيات لهذا المرشح.</p>'))

    # ---------------- 12. المنهجية ----------------
    m_rows = [[TECH_AR[t], TECH_DESC[t], TECH_ORB_TEXT[t]] for t in TECH_CODES]
    parts.append(section(
        "المنهجية والسماحيات",
        _html_table(["الخريطة", "الوصف", "السماحية (دقائق قوسية)"], m_rows)
        + "<h3>معادلة التقييم</h3>"
        '<p class="note">قوة التطابق = العامل × وزن الخريطة × وزن الزاوية × (1 − الفارق/السماحية)<sup>1.25</sup> × معزّز الدقة '
        "(×1.30 إن كان الفارق ≤ 3′، ×1.12 إن كان ≤ 8′). تُجمع أقوى ثلاثة تطابقات لكل خريطة: "
        "القوة الفعّالة = h₁ + 0.30·(h₂ + h₃)، ثم النسبة = 100·(1 − e<sup>−1.1·القوة الفعّالة</sup>). "
        f"المتوسط العام = متوسط النسب الست، والقبول عند ≥ {thr:.0f}%.</p>"
        f'<p class="note">ثوابت: السنة المدارية {TROPICAL_YEAR} يومًا · قوس نيبود {NAIBOD_PER_DAY:.9f}°/يوم.</p>',
    ))
    parts.append(
        '<div class="disclaimer"><b>تنبيه:</b> هذا التقرير مخرَج حسابي تحليلي مبني على تقنيات التسيير الفلكي المعتمدة في التطبيق، '
        "ويعتمد على دقة المدخلات (تاريخ الحدث وفترته ومكان الميلاد والمنطقة الزمنية).</div>"
    )
    parts.append(
        f'<div class="rp-foot"><span>أسترو رادار — تصحيح الطالع ودرجته</span><span>#{rid} · {now_utc:%Y-%m-%d %H:%M} UTC</span></div>'
    )

    toolbar = (
        '<div class="toolbar"><button onclick="window.print()">🖨️ طباعة / حفظ PDF</button>'
        '<span class="hint">اختر «حفظ كـ PDF» من نافذة الطباعة · الخلفيات والألوان محفوظة تلقائيًا</span></div>'
    )
    return (
        '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>تقرير تصحيح الطالع — {esc(name)} — {best_time}</title>"
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">'
        f"<style>{REPORT_CSS}</style></head><body>{toolbar}<main class=\"paper\">{''.join(parts)}</main></body></html>"
    )


# ==============================================================================
# 7. واجهة Streamlit الاحترافية للنشر المباشر على Streamlit Community Cloud
# ==============================================================================
@st.cache_resource
def _load_geo():
    gc = geonamescache.GeonamesCache()
    countries = gc.get_countries()
    cities = gc.get_cities()
    tf = TimezoneFinder()
    return countries, cities, tf


APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');
:root{--bg:#060914;--panel:#0E1426;--panel2:#121A33;--line:#1F2A48;--gold:#F5B942;--gold2:#FBD38D;--ink:#E8EEF9;--muted:#8FA0C0;--ok:#34D399;--bad:#F87171;--accent:#7C83FF}
.stApp{direction:rtl;text-align:right;color:var(--ink);font-family:'Cairo',sans-serif;
 background:radial-gradient(1100px 560px at 88% -8%,rgba(124,131,255,.20),transparent 60%),
            radial-gradient(900px 480px at 4% 6%,rgba(245,185,66,.10),transparent 55%),#060914}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp label,.stApp li,.stApp td,.stApp th,.stApp button,.stApp input,.stApp textarea,.stApp .stMarkdown{font-family:'Cairo',sans-serif}
.stApp h2,.stApp h3{color:#F1F5FF;font-weight:800}
header[data-testid="stHeader"]{background:transparent}
#MainMenu,footer{visibility:hidden}
.block-container{padding-top:1.2rem;max-width:1320px}

/* ===== الشريط الجانبي ===== */
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0C1328 0%,#080C1B 100%);box-shadow:0 0 50px rgba(0,0,0,.55)}
section[data-testid="stSidebar"] *{color:#DCE6FA}
.sb-brand{display:flex;align-items:center;gap:10px;padding:6px 2px 10px;border-bottom:1px solid var(--line);margin-bottom:6px}
.sb-brand span{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;font-size:20px;color:#1B1300;background:linear-gradient(135deg,#FBD38D,#F59E0B)}
.sb-brand b{display:block;font-size:15px;line-height:1.2;color:#fff}
.sb-brand small{letter-spacing:.2em;font-size:9.5px;color:#93A4CC}
.sb-h{margin:16px 0 4px;padding:7px 12px;border-radius:10px;font-weight:800;font-size:13.5px;color:var(--gold2);background:linear-gradient(90deg,rgba(245,185,66,.14),rgba(245,185,66,0));border-right:3px solid var(--gold)}
div[data-baseweb="input"]>div,div[data-baseweb="select"]>div,div[data-baseweb="base-input"],textarea{background:#0F1730!important;border-color:#22305A!important;color:#000000!important;border-radius:10px!important}
div[data-baseweb="input"] input,div[data-baseweb="select"] input,div[data-baseweb="select"] span,div[data-baseweb="select"] div,div[data-testid="stDateInput"] input,textarea{color:#000000!important;-webkit-text-fill-color:#000000!important}
ul[role="listbox"],div[data-baseweb="popover"] div[data-baseweb="menu"]{background:#0F1730!important;color:#000000!important}

/* ===== زر التنفيذ والتنزيل ===== */
.stButton>button,.stDownloadButton>button{font-family:'Cairo',sans-serif;font-weight:800;border-radius:12px;border:1px solid #2A3866;background:#121B38;color:#E8EEF9;transition:all .18s ease}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--gold);color:#fff;transform:translateY(-1px)}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"],button[data-testid="stBaseButton-primary"]{border:0;color:#1B1300;background:linear-gradient(135deg,#FBD38D 0%,#F5B942 55%,#F59E0B 100%);box-shadow:0 8px 24px rgba(245,185,66,.32)}
.stButton>button[kind="primary"]:hover,.stDownloadButton>button[kind="primary"]:hover,button[data-testid="stBaseButton-primary"]:hover{filter:brightness(1.07);color:#1B1300;box-shadow:0 10px 30px rgba(245,185,66,.45)}

/* ===== الهيرو ===== */
.hero{position:relative;overflow:hidden;padding:26px 30px 22px;border-radius:20px;margin-bottom:18px;border:1px solid #243158;
 background:linear-gradient(125deg,#0B1124 0%,#151B45 52%,#241F63 100%);box-shadow:0 20px 60px rgba(8,12,40,.55)}
.hero:before{content:"";position:absolute;inset:0;opacity:.55;
 background-image:radial-gradient(1.4px 1.4px at 12% 28%,#fff,transparent),radial-gradient(1px 1px at 28% 72%,#cfd8ff,transparent),radial-gradient(1.6px 1.6px at 46% 18%,#fff,transparent),radial-gradient(1px 1px at 63% 62%,#cfd8ff,transparent),radial-gradient(1.4px 1.4px at 78% 24%,#fff,transparent),radial-gradient(1px 1px at 90% 70%,#cfd8ff,transparent),radial-gradient(1px 1px at 6% 80%,#cfd8ff,transparent)}
.hero:after{content:"☉";position:absolute;left:-18px;top:-46px;font-size:210px;line-height:1;color:rgba(245,185,66,.10);font-family:'Segoe UI Symbol','Noto Sans Symbols 2','DejaVu Sans',sans-serif}
.hero>*{position:relative;z-index:1}
.hero .eyebrow{display:inline-block;font-size:10.5px;letter-spacing:.24em;color:var(--gold2);padding:3px 12px;border-radius:99px;border:1px solid rgba(245,185,66,.4);background:rgba(245,185,66,.08);margin-bottom:10px}
.hero h1{margin:0;font-size:28px;line-height:1.5;font-weight:800;background:linear-gradient(90deg,#fff 0%,#FBD38D 60%,#F5B942 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{margin:4px 0 14px;color:#B9C6EA;font-size:14px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chips span{padding:5px 13px;border-radius:99px;font-size:12px;font-weight:600;color:#DCE6FF;background:rgba(124,131,255,.14);border:1px solid rgba(124,131,255,.32)}

/* ===== بطاقة الحكم ===== */
.verdict-card{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:20px 26px;border-radius:18px;margin:6px 0 14px;border:1px solid;box-shadow:0 14px 40px rgba(0,0,0,.35)}
.verdict-card.ok{background:linear-gradient(120deg,rgba(16,185,129,.16),rgba(16,185,129,.04) 60%,rgba(124,131,255,.08));border-color:rgba(52,211,153,.45)}
.verdict-card.bad{background:linear-gradient(120deg,rgba(248,113,113,.16),rgba(248,113,113,.04) 60%,rgba(124,131,255,.06));border-color:rgba(248,113,113,.45)}
.v-badge{display:inline-block;padding:3px 14px;border-radius:99px;font-weight:800;font-size:13px}
.verdict-card.ok .v-badge{color:#6EE7B7;background:rgba(52,211,153,.14)}
.verdict-card.bad .v-badge{color:#FCA5A5;background:rgba(248,113,113,.14)}
.v-time{font-family:'DejaVu Sans Mono',Consolas,monospace;direction:ltr;text-align:right;font-weight:800;font-size:46px;line-height:1.15;margin:6px 0 2px;color:#fff;letter-spacing:2px;text-shadow:0 4px 24px rgba(124,131,255,.5)}
.v-sub{color:#B9C6EA;font-size:13.5px}.v-sub b{color:#fff}
.ring{--p:0;--c:#34D399;flex:0 0 auto;width:126px;height:126px;border-radius:50%;display:grid;place-items:center;position:relative;background:conic-gradient(var(--c) calc(var(--p) * 1%),#1B2547 0)}
.ring:before{content:"";position:absolute;inset:11px;border-radius:50%;background:#0B1124}
.ring .in{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;line-height:1.2}
.ring .in b{font-size:23px;color:#fff;font-weight:800}.ring .in small{font-size:11px;color:var(--muted)}

/* ===== بطاقات الخرائط الست ===== */
.kpi-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin:4px 0 18px}
.kpi-card{padding:14px 14px 12px;border-radius:14px;background:linear-gradient(180deg,#111A36,#0C1328);border:1px solid var(--line);transition:transform .18s ease,border-color .18s ease}
.kpi-card:hover{transform:translateY(-3px);border-color:#34447F}
.k-top{display:flex;align-items:center;gap:7px;min-height:38px}
.k-dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.k-name{font-size:11.5px;font-weight:700;color:#C5D1EF;line-height:1.45}
.k-val{font-size:27px;font-weight:800;margin:4px 0 8px;direction:ltr;text-align:right}
.k-bar{position:relative;height:7px;border-radius:99px;background:#1B2547;overflow:visible}
.k-bar i{display:block;height:100%;border-radius:99px}
.k-bar b{position:absolute;top:-3px;bottom:-3px;width:2px;background:#F87171;border-radius:2px}
@media (max-width:1100px){.kpi-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.verdict-card{flex-direction:column;align-items:flex-start}}
@media (max-width:640px){.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.v-time{font-size:36px}.hero h1{font-size:21px}}

/* ===== التبويبات ===== */
.stTabs [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid var(--line);padding-bottom:2px;flex-wrap:wrap}
.stTabs [data-baseweb="tab"]{height:44px;padding:0 16px;border-radius:12px 12px 0 0;background:transparent;color:#9FB0D6;font-weight:700}
.stTabs [data-baseweb="tab"]:hover{color:#fff;background:rgba(124,131,255,.08)}
.stTabs [aria-selected="true"]{color:var(--gold2)!important;background:linear-gradient(180deg,rgba(245,185,66,.14),rgba(245,185,66,0))}
.stTabs [data-baseweb="tab-highlight"]{background:linear-gradient(90deg,#F5B942,#FBD38D)!important;height:3px!important}

/* ===== لوحات التفاصيل ===== */
.panel-title{font-weight:800;font-size:15px;color:var(--gold2);margin:2px 0 8px;padding-right:10px;border-right:3px solid var(--gold)}
.detail{border:1px solid var(--line);border-radius:14px;background:linear-gradient(180deg,#101830,#0C1328);padding:4px 14px}
.detail div{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px dashed #1F2A48}
.detail div:last-child{border-bottom:0}
.detail span{color:var(--muted);font-size:13px}.detail b{color:#fff;font-weight:700;font-size:13.5px;text-align:left}
.report-intro{padding:14px 18px;border-radius:14px;margin-bottom:12px;background:linear-gradient(120deg,rgba(124,131,255,.14),rgba(245,185,66,.08));border:1px solid rgba(124,131,255,.32);color:#DCE6FF;line-height:1.9}
.report-intro small{color:#9FB0D6}
.app-foot{margin:26px 0 8px;text-align:center;color:#6F7FA5;font-size:12px}
[data-testid="stAlert"]{border-radius:14px}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:12px;overflow:hidden}
</style>
"""


def _stretch(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """يستدعي عنصر Streamlit بعرض كامل متوافقًا مع الإصدارات القديمة والجديدة."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except Exception:
        return fn(*args, use_container_width=True, **kwargs)


def _pct_color(v: float, thr: float) -> str:
    if v >= thr:
        return "#34D399"
    if v >= thr - 20.0:
        return "#FBBF24"
    return "#7C8DB5"


def _hero_html() -> str:
    return (
        '<div class="hero">'
        '<div class="eyebrow">✦ ASTRO RADAR · BIRTH-TIME RECTIFICATION</div>'
        f"<h1>{esc(APP_TITLE)}</h1>"
        "<p>مسح تسلسلي دقيق عبر ست تقنيات تسيير فلكية لتحديد ساعة الميلاد ودرجة الطالع</p>"
        '<div class="chips">'
        "<span>🏛 نظام البيوت: توبوسنتريك فقط (Polich-Page)</span>"
        "<span>⏱ دقة المسح: كل 4 ثوانٍ (صقل 1 ثانية)</span>"
        "<span>🎯 عتبة قبول الحدث: ≥ 60%</span>"
        "<span>🌐 Swiss Ephemeris</span>"
        "</div></div>"
    )


def _render_timeline_chart(res: dict, thr: float) -> None:
    """منحنى تفاعلي (Altair) بخلفية داكنة مستقلة عن ثيم Streamlit، مع رجوع آمن إلى line_chart."""
    tdf = res["timeline_df"]
    span = int(round((res["end_dt"] - res["start_dt"]).total_seconds()))
    offs = [min(i * SCAN_STEP_SECONDS, span) for i in range(len(tdf))]
    plot = pd.DataFrame({
        "t": [res["start_dt"] + dt.timedelta(seconds=o) for o in offs],
        "pct": tdf["متوسط الخرائط الست (%)"].to_numpy(),
    })
    try:
        import altair as alt

        grad = alt.Gradient(
            gradient="linear",
            stops=[alt.GradientStop(color="rgba(124,131,255,0.45)", offset=0),
                   alt.GradientStop(color="rgba(124,131,255,0.02)", offset=1)],
            x1=1, x2=1, y1=1, y2=0,
        )
        base = alt.Chart(plot).encode(
            x=alt.X("t:T", title=None, axis=alt.Axis(format="%H:%M", grid=False)),
            y=alt.Y("pct:Q", title="متوسط الخرائط الست (%)", scale=alt.Scale(domain=[0, 100])),
        )
        area = base.mark_area(line={"color": "#9DA4FF", "strokeWidth": 1.6}, color=grad)
        rule = alt.Chart(pd.DataFrame({"y": [thr]})).mark_rule(color="#F87171", strokeDash=[6, 4], strokeWidth=1.6).encode(y="y:Q")
        cands = _candidate_list(res)
        pts = pd.DataFrame({
            "t": [res["start_dt"] + dt.timedelta(seconds=int(c["offset_sec"])) for c in cands],
            "pct": [float(c["avg_percent"]) for c in cands],
            "المرشح": [str(i) for i in range(1, len(cands) + 1)],
            "الوقت": [c["local_dt"].strftime("%H:%M:%S") for c in cands],
            "الحالة": ["معتمد" if c["above_threshold"] else "غير معتمد" for c in cands],
        })
        dots = alt.Chart(pts).mark_point(filled=True, size=90, stroke="#060914", strokeWidth=1.5).encode(
            x="t:T", y="pct:Q",
            color=alt.Color("الحالة:N", scale=alt.Scale(domain=["معتمد", "غير معتمد"], range=["#34D399", "#8FA0C0"]),
                            legend=alt.Legend(title=None, labelColor="#C5D1EF")),
            tooltip=["المرشح", "الوقت", alt.Tooltip("pct:Q", title="المتوسط", format=".1f"), "الحالة"],
        )
        chart = (
            alt.layer(area, rule, dots)
            .properties(height=360, background="transparent")
            .configure_axis(labelColor="#9FB0D0", titleColor="#9FB0D0", gridColor="#1B2547", domainColor="#26335C", tickColor="#26335C")
            .configure_view(strokeWidth=0)
        )
        _stretch(st.altair_chart, chart, theme=None)
    except Exception:
        st.line_chart(tdf.set_index("الوقت المحلي")["متوسط الخرائط الست (%)"])


def main():
    st.set_page_config(page_title="أسترو رادار — تصحيح الطالع", page_icon="✦", layout="wide")
    st.markdown(APP_CSS, unsafe_allow_html=True)
    st.markdown(_hero_html(), unsafe_allow_html=True)

    countries, cities, tf = _load_geo()

    with st.sidebar:
        st.markdown('<div class="sb-brand"><span>✦</span><div><b>أسترو رادار</b><small>ASTRO RADAR</small></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-h">🧿 معطيات الميلاد والحدث</div>', unsafe_allow_html=True)
        name = st.text_input("اسم المولود", value="أحمد")
        gender_ar = st.radio("الجنس", ["ذكر", "أنثى"], horizontal=True)
        gender = "M" if gender_ar == "ذكر" else "F"
        birth_date = st.date_input("تاريخ الميلاد", value=dt.date(1990, 1, 1), min_value=dt.date(1940, 1, 1))

        win_labels = [w[0] for w in THREE_HOUR_WINDOWS] + ["بداية مخصصة (+3 ساعات)"]
        win_choice = st.selectbox("نطاق البحث (3 ساعات كاملة)", win_labels, index=4)
        if win_choice == "بداية مخصصة (+3 ساعات)":
            custom_t = st.time_input("ساعة بداية النطاق", value=dt.time(10, 0))
            start_h, start_m = custom_t.hour, custom_t.minute
        else:
            w_idx = win_labels.index(win_choice)
            _, start_h, start_m = THREE_HOUR_WINDOWS[w_idx]

        st.markdown('<div class="sb-h">📍 مكان الميلاد</div>', unsafe_allow_html=True)
        manual_loc = st.checkbox("إدخال الإحداثيات يدويًا", value=False)
        if not manual_loc:
            country_opts = sorted([(v["name"], k) for k, v in countries.items()])
            def_c = next((i for i, x in enumerate(country_opts) if x[1] == "SY"), 0)
            c_name, c_code = st.selectbox("الدولة", country_opts, index=def_c, format_func=lambda x: x[0])
            city_list = sorted(
                [(c["name"], float(c["latitude"]), float(c["longitude"])) for c in cities.values() if c["countrycode"] == c_code],
                key=lambda x: x[0],
            )
            if city_list:
                def_ct = next((i for i, x in enumerate(city_list) if x[0] == "Damascus"), 0)
                ct_name, lat, lon = st.selectbox("المدينة", city_list, index=def_ct, format_func=lambda x: x[0])
            else:
                ct_name, lat, lon = c_name, 33.5138, 36.2765
            tz_name = tf.timezone_at(lat=lat, lng=lon) or "UTC"
            loc_label = f"{c_name} / {ct_name}"
        else:
            loc_label = st.text_input("اسم المدينة", value="دمشق")
            lat = st.number_input("خط العرض", value=33.5138, min_value=-89.0, max_value=89.0, format="%.4f")
            lon = st.number_input("خط الطول", value=36.2765, min_value=-180.0, max_value=180.0, format="%.4f")
            tz_name = st.text_input("المنطقة الزمنية IANA", value="Asia/Damascus")

        st.markdown('<div class="sb-h">⚡ الحدث الماضي المعتمد</div>', unsafe_allow_html=True)
        event_kind = st.selectbox("نوع الحدث الحاسم", list(EVENT_TYPES.keys()))
        event_date = st.date_input("تاريخ الحدث", value=dt.date(2021, 1, 1), min_value=dt.date.today() - dt.timedelta(days=int(25 * 365.25)), max_value=dt.date.today())
        period_ar = st.radio("فترة الحدث", ["صباحًا", "مساءً"], horizontal=True)
        event_period = "AM" if period_ar == "صباحًا" else "PM"

        st.info("البيوت: توبوسنتريك فقط | المسح: كل 4 ثوانٍ | العتبة: ≥ 60%")
        run_btn = _stretch(st.button, "بدء التصحيح السداسي", type="primary")

    if run_btn or "rect_res" not in st.session_state:
        if event_date <= birth_date:
            st.error("يجب أن يكون تاريخ الحدث الماضي بعد تاريخ الميلاد.")
            return
        if event_date > dt.date.today():
            st.error("يجب أن يكون الحدث قد وقع في الماضي (تاريخ الحدث بعد تاريخ اليوم).")
            return
        try:
            tz_obj = pytz.timezone(tz_name)
        except Exception:
            st.error(f"المنطقة الزمنية غير معروفة: {tz_name}")
            return

        def _to_utc(local_dt: dt.datetime) -> dt.datetime:
            return tz_obj.localize(local_dt, is_dst=None).astimezone(pytz.UTC).replace(tzinfo=None)

        eph = SwissEphemeris()
        t0 = time.time()
        try:
            with st.spinner("جاري المسح التسلسلي كل 4 ثوانٍ وحساب الخرائط الست..."):
                st.session_state["rect_res"] = rectify_birth_time(
                    eph=eph,
                    birth_date=birth_date,
                    lat=lat,
                    lon=lon,
                    to_utc=_to_utc,
                    event_kind=event_kind,
                    event_date=event_date,
                    event_period=event_period,
                    gender=gender,
                    start_hour=start_h,
                    start_minute=start_m,
                )
        except Exception as exc:  # مثل ساعة غير موجودة/مكررة عند تغيير التوقيت الصيفي
            st.error(f"تعذّر إكمال التصحيح: {exc}")
            return
        st.session_state["rect_meta"] = {
            "name": name,
            "gender": gender,
            "gender_ar": gender_ar,
            "birth_date": birth_date,
            "win_label": win_choice,
            "loc_label": loc_label,
            "lat": float(lat),
            "lon": float(lon),
            "tz_name": tz_name,
            "event_kind": event_kind,
            "event_date": event_date,
            "event_period": event_period,
            "event_period_ar": period_ar,
            "step_s": SCAN_STEP_SECONDS,
            "span_hours": SPAN_HOURS,
            "threshold": THRESHOLD_PERCENT,
            "eph_mode": "Moshier (مدمج)" if eph.flags == eph.swe.FLG_MOSEPH else "Swiss Ephemeris (ملفات .se1)",
            "elapsed": time.time() - t0,
        }
        st.session_state.pop("rect_report", None)

    res = st.session_state["rect_res"]
    meta = st.session_state.get("rect_meta", {"name": name})
    _render_results(res, meta)

    st.markdown(
        '<div class="app-foot">✦ أسترو رادار — أداة تحليلية مساعدة؛ تُنصح المقارنة بأكثر من حدث حاسم قبل اعتماد ساعة الميلاد.</div>',
        unsafe_allow_html=True,
    )


def _render_results(res: dict, meta: dict) -> None:
    name = meta.get("name", "—")
    thr = float(res.get("threshold_percent", THRESHOLD_PERCENT))

    if not res["has_above_threshold"]:
        st.error(
            f"❌ تم رفض الحدث: أعلى متوسط للخرائط الست بلغ {res['max_avg_percent']:.1f}% وهو أقل من عتبة القبول المطلوبة (60.0%). "
            "يرجى إدخال حدث حاسم آخر (مثل الوفاة أو الولادة أو عملية جراحية أو عقد قران/زفاف)."
        )
        top_diag = res["diagnostic"][0] if res["diagnostic"] else None
        if top_diag:
            st.warning(f"أقرب ذروة تشخيصية (غير معتمدة): {top_diag['local_dt'].strftime('%H:%M:%S')} — الطالع {describe_lon(top_diag['asc_lon'])}")
        best = top_diag
        accepted = False
    else:
        best = res["qualified"][0]
        accepted = True

    if best is None:
        return

    ring_col = _pct_color(best["avg_percent"], thr)
    best_time = best["local_dt"].strftime("%H:%M:%S")
    if accepted:
        st.markdown(
            '<div class="verdict-card ok"><div class="v-main">'
            '<div class="v-badge">✔ تم قبول الحدث وتحديد ساعة الميلاد</div>'
            f'<div class="v-time">{best_time}</div>'
            f'<div class="v-sub">الطالع: <b>{esc(fmt_lon(best["asc_lon"]))}</b> &nbsp;|&nbsp; '
            f'متوسط الخرائط الست: <b>{best["avg_percent"]:.1f}%</b> &nbsp;|&nbsp; مرشحون معتمدون: <b>{len(res["qualified"])}</b></div>'
            "</div>"
            f'<div class="ring" style="--p:{best["avg_percent"]:.1f};--c:{ring_col}"><div class="in"><b>{best["avg_percent"]:.1f}%</b><small>المتوسط</small></div></div>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="verdict-card bad"><div class="v-main">'
            '<div class="v-badge">✖ نتيجة تشخيصية غير معتمدة</div>'
            f'<div class="v-time">{best_time}</div>'
            f'<div class="v-sub">الطالع: <b>{esc(fmt_lon(best["asc_lon"]))}</b> &nbsp;|&nbsp; '
            f'المتوسط: <b>{best["avg_percent"]:.1f}%</b> &nbsp;|&nbsp; العتبة المطلوبة: <b>{thr:.0f}%</b></div>'
            "</div>"
            f'<div class="ring" style="--p:{best["avg_percent"]:.1f};--c:{ring_col}"><div class="in"><b>{best["avg_percent"]:.1f}%</b><small>المتوسط</small></div></div>'
            "</div>",
            unsafe_allow_html=True,
        )

    # بطاقات الخرائط الست (تحل محل st.metric الأصلية وتعرض نفس القيم)
    cards = []
    for tc in TECH_CODES:
        v = best["tech_percents"][tc]
        col = _pct_color(v, thr)
        cards.append(
            '<div class="kpi-card">'
            f'<div class="k-top"><span class="k-dot" style="background:{TECH_COLORS[tc]}"></span><span class="k-name">{esc(TECH_AR[tc])}</span></div>'
            f'<div class="k-val" style="color:{col}">{v:.1f}%</div>'
            f'<div class="k-bar"><i style="width:{max(0.0, min(100.0, v)):.1f}%;background:{col}"></i><b style="right:{thr:.0f}%"></b></div>'
            "</div>"
        )
    st.markdown('<div class="kpi-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)

    natal: Natal = best["natal"]
    cusp_list = natal_cusp_list(natal)

    tabs = st.tabs([
        "🎯 النتيجة والدائرة", "📈 منحنى المسح", "🪐 المواقع والبيوت",
        "🔗 التطابقات", "👥 المرشحون", "🖨️ التقرير القابل للطباعة",
    ])

    # ---- 1) النتيجة والدائرة
    with tabs[0]:
        c1, c2 = st.columns([1.15, 1])
        with c1:
            svg = render_zodiac_svg_pro(natal, best_time, name, best["avg_percent"], theme="dark", size=560)
            st.iframe(svg, height=600)
        with c2:
            st.markdown('<div class="panel-title">ملخص الطالع</div>', unsafe_allow_html=True)
            rows = [
                ("ساعة الميلاد", best_time),
                ("الطالع AS", fmt_lon(best["asc_lon"])),
                ("وتد السماء MC", fmt_lon(best["mc_lon"])),
                ("سهم السعادة POF", fmt_lon(best["pof_lon"])),
                ("حاكم الطالع", PLANET_AR[best["asc_ruler"]]),
                ("برج الانتهاء السنوي", best["prof_sign_ar"]),
                ("رب السنة", best["lord_of_year_ar"]),
                ("نهاري / ليلي", "نهاري" if bool(natal.is_day[0]) else "ليلي"),
            ]
            if res.get("ev_jd") is not None:
                age = (float(res["ev_jd"]) - float(natal.jd[0])) / TROPICAL_YEAR
                rows.append(("العمر عند الحدث", f"{age:.2f} سنة"))
            st.markdown(
                '<div class="detail">' + "".join(f"<div><span>{esc(k)}</span><b>{esc(v)}</b></div>" for k, v in rows) + "</div>",
                unsafe_allow_html=True,
            )
            st.markdown('<div class="panel-title" style="margin-top:14px">معطيات التشغيل</div>', unsafe_allow_html=True)
            bd = meta.get("birth_date")
            ed = meta.get("event_date")
            run_rows = [
                ("المولود", f"{name} ({meta.get('gender_ar', '—')})"),
                ("الميلاد", f"{bd:%Y-%m-%d} · {meta.get('loc_label', '—')}" if hasattr(bd, "strftime") else "—"),
                ("الحدث", f"{meta.get('event_kind', '—')}"),
                ("تاريخ الحدث", f"{ed:%Y-%m-%d} ({meta.get('event_period_ar', '—')})" if hasattr(ed, "strftime") else "—"),
                ("النطاق", f"{res['start_dt']:%H:%M:%S} ← {res['end_dt']:%H:%M:%S}"),
            ]
            st.markdown(
                '<div class="detail">' + "".join(f"<div><span>{esc(k)}</span><b>{esc(v)}</b></div>" for k, v in run_rows) + "</div>",
                unsafe_allow_html=True,
            )

    # ---- 2) منحنى المسح
    with tabs[1]:
        st.subheader("منحنى المسح التسلسلي (كل 4 ثوانٍ)")
        _render_timeline_chart(res, thr)
        _stretch(
            st.download_button, "⬇️ تنزيل جدول المسح الكامل (CSV)",
            data=res["timeline_df"].to_csv(index=False).encode("utf-8-sig"),
            file_name="scan_timeline.csv", mime="text/csv", key="dl_timeline",
        )

    # ---- 3) المواقع والبيوت
    with tabs[2]:
        ca, cb = st.columns(2)
        with ca:
            st.subheader("مواقع الكواكب")
            _stretch(st.dataframe, pd.DataFrame(planets_rows(natal, cusp_list)), hide_index=True)
        with cb:
            st.subheader("رؤوس البيوت (توبوسنتريك)")
            _stretch(st.dataframe, pd.DataFrame(houses_rows(natal)), hide_index=True)
        cc, cd = st.columns(2)
        with cc:
            st.subheader("النقطة الشرقية والسهام")
            _stretch(st.dataframe, pd.DataFrame(points_rows(natal)), hide_index=True)
        with cd:
            st.subheader("الزوايا بين الكواكب (≤ 6°)")
            lons_n = {c: float(natal.pl[c][0]) for c in PLANETS}
            na = natal_aspects(lons_n, orb=6.0)
            _stretch(
                st.dataframe,
                pd.DataFrame([
                    {"الكوكب الأول": PLANET_AR[a], "الزاوية": f"{ASPECT_AR.get(asp, asp)} ({asp}°)",
                     "الكوكب الثاني": PLANET_AR[b], "السماحية (°)": round(o, 2)}
                    for a, b, asp, o in na
                ]),
                hide_index=True,
            )
        ev_pl = res.get("event_planets") or {}
        if ev_pl:
            st.subheader("الكواكب العابرة وقت الحدث")
            _stretch(
                st.dataframe,
                pd.DataFrame([
                    {"الكوكب": PLANET_AR[c], "الموضع": fmt_lon(ev_pl[c]), "البيت": house_of(ev_pl[c], cusp_list)}
                    for c in PLANETS if c in ev_pl
                ]),
                hide_index=True,
            )

    # ---- 4) التطابقات
    with tabs[3]:
        st.subheader("تفاصيل التطابقات الفلكية")
        all_hits = list(best["hits"])
        c_f1, c_f2 = st.columns([3, 1])
        with c_f1:
            sel = st.multiselect("تصفية بحسب الخريطة", [TECH_AR[t] for t in TECH_CODES], default=[TECH_AR[t] for t in TECH_CODES])
        with c_f2:
            show_all = st.checkbox("عرض كل التطابقات", value=False)
        flt = [h for h in all_hits if h[1] in sel]
        shown = flt if show_all else flt[:35]
        st.caption(f"المعروض {len(shown)} من أصل {len(flt)} تطابقًا (الأقوى أولًا).")
        hits_df = pd.DataFrame(
            [
                {
                    "الخريطة": h[1],
                    "الدليل الموجه": h[2],
                    "الزاوية": f"{h[5]} ({h[4]}°)",
                    "النقطة الأصلية": h[3],
                    "الفارق (دقيقة قوسية)": round(h[6], 2),
                }
                for h in shown
            ]
        )
        _stretch(st.dataframe, hits_df, hide_index=True)

    # ---- 5) المرشحون
    with tabs[4]:
        st.subheader("المرشحون بعد الصقل الدقيق")
        cdf = pd.DataFrame(candidates_rows(res))
        try:
            colcfg = {"المتوسط (%)": st.column_config.ProgressColumn("المتوسط (%)", min_value=0, max_value=100, format="%.1f")}
            _stretch(st.dataframe, cdf, hide_index=True, column_config=colcfg)
        except Exception:
            _stretch(st.dataframe, cdf, hide_index=True)
        _stretch(
            st.download_button, "⬇️ تنزيل المرشحين (CSV)",
            data=cdf.to_csv(index=False).encode("utf-8-sig"), file_name="candidates.csv", mime="text/csv", key="dl_cands",
        )

    # ---- 6) التقرير القابل للطباعة
    with tabs[5]:
        if "rect_report" not in st.session_state:
            st.session_state["rect_report"] = build_printable_report_html(res, meta)
        report_html = st.session_state["rect_report"]
        st.markdown(
            '<div class="report-intro"><b>🖨️ تقرير A4 كامل</b> يحوي: الحكم والنتيجة · معطيات الإدخال · الخرائط الست · دائرة الزودياك · '
            "مواقع الكواكب · البيوت والأسهم · الزوايا · العبور وقت الحدث · دلائل الحدث · منحنى المسح · المرشحون · كل التطابقات · المنهجية."
            "<br><small>اضغط «طباعة / حفظ PDF» داخل المعاينة، أو نزّل الملف وافتحه في المتصفح.</small></div>",
            unsafe_allow_html=True,
        )
        d1, d2 = st.columns(2)
        stamp = f"{best['local_dt']:%Y%m%d_%H%M%S}"
        with d1:
            _stretch(
                st.download_button, "⬇️ تنزيل التقرير (HTML قابل للطباعة)", type="primary",
                data=report_html.encode("utf-8"), file_name=f"asc_rectification_report_{stamp}.html",
                mime="text/html", key="dl_report",
            )
        with d2:
            _stretch(
                st.download_button, "⬇️ تنزيل جدول المسح (CSV)",
                data=res["timeline_df"].to_csv(index=False).encode("utf-8-sig"),
                file_name=f"scan_timeline_{stamp}.csv", mime="text/csv", key="dl_timeline2",
            )
        st.iframe(report_html, height=1100)


if __name__ == "__main__":
    main()
