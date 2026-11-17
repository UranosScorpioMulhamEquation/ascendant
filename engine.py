# -*- coding: utf-8 -*-
"""
engine.py — محرك تصحيح الطالع (Rectification Engine)

المرجع: Juan Estadella, "Predictive Astrology" (3rd ed.) — الفصول 2، 3، 5، 6، 9، 13 والملحقات I–III
(+ Marr / Polich & Nelson Page كما وردوا في الكتاب).

الفكرة: لكل وقت ميلاد مرشّح داخل النافذة (3 ساعات) تُحسب الاتجاهات الأولية التوبوسنتريك،
التسيير الثانوي، الأقواس الشمسية، والعبور (المباشر وما قبل الولادة) في تاريخ كل حدث،
ثم يُعطى المرشّح نقاطًا حسب تطابق رموز الحدث (جدول بوليس/مار) بسماحيات الكتاب الضيقة.
كل الحسابات متجهة (numpy) على مصفوفة الأوقات المرشحة دفعة واحدة.

لا يعتمد هذا الملف على swisseph إلا داخل الفئة SwissEphemeris، لذلك يمكن اختبار المعادلات وحدها.
"""
from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass, replace
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

# ----------------------------------------------------------------------------
# ثوابت
# ----------------------------------------------------------------------------
NAIBOD_PER_DAY = 0.00269861      # درجة/يوم  (مفتاح نايبود 59'08.33"/سنة ÷ 365.2422) — الكتاب ص70
TROPICAL_YEAR = 365.2422
BASE_SCORE = 25.0                # أعلى نقاط لاتجاه واحد (كما في Polaris: 25)

PLANETS = ['SUN', 'MOON', 'MER', 'VEN', 'MAR', 'JUP', 'SAT', 'URA', 'NEP', 'PLU', 'NN', 'SN']
PLANET_AR = {
    'SUN': 'الشمس', 'MOON': 'القمر', 'MER': 'عطارد', 'VEN': 'الزهرة', 'MAR': 'المريخ',
    'JUP': 'المشتري', 'SAT': 'زحل', 'URA': 'أورانوس', 'NEP': 'نبتون', 'PLU': 'بلوتو',
    'NN': 'العقدة الشمالية', 'SN': 'العقدة الجنوبية',
}
FACTOR_AR = {
    'AS': 'الطالع AS', 'MC': 'وتد السماء MC', 'DS': 'الغارب DS', 'IC': 'وتد الأرض IC',
    'H2': 'بيت 2', 'H3': 'بيت 3', 'H5': 'بيت 5', 'H6': 'بيت 6', 'H8': 'بيت 8',
    'H9': 'بيت 9', 'H11': 'بيت 11', 'H12': 'بيت 12',
}
SIGNS_AR = ["الحمل", "الثور", "الجوزاء", "السرطان", "الأسد", "العذراء",
            "الميزان", "العقرب", "القوس", "الجدي", "الدلو", "الحوت"]

ASPECTS = (0, 30, 45, 60, 90, 120, 135, 150, 180)      # الكتاب ص72
MAJOR_ASPECTS = (0, 60, 90, 120, 180)
ASPECT_W = {0: 1.0, 180: 1.0, 90: 0.8, 120: 0.8, 60: 0.8,
            30: 0.4, 45: 0.4, 135: 0.4, 150: 0.4}

# سماحيات الكتاب بالدقائق القوسية
PD_ORB_MAJOR, PD_ORB_MINOR = 11.0, 6.0        # اتجاهات أولية (ص36، ص72)
SA_ORB_MAJOR, SA_ORB_MINOR = 12.0, 6.0        # أقواس شمسية (تقدير عملي، الكتاب لا يحدده)
TR_ORB = 65.0                                 # عبور دقيق ≈ 65'-68' (ص153)
SEC_ORB = {'SUN': 11, 'MER': 11, 'VEN': 11, 'MAR': 11, 'JUP': 8, 'SAT': 8,
           'URA': 3, 'NEP': 3, 'PLU': 3, 'NN': 3, 'SN': 3}   # ص92
SEC_ORB_MOON = (32.0, 18.0)                   # قمر: 32' اقتران/مقابلة، 18' البقية


# ----------------------------------------------------------------------------
# جدول الأحداث (Polaris — الفصل 5 ص73-79، وMarr — الملحق III)
#   sig  : الأوتاد/البيوت النموذجية   sig2: أحيانًا
#   pl   : الكواكب النموذجية         pl2 : أحيانًا
# ----------------------------------------------------------------------------
def _ev(sig, pl, sig2=(), pl2=()):
    return dict(sig=list(sig), pl=list(pl), sig2=list(sig2), pl2=list(pl2))


EVENT_TYPES: Dict[str, dict] = {
    "السفر": _ev(['H9', 'MC', 'AS'], ['MOON', 'MER', 'URA', 'JUP'], [], ['VEN', 'NEP', 'SUN', 'NN']),
    "سفر سلبي (طارئ/مشاكل)": _ev(['H9', 'MC', 'AS'], ['SAT', 'MAR', 'NEP', 'PLU', 'MER', 'URA'], ['H12'], []),
    "موت الاب او الجد": _ev(['MC', 'AS', 'H8'], ['SAT', 'SUN', 'NEP', 'PLU', 'MAR', 'SN'], ['H12'], ['MOON', 'URA']),
    "موت الام او الجدة": _ev(['IC', 'AS', 'H8'], ['MOON', 'VEN', 'SAT', 'NEP', 'PLU', 'SN', 'MAR'], ['H12'], ['SUN', 'URA']),
    "موت الابن": _ev(['H5', 'IC', 'DS', 'H8'], ['MAR', 'SAT', 'NEP', 'PLU', 'SN'], ['H12'], ['SUN', 'MER', 'URA']),
    "موت الابنة": _ev(['H5', 'IC', 'DS', 'H8'], ['VEN', 'MOON', 'NEP', 'PLU', 'SN'], ['H12'], ['MAR', 'URA', 'MER']),
    "موت الزوج": _ev(['DS', 'IC', 'H8'], ['SAT', 'SUN', 'NEP', 'PLU', 'SN', 'MAR'], ['H12', 'H5'], ['URA']),
    "موت الزوجة": _ev(['DS', 'IC', 'H8'], ['MOON', 'VEN', 'SAT', 'NEP', 'PLU', 'SN', 'MAR'], ['H12', 'H5'], ['URA']),
    "موت أخ": _ev(['H3', 'AS', 'IC', 'H8'], ['MER', 'MAR', 'SAT', 'NEP', 'PLU', 'SN'], ['H12'], ['MOON', 'SUN']),
    "موت أخت": _ev(['H3', 'AS', 'IC', 'H8'], ['MOON', 'MER', 'VEN', 'MAR', 'SAT', 'NEP', 'PLU', 'SN'], ['H12'], []),
    "ولادة ابن": _ev(['H5', 'AS', 'IC'], ['MAR', 'SUN', 'JUP', 'NN'], [], ['PLU', 'URA', 'MOON', 'VEN', 'MER']),
    "ولادة ابنة": _ev(['H5', 'AS', 'IC'], ['VEN', 'MOON', 'JUP', 'NN'], [], ['MAR', 'URA', 'PLU', 'SUN', 'MER']),
    "ولادة أخ أصغر": _ev(['H3', 'IC', 'DS'], ['MER', 'JUP'], [], ['SUN', 'MOON', 'VEN', 'NN', 'URA', 'PLU']),
    "ولادة أخت صغرى": _ev(['H3', 'IC', 'DS'], ['MOON', 'MER', 'VEN'], [], ['SUN', 'JUP', 'NN', 'URA', 'PLU']),
    # الزواج يختلف حسب جنس المولود (ص74)
    "تاريخ الزواج/عقد القران": {
        'M': _ev(['DS', 'MC', 'H5'], ['VEN', 'MOON', 'NN', 'JUP'], [], ['MER', 'URA', 'MAR', 'SUN']),
        'F': _ev(['DS', 'MC', 'H5'], ['SUN', 'JUP', 'MAR', 'NN'], [], ['MER', 'URA', 'VEN', 'MOON', 'PLU']),
    },
    "طلاق / انفصال": _ev(['DS', 'IC'], ['MAR', 'SAT', 'NEP', 'SN', 'PLU'], ['H12'], ['MER', 'URA', 'VEN', 'MOON']),
    "عملية جراحية بمشفى": _ev(['AS', 'H12', 'MC'], ['MAR', 'SAT', 'NEP'], [], ['URA', 'PLU', 'MOON']),
    "حادث": _ev(['H3', 'MC', 'AS'], ['MAR', 'URA', 'SAT', 'MER'], ['H12'], ['NEP', 'SN', 'PLU', 'MOON']),
    "نجاح / ترقية / انتخاب": _ev(['H3', 'MC', 'AS'], ['SUN', 'JUP', 'MOON', 'MER', 'URA', 'VEN'], ['H11', 'H2'], ['NN', 'PLU']),
    "فشل / استقالة / تقاعد": _ev(['H3', 'MC', 'AS'], ['SAT', 'SUN', 'NEP', 'MAR', 'SN'], ['H12'], ['URA', 'MOON', 'MER', 'PLU']),
    "تغيير مسكن": _ev(['H3', 'IC', 'AS'], ['MER', 'MOON', 'NN', 'JUP', 'VEN', 'SUN'], [], ['URA']),
    "تخرج / نشر": _ev(['H3', 'MC', 'AS'], ['MER', 'MOON', 'JUP', 'SUN', 'URA', 'VEN'], [], ['NN']),
    "خسارة مالية": _ev(['H2', 'AS', 'MC'], ['NEP', 'URA', 'MER', 'MAR', 'SAT'], [], ['PLU', 'SN']),
    "مكسب مالي / زيادة دخل": _ev(['H2', 'H5', 'AS', 'MC'], ['JUP', 'VEN', 'URA'], [], ['PLU']),
    "اعتقال / سجن": _ev(['H12', 'MC', 'AS'], ['SAT', 'URA', 'NEP', 'MAR', 'PLU', 'SN'], ['H3'], ['SUN', 'MER']),
}


def resolve_spec(kind: str, gender: str) -> dict:
    s = EVENT_TYPES[kind]
    if 'M' in s and 'F' in s:
        return s['M'] if gender == 'M' else s['F']
    return s


# ----------------------------------------------------------------------------
# رياضيات الكرة السماوية (Estadella ص22-27، ص65-70، ص262-268)
# ----------------------------------------------------------------------------
def _wrap180(x):
    return (np.asarray(x, float) + 180.0) % 360.0 - 180.0


def ra_of_lon(lam, eps_deg):
    """الصعود المستقيم لنقطة على فلك البروج (عرض = 0)."""
    lam_r = np.radians(lam)
    e = math.radians(eps_deg)
    return np.degrees(np.arctan2(math.cos(e) * np.sin(lam_r), np.cos(lam_r))) % 360.0


def dec_of_lon(lam, eps_deg):
    return np.degrees(np.arcsin(math.sin(math.radians(eps_deg)) * np.sin(np.radians(lam))))


def mc_from_ramc(ramc, eps_deg):
    r = np.radians(ramc)
    return np.degrees(np.arctan2(np.sin(r), np.cos(r) * math.cos(math.radians(eps_deg)))) % 360.0


def lam_from_oa(oa_deg, phi_rad, eps_rad):
    """
    معادلة ماره المبسطة للبيوت/العوامل المسيّرة (الكتاب ص23، ص69):
      tan(LONG) = (sin E · tan φ − cos E · cos OA) / sin OA
      +90° إن كان OA < 180° وإلا +270°.
    عند العوامل ذات الانحدار المائل (OD) تُعطى E سالبة.
    """
    oa = np.asarray(oa_deg, float) % 360.0
    oa_r = np.radians(oa)
    x = np.sin(eps_rad) * np.tan(phi_rad) - np.cos(eps_rad) * np.cos(oa_r)
    y = np.sin(oa_r)
    y = np.where(np.abs(y) < 1e-12, 1e-12, y)
    lam = np.degrees(np.arctan(x / y)) + np.where(oa < 180.0, 90.0, 270.0)
    return lam % 360.0


def all_cusps(ramc, lat_deg, eps_deg) -> Dict[str, np.ndarray]:
    """
    البيوت التوبوسنتريك (Polich & Page). الأقطاب: 1/3 و2/3 من ظل خط العرض (ص23-24).
    OA البيت = RAMC + 30°·k  (XI→1، XII→2، AS→3، II→4، III→5).
    """
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
    return out


def east_point(ramc, eps_deg):
    """
    النقطة الشرقية EP = نقطة البروج الصاعدة على خط الاستواء (قطب = 0).
    RA(EP) = RAMC + 90° دائمًا، لذلك EP دالّة في RAMC فقط (لا تتأثر بخط العرض).
    """
    return lam_from_oa(np.asarray(ramc, float) + 90.0, 0.0, math.radians(eps_deg))


def planet_speculum(lam, ramc, lat_deg, eps_deg):
    """
    مصفوفة الـ Speculum لنقطة زودياكية (عرض = 0) — الملحق I:
    MD, SA, قطب الكوكب φ, ADP, OA/OD. تُرجع (φ_rad, oa_or_od_deg, is_oa).
    """
    lat = math.radians(lat_deg)
    lam = np.asarray(lam, float)
    ramc = np.asarray(ramc, float)
    ra = ra_of_lon(lam, eps_deg)
    dec = np.radians(dec_of_lon(lam, eps_deg))
    ad = np.arcsin(np.clip(math.tan(lat) * np.tan(dec), -1.0, 1.0))      # sin AD = tanΦ tanδ
    d_mc = _wrap180(ra - ramc)
    d_ic = _wrap180(ra - (ramc + 180.0))
    above = np.abs(d_mc) <= 90.0 + np.degrees(ad)
    md = np.where(above, np.abs(d_mc), np.abs(d_ic))
    sa = np.where(above, 90.0 + np.degrees(ad), 90.0 - np.degrees(ad))
    sa = np.where(np.abs(sa) < 1e-9, 1e-9, sa)
    phi_p = np.arctan(md / sa * math.tan(lat))                           # tan φ = MD/SA · tanΦ
    adp = np.arcsin(np.clip(np.tan(phi_p) * np.tan(dec), -1.0, 1.0))     # sin ADP = tan φ tan δ
    is_oa = np.where(above, d_mc >= 0.0, d_ic < 0.0)                     # الربعان 1 و2 → OA، 3 و4 → OD
    oa_od = np.where(is_oa, ra - np.degrees(adp), ra + np.degrees(adp)) % 360.0
    return phi_p, oa_od, is_oa


def direct_planet(lam, ramc, lat_deg, eps_deg, arc):
    """موضع كوكب (نقطة زودياكية) بعد تسييره قوسًا arc (±) — الكتاب ص69-70."""
    phi_p, oa_od, is_oa = planet_speculum(lam, ramc, lat_deg, eps_deg)
    e = math.radians(eps_deg)
    eps_signed = np.where(is_oa, e, -e)
    return lam_from_oa(oa_od + arc, phi_p, eps_signed)


# ----------------------------------------------------------------------------
# الأفيمريس
# ----------------------------------------------------------------------------
def gmst_deg(jd):
    return (280.46061837 + 360.98564736629 * (np.asarray(jd, float) - 2451545.0)) % 360.0


def _interp_grid(raw: Callable[[float], Dict[str, float]], jd: np.ndarray) -> Dict[str, np.ndarray]:
    """تقييم raw على شبكة كل ~10 دقائق ثم استيفاء خطي (خطأ القمر < 0.03′)."""
    jd = np.atleast_1d(np.asarray(jd, float))
    lo, hi = float(jd.min()), float(jd.max())
    if jd.size <= 3 or hi - lo < 1e-9:
        vals = [raw(float(j)) for j in jd]
        return {k: np.array([v[k] for v in vals]) for k in vals[0]}
    n = int(min(max((hi - lo) * 144.0 + 2, 3), 600))
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

    def eps(self, jd: float) -> float:
        raise NotImplementedError

    def ramc(self, jd, lon: float) -> np.ndarray:
        raise NotImplementedError


class SwissEphemeris(Ephemeris):
    _IDS = {'SUN': 0, 'MOON': 1, 'MER': 2, 'VEN': 3, 'MAR': 4,
            'JUP': 5, 'SAT': 6, 'URA': 7, 'NEP': 8, 'PLU': 9}

    def __init__(self, ephe_path: Optional[str] = None):
        import os
        import swisseph as swe
        self.swe = swe
        if ephe_path:
            swe.set_ephe_path(ephe_path)
        has_files = bool(ephe_path and os.path.isdir(ephe_path) and
                         any(f.endswith('.se1') for f in os.listdir(ephe_path)))
        self.flags = swe.FLG_SWIEPH if has_files else swe.FLG_MOSEPH   # Moshier عند غياب الملفات

    def _raw(self, jd: float) -> Dict[str, float]:
        swe = self.swe
        out = {k: swe.calc_ut(jd, i, self.flags)[0][0] for k, i in self._IDS.items()}
        out['NN'] = swe.calc_ut(jd, swe.MEAN_NODE, self.flags)[0][0]      # العقدة المتوسطة فقط (ص36)
        out['SN'] = (out['NN'] + 180.0) % 360.0
        return out

    def lons(self, jd):
        return _interp_grid(self._raw, jd)

    def eps(self, jd: float) -> float:
        return float(self.swe.calc_ut(jd, self.swe.ECL_NUT, self.flags)[0][0])

    def ramc(self, jd, lon: float):
        jd = np.atleast_1d(np.asarray(jd, float))
        st = np.array([self.swe.sidtime(float(j)) for j in jd])           # ساعات، ظاهري
        return (st * 15.0 + lon) % 360.0


# ----------------------------------------------------------------------------
# مرشّحات الوقت
# ----------------------------------------------------------------------------
def jd_from_utc(d: dt.datetime) -> float:
    return (d - dt.datetime(1970, 1, 1)).total_seconds() / 86400.0 + 2440587.5


def make_candidates(birth_date: dt.date, start_hour: int, span_hours: float, step_s: int,
                    to_utc: Callable[[dt.datetime], dt.datetime], anchor: str = 'forward'):
    """
    نافذة محلية [start_hour, start_hour+span). للنافذة 22→01: anchor='forward' تبدأ 22:00 في يوم
    الميلاد المُدخل وتنتهي 01:00 صباح اليوم التالي؛ 'backward' تبدأ 22:00 من اليوم السابق.
    """
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


def build_natal(eph: Ephemeris, jd, lat: float, lon: float) -> Natal:
    jd = np.atleast_1d(np.asarray(jd, float))
    eps = eph.eps(float(jd[jd.size // 2]))
    ramc = eph.ramc(jd, lon)
    return Natal(jd, ramc, eps, lat, lon, eph.lons(jd), all_cusps(ramc, lat, eps))


def chart_points(natal: Natal, i: int = 0) -> dict:
    asc = float(natal.cusps['AS'][i]); mc = float(natal.cusps['MC'][i])
    sun = float(natal.pl['SUN'][i]); moon = float(natal.pl['MOON'][i])
    ep = float(east_point(natal.ramc[i], natal.eps))
    return dict(ramc=float(natal.ramc[i]), asc=asc, mc=mc, ep=ep,
                pof=(asc + moon - sun) % 360.0,
                ra_ep=float((natal.ramc[i] + 90.0) % 360.0),
                cusps={k: float(v[i]) for k, v in natal.cusps.items()},
                planets={k: float(v[i]) for k, v in natal.pl.items()})


# ----------------------------------------------------------------------------
# الأحداث والتسجيل
# ----------------------------------------------------------------------------
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
    tech: str
    text: str
    orb: float      # دقائق قوسية
    score: float


def _aspect_matrix(lam_a, lam_b, lim_major, lim_minor, aspects):
    d = np.atleast_1d((np.asarray(lam_a, float) - np.asarray(lam_b, float)) % 360.0)
    A = np.array(aspects, float)[:, None]
    o = np.minimum(np.abs(d[None, :] - A), np.abs(d[None, :] - (360.0 - A))) * 60.0
    lim = np.where(np.isin(A, (0.0, 180.0)), lim_major, lim_minor)
    w = np.clip(1.0 - o / lim, 0.0, None) * np.array([ASPECT_W[int(a)] for a in aspects])[:, None]
    return o, w


class _Acc:
    def __init__(self, n: int, explain: bool):
        self.total = np.zeros(n)
        self.explain = explain
        self.hits: List[Hit] = []

    def add(self, tech, desc, lam_a, lam_b, factor, tech_w, lim_maj, lim_min, aspects):
        o, w = _aspect_matrix(lam_a, lam_b, lim_maj, lim_min, aspects)
        sc = BASE_SCORE * factor * tech_w * w
        self.total += sc.sum(axis=0)
        if self.explain:
            for i, a in enumerate(aspects):
                if sc[i, 0] > 0:
                    self.hits.append(Hit(tech, f"{desc[0]}  {a}°  {desc[1]}", float(o[i, 0]), float(sc[i, 0])))


def _lists(spec):
    sigs = [(s, 1.0) for s in spec['sig']] + [(s, 0.5) for s in spec['sig2']]
    pls = [(p, 1.0) for p in spec['pl']] + [(p, 0.5) for p in spec['pl2']]
    return sigs, pls


def _primary(acc, natal, spec, days):
    sigs, pls = _lists(spec)
    A = days * NAIBOD_PER_DAY
    for sgn, dlab in ((1, 'مباشر'), (-1, 'عكسي')):
        arc = sgn * A
        dc = all_cusps(natal.ramc + arc, natal.lat, natal.eps)
        for s, fs in sigs:
            for p, fp in pls:
                acc.add('اتجاه أولي', (f"{FACTOR_AR[s]} ({dlab})", PLANET_AR[p]),
                        dc[s], natal.pl[p], fs * fp, 1.0, PD_ORB_MAJOR, PD_ORB_MINOR, ASPECTS)
        for p, fp in pls:
            ld = direct_planet(natal.pl[p], natal.ramc, natal.lat, natal.eps, arc)
            for s, fs in sigs:
                acc.add('اتجاه أولي', (f"{PLANET_AR[p]} ({dlab})", FACTOR_AR[s]),
                        ld, natal.cusps[s], fs * fp, 0.8, PD_ORB_MAJOR, PD_ORB_MINOR, ASPECTS)


def _sec_limits(p):
    return SEC_ORB_MOON if p == 'MOON' else (SEC_ORB[p], SEC_ORB[p])


def _secondary(acc, eph, natal, spec, days):
    sigs, pls = _lists(spec)
    yrs = days / TROPICAL_YEAR
    sun0 = ra_of_lon(natal.pl['SUN'], natal.eps)
    for jdx, lab in ((natal.jd + yrs, 'تقدمي'), (natal.jd - yrs, 'تراجعي')):
        pl = eph.lons(jdx)
        arc = _wrap180(ra_of_lon(pl['SUN'], natal.eps) - sun0)          # قوس شمسي في RA (ص86)
        dc = all_cusps(natal.ramc + arc, natal.lat, natal.eps)
        for p, fp in pls:
            lmj, lmn = _sec_limits(p)
            for s, fs in sigs:
                acc.add('تسيير ثانوي', (f"{FACTOR_AR[s]} ({lab})", PLANET_AR[p]),
                        dc[s], natal.pl[p], fs * fp, 0.8, lmj, lmn, ASPECTS)
                acc.add('تسيير ثانوي', (f"{PLANET_AR[p]} ({lab})", FACTOR_AR[s]),
                        pl[p], natal.cusps[s], fs * fp, 0.7, lmj, lmn, ASPECTS)


def _solar_arc(eph, acc, natal, spec, days):
    sigs, pls = _lists(spec)
    yrs = days / TROPICAL_YEAR
    sun_p = eph.lons(natal.jd + yrs)['SUN']
    sa = (sun_p - natal.pl['SUN']) % 360.0                              # قوس شمسي في الطول
    for s, fs in sigs:
        for p, fp in pls:
            acc.add('قوس شمسي', (f"{FACTOR_AR[s]} (+قوس)", PLANET_AR[p]),
                    natal.cusps[s] + sa, natal.pl[p], fs * fp, 0.5, SA_ORB_MAJOR, SA_ORB_MINOR, ASPECTS)
            acc.add('قوس شمسي', (f"{PLANET_AR[p]} (+قوس)", FACTOR_AR[s]),
                    natal.pl[p] + sa, natal.cusps[s], fs * fp, 0.4, SA_ORB_MAJOR, SA_ORB_MINOR, ASPECTS)


def _transits(eph, acc, natal, ev, spec):
    sigs, pls = _lists(spec)
    pl_dir = eph.lons(np.array([ev.jd]))
    pl_pre = eph.lons(2.0 * natal.jd - ev.jd)                           # التاريخ ما قبل الولادة (ص159)
    for lab, pl in (('مباشر', pl_dir), ('ما قبل الولادة', pl_pre)):
        for p, fp in pls:
            if p == 'MOON' and not ev.has_time:
                continue                                                 # ساعة الحدث مجهولة → القمر غير موثوق
            for s, fs in sigs:
                acc.add('عبور', (f"{PLANET_AR[p]} عابر ({lab})", FACTOR_AR[s]),
                        pl[p], natal.cusps[s], fs * fp, 0.35, TR_ORB, TR_ORB, MAJOR_ASPECTS)


ALL_TECH = ('PD', 'SD', 'SA', 'TR')


def score_events(eph, natal, events: Sequence[Event], gender: str, explain: bool = False,
                 techniques: Sequence[str] = ALL_TECH):
    n = natal.jd.size
    total = np.zeros(n)
    detail = []
    for ev in events:
        spec = resolve_spec(ev.kind, gender)
        acc = _Acc(n, explain)
        days = ev.jd - natal.jd
        if 'PD' in techniques:
            _primary(acc, natal, spec, days)
        if 'SD' in techniques:
            _secondary(acc, eph, natal, spec, days)
        if 'SA' in techniques:
            _solar_arc(eph, acc, natal, spec, days)
        if 'TR' in techniques:
            _transits(eph, acc, natal, ev, spec)
        total += ev.weight * acc.total
        if explain:
            detail.append((ev, sorted(acc.hits, key=lambda h: -h.score)))
    return total, detail


# ----------------------------------------------------------------------------
# البحث والتصحيح
# ----------------------------------------------------------------------------
def _peaks(score: np.ndarray, step_s: int, n: int, exclusion_s: int = 240):
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


def _plateau_s(score, i, step_s, frac=0.85):
    thr = score[i] * frac
    l = r = i
    while l > 0 and score[l - 1] >= thr:
        l -= 1
    while r < len(score) - 1 and score[r + 1] >= thr:
        r += 1
    return (r - l + 1) * step_s


def describe_lon(lam: float) -> str:
    lam = lam % 360.0
    sign = SIGNS_AR[int(lam // 30)]
    deg = lam % 30.0
    d = int(deg); m = int((deg - d) * 60); s = int(round(((deg - d) * 60 - m) * 60))
    if s == 60:
        s = 0; m += 1
    if m == 60:
        m = 0; d += 1
    return f"{d}°{m:02d}′{s:02d}″ {sign}"


def rectify(eph: Ephemeris, birth_date: dt.date, lat: float, lon: float,
            to_utc: Callable[[dt.datetime], dt.datetime], events: Sequence[Event], gender: str,
            start_hour: int, span_hours: float = 3.0, step_s: int = 8, anchor: str = 'forward',
            techniques: Sequence[str] = ALL_TECH, n_peaks: int = 5,
            null_runs: int = 0, seed: int = 7) -> dict:
    locs, jd = make_candidates(birth_date, start_hour, span_hours, step_s, to_utc, anchor)
    natal = build_natal(eph, jd, lat, lon)
    score, _ = score_events(eph, natal, events, gender, False, techniques)
    peaks = _peaks(score, step_s, n_peaks)

    results = []
    for i in peaks:
        plateau = _plateau_s(score, i, step_s)
        # صقل بخطوة ثانية واحدة حول القمة
        fl = [locs[i] + dt.timedelta(seconds=k) for k in range(-2 * step_s, 2 * step_s + 1)]
        fjd = np.array([jd_from_utc(to_utc(x)) for x in fl])
        fn = build_natal(eph, fjd, lat, lon)
        fs_, _ = score_events(eph, fn, events, gender, False, techniques)
        j = int(np.argmax(fs_))
        n1 = build_natal(eph, fjd[j:j + 1], lat, lon)
        _, detail = score_events(eph, n1, events, gender, True, techniques)
        pts = chart_points(n1)
        results.append(dict(time=fl[j], jd=float(fjd[j]), score=float(fs_[j]), plateau_s=plateau,
                            points=pts, detail=detail))

    results.sort(key=lambda r: -r['score'])          # الترتيب النهائي بعد الصقل لا قبله
    out = dict(candidates=results, n_candidates=len(locs), step_s=step_s,
               scores=score, times=locs, null=None)

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
            sc, _ = score_events(eph, natal, shifted, gender, False, techniques)
            null_max.append(float(sc.max()))
        p = (1 + sum(m >= real_max for m in null_max)) / (null_runs + 1)
        out['null'] = dict(p=p, real=real_max, null_mean=float(np.mean(null_max)),
                           null_p95=float(np.percentile(null_max, 95)), runs=null_runs)
    return out
