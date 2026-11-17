# -*- coding: utf-8 -*-
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

# ==============================================================================
# ستايل الواجهة الاحترافية (خلفية سوداء كاملة للجميع + نصوص بيضاء ناصعة)
# ==============================================================================
CUSTOM_UI_STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&display=swap');

/* إعدادات الخط والاتجاه والخلفية العامة السوداء */
html, body, .stApp {
    font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif !important;
    background-color: #000000 !important;
    color: #FFFFFF !important;
}

.stApp {
    direction: rtl;
    text-align: right;
    background: #000000 !important;
}

header[data-testid="stHeader"] {
    background: rgba(0, 0, 0, 0.85) !important;
    backdrop-filter: blur(10px) !important;
}

/* ==========================================================================
   1. العناوين والنصوص العامة بلون أبيض ناصع
   ========================================================================== */
h1, h2, h3, h4, h5, h6, .stHeading {
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    color: #FFFFFF !important;
    text-shadow: 0 0 10px rgba(255, 255, 255, 0.2) !important;
}

h1 {
    font-size: 2.2rem !important;
    border-bottom: 2px solid #333333;
    padding-bottom: 8px;
    margin-bottom: 18px !important;
    color: #FFFFFF !important;
}

h2, h3 {
    color: #FFFFFF !important;
    border-right: 4px solid #FFFFFF;
    padding-right: 12px !important;
    margin-top: 15px !important;
}

p, span, label, div {
    color: #FFFFFF !important;
}

.stCaption, small, [data-testid="stCaptionContainer"] {
    color: #CCCCCC !important;
    font-size: 0.88rem !important;
    line-height: 1.6 !important;
}

/* بطاقات الأعمدة وحاويات الإدخال */
[data-testid="column"] {
    background: #0A0A0A !important;
    border: 1px solid #262626 !important;
    border-radius: 12px !important;
    padding: 20px 22px !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.8) !important;
    transition: all 0.3s ease-in-out !important;
}

[data-testid="column"]:hover {
    border-color: #444444 !important;
}

/* ==========================================================================
   2. حقول الإدخال، الاختيار، والقوائم المنسدلة: خلفية سوداء + نص أبيض ناصع
   ========================================================================== */
input, textarea, [data-baseweb="input"], [data-baseweb="base-input"] {
    background-color: #0D0D0D !important;
    color: #FFFFFF !important;
    border-color: #333333 !important;
    border-radius: 8px !important;
    font-family: 'Cairo', sans-serif !important;
}

input:focus, textarea:focus, [data-baseweb="input"]:focus-within {
    border-color: #FFFFFF !important;
    box-shadow: 0 0 12px rgba(255, 255, 255, 0.3) !important;
}

[data-baseweb="select"] {
    background-color: #0D0D0D !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
}

[data-baseweb="select"] > div {
    background-color: #0D0D0D !important;
    border-color: #333333 !important;
    color: #FFFFFF !important;
}

/* القوائم المنسدلة العائمة والخيارات بالداخل بالكامل */
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
div[data-baseweb="menu"],
ul[data-baseweb="menu"],
ul[role="listbox"],
div[role="listbox"],
div[class*="menu"],
div[class*="popover"],
div[class*="dropdown"],
div[class*="overlay"],
div[class*="portal"],
div[data-floating-ui-portal] > div,
div[id^="base-ui-portal"] > div,
body > div[style*="position: absolute"],
body > div[style*="position: fixed"] {
    background-color: #000000 !important;
    background: #000000 !important;
    border: 1px solid #444444 !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.95) !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
}

div[data-baseweb="popover"] li,
div[data-baseweb="popover"] div,
ul[role="listbox"] li,
ul[role="listbox"] div,
div[role="listbox"] div,
li[role="option"],
div[role="option"],
div[class*="menu-item"],
div[class*="option-item"] {
    background-color: #000000 !important;
    background: #000000 !important;
    color: #FFFFFF !important;
    border-bottom: 1px solid #1A1A1A !important;
    font-family: 'Cairo', sans-serif !important;
}

div[data-baseweb="popover"] li:hover,
div[data-baseweb="popover"] li[aria-selected="true"],
ul[role="listbox"] li:hover,
ul[role="listbox"] li[aria-selected="true"],
div[role="listbox"] div:hover,
div[role="listbox"] div[aria-selected="true"],
li[role="option"]:hover,
li[role="option"][aria-selected="true"],
div[role="option"]:hover,
div[role="option"][aria-selected="true"] {
    background-color: #222222 !important;
    background: #222222 !important;
    color: #FFFFFF !important;
    font-weight: 800 !important;
}

div[data-baseweb="popover"] span,
ul[role="listbox"] span,
li[role="option"] span,
div[role="option"] span {
    color: #FFFFFF !important;
}

/* وسم الاختيارات المتعددة */
[data-baseweb="tag"] {
    background: #1A1A1A !important;
    border: 1px solid #444444 !important;
    border-radius: 6px !important;
    color: #FFFFFF !important;
}

[data-baseweb="tag"] span {
    color: #FFFFFF !important;
}

/* ==========================================================================
   3. جدول إدخال الأحداث والجداول: خلفية سوداء كاملة وخط أبيض ناصع
   ========================================================================== */
[data-testid="stDataEditor"],
[data-testid="stDataEditor"] > div,
[data-testid="stDataEditor"] iframe,
[data-testid="stDataFrame"] {
    background-color: #000000 !important;
    background: #000000 !important;
    border: 1px solid #333333 !important;
    border-radius: 8px !important;
    padding: 0 !important;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.8) !important;
    color: #FFFFFF !important;
}

[data-testid="stDataEditor"] canvas {
    background-color: #000000 !important;
}

[data-testid="stDataEditor"] *,
[data-testid="stDataFrame"] * {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

/* محرر خلايا الجدول عند النقر */
div[data-testid="data-grid-overlay-editor"],
div[class*="overlay-editor"],
div[class*="gdg-input"] {
    background-color: #0A0A0A !important;
    background: #0A0A0A !important;
    color: #FFFFFF !important;
    border: 2px solid #555555 !important;
    border-radius: 6px !important;
}

div[data-testid="data-grid-overlay-editor"] input,
div[class*="overlay-editor"] input,
div[data-testid="data-grid-overlay-editor"] select,
div[class*="overlay-editor"] select {
    background-color: #0A0A0A !important;
    background: #0A0A0A !important;
    color: #FFFFFF !important;
    font-weight: 800 !important;
    font-size: 1rem !important;
}

div[data-testid="data-grid-overlay-editor"] div,
div[data-testid="data-grid-overlay-editor"] li,
div[class*="overlay-editor"] div,
div[class*="overlay-editor"] li {
    background-color: #000000 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    padding: 6px 12px !important;
}

div[data-testid="data-grid-overlay-editor"] li:hover,
div[data-testid="data-grid-overlay-editor"] div:hover,
div[class*="overlay-editor"] li:hover,
div[class*="overlay-editor"] div:hover {
    background-color: #262626 !important;
    color: #FFFFFF !important;
    font-weight: 900 !important;
}

/* ==========================================================================
   4. منع انعكاس الحروف في حقول التاريخ والوقت
   ========================================================================== */
input[type="date"],
input[type="time"],
input[type="datetime-local"],
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input,
[data-baseweb="input"] input[type="date"],
[data-baseweb="input"] input[type="time"],
div[data-testid="data-grid-overlay-editor"] input[type="date"],
div[class*="overlay-editor"] input[type="date"],
::-webkit-datetime-edit,
::-webkit-datetime-edit-fields-wrapper,
::-webkit-datetime-edit-text,
::-webkit-datetime-edit-month-field,
::-webkit-datetime-edit-day-field,
::-webkit-datetime-edit-year-field {
    direction: ltr !important;
    text-align: right !important;
    unicode-bidi: isolate !important;
    font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif !important;
    color: #FFFFFF !important;
}

input[type="text"],
textarea,
input:not([type="date"]):not([type="time"]):not([type="number"]) {
    direction: rtl !important;
    text-align: right !important;
    unicode-bidi: plaintext !important;
}

/* ==========================================================================
   5. المؤشرات الفلكية، الأزرار، التنبيهات والأكورديون
   ========================================================================== */
[data-testid="stMetric"] {
    background: #0D0D0D !important;
    border: 1px solid #333333 !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.8) !important;
    text-align: center !important;
}

[data-testid="stMetricValue"] {
    color: #FFFFFF !important;
    font-size: 1.65rem !important;
    font-weight: 900 !important;
    text-shadow: 0 0 12px rgba(255, 255, 255, 0.3) !important;
    display: flex;
    justify-content: center;
}

[data-testid="stMetricLabel"] {
    color: #CCCCCC !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    display: flex;
    justify-content: center;
}

/* الأزرار العادية */
.stButton > button {
    background: #171717 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    font-size: 1.05rem !important;
    border: 1px solid #444444 !important;
    border-radius: 8px !important;
    padding: 0.6rem 2rem !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5) !important;
    transition: all 0.3s ease !important;
    font-family: 'Cairo', sans-serif !important;
}

.stButton > button:hover {
    background: #262626 !important;
    color: #FFFFFF !important;
    border-color: #888888 !important;
    transform: translateY(-2px);
}

/* الزر الرئيسي لإطلاق التصحيح */
.stButton > button[kind="primary"] {
    background: #FFFFFF !important;
    color: #000000 !important;
    font-size: 1.25rem !important;
    font-weight: 900 !important;
    padding: 0.8rem 3rem !important;
    border: 1px solid #FFFFFF !important;
    box-shadow: 0 6px 25px rgba(255, 255, 255, 0.3) !important;
}

.stButton > button[kind="primary"]:hover {
    background: #E6E6E6 !important;
    color: #000000 !important;
    box-shadow: 0 8px 30px rgba(255, 255, 255, 0.5) !important;
    transform: translateY(-3px);
}

/* التنبيهات والمعلومات */
[data-testid="stAlert"] {
    background-color: #0D0D0D !important;
    border-right: 5px solid #FFFFFF !important;
    border-top: 1px solid #333333 !important;
    border-bottom: 1px solid #333333 !important;
    border-left: 1px solid #333333 !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
}

[data-testid="stAlert"] * {
    color: #FFFFFF !important;
}

/* الأكورديون والقوائم القابلة للتوسيع */
[data-testid="stExpander"] {
    background: #0A0A0A !important;
    border: 1px solid #2B2B2B !important;
    border-radius: 8px !important;
    margin-bottom: 10px !important;
}

[data-testid="stExpander"] details summary {
    color: #FFFFFF !important;
    font-weight: 700 !important;
}

[data-testid="stExpander"] details summary:hover {
    color: #CCCCCC !important;
}

[data-testid="stSlider"] div[role="slider"] {
    background-color: #FFFFFF !important;
    border: 2px solid #000000 !important;
    box-shadow: 0 0 10px #FFFFFF !important;
}

hr {
    border: none !important;
    height: 1px !important;
    background: #2E2E2E !important;
    margin: 28px 0 !important;
}

::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #000000;
}
::-webkit-scrollbar-thumb {
    background: #333333;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #555555;
}
</style>
"""

# ==============================================================================
# دالة توليد التقرير القابل للطباعة بصيغة HTML مخصصة
# ==============================================================================
def generate_html_report(name: str, gender_ar: str, birth_date: datetime.date,
                         win_label: str, selected_country: str, city_str: str,
                         lat: float, lon: float, tz_str: str,
                         events_rows: pd.DataFrame, res: dict, cands: list) -> str:
    top = cands[0]
    pts = top["points"]
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # جدول المرشحين
    cands_rows_html = ""
    for i, c in enumerate(cands):
        cands_rows_html += f"""
        <tr>
            <td style="text-align:center; font-weight:bold;">{i + 1}</td>
            <td style="text-align:center;">{c['time'].strftime('%Y-%m-%d %H:%M:%S')}</td>
            <td style="text-align:center; font-weight:bold; color:#000;">{round(c['score'], 1)}</td>
            <td style="text-align:center;">{E.describe_lon(c['points']['asc'])}</td>
            <td style="text-align:center;">{E.describe_lon(c['points']['mc'])}</td>
            <td style="text-align:center;">{E.describe_lon(c['points']['ep'])}</td>
            <td style="text-align:center;">{c['plateau_s']} ث</td>
        </tr>
        """

    # جدول أحداث الماضي
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

    # تفاصيل تطابقات المرشح الأول
    detail_html = ""
    for ev, hits in top["detail"]:
        detail_html += f"""
        <div style="margin-top:15px; border:1px solid #dcdcdc; border-radius:8px; padding:12px; background:#fafafa; page-break-inside:avoid;">
            <h4 style="margin:0 0 8px 0; color:#111;">📌 {ev.label} — <span>({len(hits)} تطابق)</span></h4>
        """
        if not hits:
            detail_html += "<p style='color:#777; margin:4px 0;'>لا تطابقات ضمن السماحيات لهذا الحدث عند هذا الوقت.</p>"
        else:
            detail_html += "<ul style='margin:4px 0; padding-right:20px;'>"
            for h in hits[:15]:
                detail_html += f"<li><b style='color:#000;'>[{h.tech}]</b> {h.text} — فارق: <b>{h.orb:.1f}′</b> — نقاط: <b>{h.score:.1f}</b></li>"
            detail_html += "</ul>"
        detail_html += "</div>"

    null_html = ""
    if res.get("null"):
        n = res["null"]
        null_html = f"""
        <div style="background:#f2f2f2; border-right:4px solid #111; padding:12px 15px; margin:15px 0; border-radius:4px;">
            <b>اختبار الصدفة ({n['runs']} محاكاة):</b> أعلى نقاط حقيقية = <b>{n['real']:.1f}</b> مقابل متوسط <b>{n['null_mean']:.1f}</b> وأعلى 95٪ = <b>{n['null_p95']:.1f}</b> في الأحداث المُزاحة؛ القيمة التقريبية <b>p ≈ {n['p']:.3f}</b>.
        </div>
        """

    ratio_html = ""
    if len(cands) > 1:
        ratio = top["score"] / max(cands[1]["score"], 1e-9)
        diff_text = 'تمييز جيد' if ratio >= 1.25 else 'تمييز ضعيف — أضف أحداثًا' if ratio < 1.1 else 'تمييز متوسط'
        ratio_html = f"""
        <div style="background:#f9f9f9; border-right:4px solid #555; padding:12px 15px; margin:15px 0; border-radius:4px;">
            عرض هضبة التطابق حول الوقت الأول ≈ <b>{top['plateau_s']} ثانية</b>. 
            نسبة نقاط الأول إلى الثاني = <b>{ratio:.2f}</b> ({diff_text}).
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تقرير تصحيح الطالع الفلكي - {name}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
        body {{
            font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
            background-color: #f7f9fc;
            color: #111;
            margin: 0;
            padding: 25px;
            direction: rtl;
            text-align: right;
        }}
        .report-card {{
            max-width: 950px;
            margin: auto;
            background: #fff;
            padding: 35px 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            border: 1px solid #e0e5ed;
        }}
        .header {{
            border-bottom: 3px solid #111;
            padding-bottom: 15px;
            margin-bottom: 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{
            margin: 0;
            color: #000;
            font-size: 24px;
            font-weight: 800;
        }}
        .header p {{
            margin: 5px 0 0 0;
            color: #666;
            font-size: 14px;
        }}
        .btn-print {{
            background: #000;
            color: #fff;
            border: 1px solid #000;
            padding: 10px 22px;
            border-radius: 8px;
            cursor: pointer;
            font-family: 'Cairo', sans-serif;
            font-weight: bold;
            font-size: 15px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
            transition: all 0.2s;
        }}
        .btn-print:hover {{
            background: #333;
        }}
        .section-title {{
            color: #000;
            border-right: 4px solid #000;
            padding-right: 10px;
            margin: 25px 0 12px 0;
            font-size: 18px;
            font-weight: 700;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px 12px;
        }}
        th {{
            background-color: #000;
            color: #fff;
            font-weight: 700;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .highlight-box {{
            background: #000;
            color: #fff;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #333;
            margin: 20px 0;
            text-align: center;
        }}
        .highlight-box h2 {{
            margin: 0;
            color: #fff;
            font-size: 26px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 15px;
        }}
        .metric-cell {{
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 8px;
            padding: 12px;
        }}
        .metric-cell div:first-child {{
            font-size: 13px;
            color: #ccc;
            margin-bottom: 5px;
        }}
        .metric-cell div:last-child {{
            font-size: 18px;
            font-weight: 800;
            color: #fff;
        }}
        .footer {{
            margin-top: 35px;
            border-top: 1px solid #ddd;
            padding-top: 15px;
            font-size: 12px;
            color: #777;
            text-align: center;
        }}
        @media print {{
            body {{
                background: #fff;
                padding: 0;
            }}
            .report-card {{
                box-shadow: none;
                border: none;
                padding: 0;
                max-width: 100%;
            }}
            .no-print {{
                display: none !important;
            }}
            .highlight-box {{
                background: #f4f4f4 !important;
                color: #000 !important;
                border: 2px solid #000 !important;
            }}
            .highlight-box h2 {{
                color: #000 !important;
            }}
            .metric-cell {{
                background: #fff !important;
                border: 1px solid #ccc !important;
            }}
            .metric-cell div:first-child {{
                color: #555 !important;
            }}
            .metric-cell div:last-child {{
                color: #000 !important;
            }}
            th {{
                background-color: #000 !important;
                color: #fff !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-card">
        <div class="header">
            <div>
                <h1>نظام تصحيح الطالع الفلكي المتقدم</h1>
                <p>تاريخ استخراج التقرير: {now_str} | تطوير الفلكي استرو رادار</p>
            </div>
            <div class="no-print">
                <button onclick="window.print()" class="btn-print">🖨️ طباعة التقرير / حفظ PDF</button>
            </div>
        </div>

        <div class="highlight-box">
            <div style="font-size:16px; color:#ddd; margin-bottom:5px;">🕒 أرجح وقت ميلاد محلي مصحح:</div>
            <h2>{top['time'].strftime('%H:%M:%S')} &nbsp;&nbsp; ({top['time'].strftime('%Y-%m-%d')})</h2>
            <div class="metrics-grid">
                <div class="metric-cell">
                    <div>🎯 الطالع AS</div>
                    <div>{E.describe_lon(pts['asc'])}</div>
                </div>
                <div class="metric-cell">
                    <div>⛰️ وتد السماء MC</div>
                    <div>{E.describe_lon(pts['mc'])}</div>
                </div>
                <div class="metric-cell">
                    <div>🧭 النقطة الشرقية EP</div>
                    <div>{E.describe_lon(pts['ep'])}</div>
                </div>
            </div>
            <div style="margin-top:10px; font-size:12px; color:#ccc;">
                RAMC = {pts['ramc']:.4f}° | RA(EP) = RAMC + 90° = {pts['ra_ep']:.4f}°
            </div>
        </div>

        {ratio_html}
        {null_html}

        <div class="section-title">بيانات الشخص ومكان الميلاد</div>
        <table>
            <tr>
                <th style="width:25%;">الاسم</th>
                <td>{name}</td>
                <th style="width:25%;">الجنس</th>
                <td>{gender_ar}</td>
            </tr>
            <tr>
                <th>تاريخ الميلاد المُدخل</th>
                <td>{birth_date}</td>
                <th>النافذة الزمنية المبحوثة</th>
                <td>{win_label}</td>
            </tr>
            <tr>
                <th>بلد ومدينة الميلاد</th>
                <td>{selected_country} - {city_str}</td>
                <th>المنطقة الزمنية</th>
                <td>{tz_str}</td>
            </tr>
            <tr>
                <th>الإحداثيات الجغرافية</th>
                <td colspan="3">خط العرض: {lat:.4f} | خط الطول: {lon:.4f}</td>
            </tr>
        </table>

        <div class="section-title">أحداث الماضي المعتمدة في التصحيح ({len(events_rows)} أحداث)</div>
        <table>
            <thead>
                <tr>
                    <th>نوع الحدث</th>
                    <th style="text-align:center;">التاريخ</th>
                    <th style="text-align:center;">الساعة</th>
                    <th style="text-align:center;">الوزن</th>
                </tr>
            </thead>
            <tbody>
                {ev_rows_html}
            </tbody>
        </table>

        <div class="section-title">قائمة المرشحين مرتبة حسب قوة التطابق</div>
        <table>
            <thead>
                <tr>
                    <th style="text-align:center;">الترتيب</th>
                    <th style="text-align:center;">الوقت المحلي</th>
                    <th style="text-align:center;">النقاط</th>
                    <th style="text-align:center;">الطالع AS</th>
                    <th style="text-align:center;">وتد السماء MC</th>
                    <th style="text-align:center;">النقطة الشرقية EP</th>
                    <th style="text-align:center;">عرض الهضبة</th>
                </tr>
            </thead>
            <tbody>
                {cands_rows_html}
            </tbody>
        </table>

        <div class="section-title">تفصيل التطابقات الفلكية للمرشح الأول</div>
        {detail_html}

        <div class="footer">
            ملاحظات: الدقة تتحدد بعدد الأحداث وجودتها وصحة تاريخها، لا بالبرنامج وحده. 
            المنطقة الزمنية التاريخية (DST/LMT) قد تحمل خطأ في التواريخ القديمة. المحرك مختبَر لنصف الكرة الشمالي.
        </div>
    </div>
</body>
</html>"""
    return html

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
    manual = st.checkbox("إدخال الإحداثيات يدويًا (أدق)")
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
st.caption("أضف كل حدث مؤرَّخ تعرفه (وفاة، ولادة، زواج،…). كلما زاد العدد وقلّ الغموض ارتفعت الدقة: "
           " وحدث واحد لا يكفي لتمييز وقت واحد عن غيره. "
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

            # زر تصدير وطباعة المخرجات كملف HTML احترافي
            city_display = city if (not manual and city_names) else f"إحداثيات يدوية ({lat:.4f}, {lon:.4f})"
            html_report = generate_html_report(
                name=name, gender_ar=gender_ar, birth_date=birth_date,
                win_label=win_label, selected_country=selected_country,
                city_str=city_display, lat=lat, lon=lon, tz_str=tz_str,
                events_rows=rows, res=res, cands=cands
            )

            st.download_button(
                label="📄 تحميل تقرير النتائج الكامل (ملف HTML جاهز للطباعة والحفظ كـ PDF) 🖨️",
                data=html_report.encode("utf-8"),
                file_name=f"تقرير_تصحيح_الطالع_{name}_{birth_date}.html",
                mime="text/html",
                type="secondary",
            )

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
