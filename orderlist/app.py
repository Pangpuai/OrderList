import os
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import Image as RLImage


# All paths resolved relative to this file — works regardless of cwd when streamlit is launched
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="ระบบสร้างใบสั่งซื้อ Giffarine ",
    page_icon="📦",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 0.5rem 1rem; }
</style>
""", unsafe_allow_html=True)

css_path = os.path.join(BASE_DIR, "styles.css")

if os.path.exists(css_path):
    with open(css_path, encoding="utf-8") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

# ─────────────────────────────────────────────
# LOAD PRODUCTS
# ─────────────────────────────────────────────

@st.cache_data
def load_products():
    csv_path = os.path.join(BASE_DIR, "giffarine_products.csv")
    df = pd.read_csv(csv_path)
    df["product_code"]     = df["product_code"].astype(str).str.strip()
    df["full_price_thb"]   = pd.to_numeric(df["full_price_thb"],   errors="coerce").fillna(0)
    df["member_price_thb"] = pd.to_numeric(df["member_price_thb"], errors="coerce").fillna(0)
    mask = df["member_price_thb"] == 0
    df.loc[mask, "member_price_thb"] = df.loc[mask, "full_price_thb"]
    return df

try:
    products = load_products()
except FileNotFoundError:
    st.error("❌ ไม่พบไฟล์ `giffarine_products.csv` — กรุณาวางไฟล์ในโฟลเดอร์เดียวกับ app.py")
    st.stop()

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

if "orders" not in st.session_state:
    st.session_state.orders = []

if "gifts" not in st.session_state:
    st.session_state.gifts = []

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def add_item(item, qty: int, is_gift: bool = False):
    """Add a product to the cart or gift list, incrementing quantity if already present."""
    code = str(item["product_code"])
    target = st.session_state.gifts if is_gift else st.session_state.orders

    for order in target:
        if order["รหัสสินค้า"] == code:
            order["จำนวน"] += qty
            order["ยอดรวม"] = order["ราคาสมาชิก"] * order["จำนวน"]
            st.toast(f"เพิ่มจำนวน {item['product_name']} แล้ว ✅")
            return

    if is_gift:
        target.append({
            "รหัสสินค้า": code,
            "ชื่อสินค้า": f"Free {item['product_name']}",
            "ราคาเต็ม":   0.0,
            "ราคาสมาชิก": 0.0,
            "จำนวน":      int(qty),
            "ยอดรวม":     0.0,
        })
    else:
        target.append({
            "รหัสสินค้า": code,
            "ชื่อสินค้า": item["product_name"],
            "ราคาเต็ม":   float(item["full_price_thb"]),
            "ราคาสมาชิก": float(item["member_price_thb"]),
            "จำนวน":      int(qty),
            "ยอดรวม":     float(item["member_price_thb"]) * int(qty),
        })

    label = "ของแถม" if is_gift else "สินค้า"
    st.toast(f"เพิ่ม{label} {item['product_name']} แล้ว ✅")


def register_fonts():
    """Register Thai fonts once; safe to call multiple times."""
    font_path = os.path.join(BASE_DIR, "font", "THSarabunNew.ttf")
    font_keng  = os.path.join(BASE_DIR, "font", "aying01unicode.ttf")
    try:
        pdfmetrics.registerFont(TTFont("THSarabunNew", font_path))
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("aying01unicode", font_keng))
    except Exception:
        pass


def build_pdf(orders_df, gifts_df, member_id, customer_name, Tai_name, order_date_str, order_status):

    pdf_buffer = BytesIO()
    register_fonts()

    doc = SimpleDocTemplate(
        pdf_buffer,
        leftMargin=70,
        rightMargin=50,
        topMargin=50,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MyTitle",
        parent=styles["Title"],
        fontName="THSarabunNew",
        fontSize=22,
    )

    normal_style = ParagraphStyle(
        "MyNormal",
        parent=styles["Normal"],
        fontName="THSarabunNew",
        fontSize=16,
        leading=20,
    )

    customer_style = ParagraphStyle(
        "CustomerInfo",
        parent=normal_style,
        fontName="THSarabunNew",
        leftIndent=20,
    )

    Tai_name_style = ParagraphStyle(
        "Tai_name",
        parent=normal_style,
        fontName="aying01unicode",
        leftIndent=25,
        fontSize=14,
    )

    summary_style = ParagraphStyle(
        "Summary",
        parent=normal_style,
        leftIndent=20,
    )

    right_style = ParagraphStyle(
        "RightText",
        parent=normal_style,
        alignment=TA_RIGHT,
    )

    # ── FIX 2: product_style defined so text wraps inside the cell ──
    product_style = ParagraphStyle(
        "ProductCell",
        parent=normal_style,
        fontName="THSarabunNew",
        fontSize=14,
        leading=17,
        wordWrap="CJK",
    )

    gift_product_style = ParagraphStyle(
        "GiftProductCell",
        parent=product_style,
        textColor=colors.black,
    )

    section_style = ParagraphStyle(
        "SectionHeading",
        parent=normal_style,
        fontName="THSarabunNew",
        fontSize=18,
        leading=22,
        spaceAfter=6,
    )

    content = []

    # ── Header ──────────────────────────────
    content.append(Paragraph("ใบสั่งซื้อสินค้า GIFFARINE  ", title_style))
    content.append(Spacer(1, 12))
    content.append(Paragraph(f"รหัสสมาชิก : {member_id or '-'}", customer_style))
    content.append(Paragraph(f"ชื่อผู้สั่งซื้อ : {customer_name or '-'}", customer_style))
    content.append(Paragraph(f"ၸိုဝ်ႈၵူၼ်းသင်ႇသိုဝ်ႉ : &nbsp;&nbsp;&nbsp; {Tai_name or '-'}", Tai_name_style))
    content.append(Paragraph(f"วันที่สั่งซื้อ : {order_date_str}", customer_style))
    content.append(Spacer(1, 12))

    # ── Orders table ─────────────────────────
    usable_width = doc.width

    col_widths = [
        usable_width * 0.07,  # ลำดับ
        usable_width * 0.12,  # รหัสสินค้า
        usable_width * 0.37,  # ชื่อสินค้า
        usable_width * 0.12,  # ราคาเต็ม
        usable_width * 0.12,  # ราคาสมาชิก
        usable_width * 0.08,  # จำนวน
        usable_width * 0.12,  # รวม
    ]

    table_header = ["ลำดับ", "รหัสสินค้า", "ชื่อสินค้า", "ราคาเต็ม", "ราคาสมาชิก", "จำนวน", "รวม"]
    table_data = [table_header]

    for i, (_, row) in enumerate(orders_df.iterrows(), start=1):
        table_data.append([
            str(i),
            str(row["รหัสสินค้า"]),
            Paragraph(str(row["ชื่อสินค้า"]), product_style),  # FIX 2: wraps
            f"{row['ราคาเต็ม']:,.2f}",
            f"{row['ราคาสมาชิก']:,.2f}",
            str(int(row["จำนวน"])),
            f"{row['ยอดรวม']:,.2f}",
        ])

    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
    ("GRID",       (0, 0), (-1, -1), 1, colors.black),
    ("BACKGROUND", (0, 0), (-1, 0), colors.lightskyblue),

    ("FONTNAME",   (0, 0), (-1, -1), "THSarabunNew"),
    ("FONTSIZE",   (0, 0), (-1, -1), 14),

    ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),

    # Header กลางทั้งหมด
    ("ALIGN",      (0, 0), (-1, 0), "CENTER"),

    # ลำดับ
    ("ALIGN",      (0, 1), (0, -1), "CENTER"),

    # รหัสสินค้า
    ("ALIGN",      (1, 1), (1, -1), "CENTER"),

    # ชื่อสินค้า
    ("ALIGN",      (2, 1), (2, -1), "LEFT"),

    # ราคาเต็ม
    ("ALIGN",      (3, 1), (3, -1), "RIGHT"),

    # ราคาสมาชิก
    ("ALIGN",      (4, 1), (4, -1), "RIGHT"),

    # จำนวน
    ("ALIGN",      (5, 1), (5, -1), "CENTER"),

    # รวม
    ("ALIGN",      (6, 1), (6, -1), "RIGHT"),
    
    ("TOPPADDING",    (0, 0), (-1, 0), 6),
    ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
    ("LEFTPADDING",  (0,0), (-1,-1), 4),
    ("RIGHTPADDING", (0,0), (-1,-1), 4),
]))

    content.append(table)
    content.append(Spacer(1, 15))

    # ── Summary ───────────────────────────────
    total_qty    = int(orders_df["จำนวน"].sum())
    total_amount = float(orders_df["ยอดรวม"].sum())

    content.append(Paragraph(f"จำนวนสินค้ารวม : {total_qty:,} ชิ้น", summary_style))
    content.append(Paragraph(f"ยอดรวมทั้งหมด : <font color='red'>{total_amount:,.2f}</font> บาท", summary_style))
    content.append(Paragraph("รับสินค้า โดย คำนวล รหัสสมาชิก 11152465", summary_style))

    # ── Status ────────────────────────────────
    status_color = colors.black
    status_style = ParagraphStyle(
        "StatusText",
        parent=normal_style,
        textColor=status_color,
        fontName="THSarabunNew",
        fontSize=16,
        leftIndent=20,
    )
    content.append(Spacer(1, 8))
    content.append(Paragraph(f"สถานะ : {order_status}", status_style))

    # ── Free Gift table ───────────────────────
    if not gifts_df.empty:
        content.append(Spacer(1, 20))
        content.append(Paragraph("ของแถม (Free Gift)", section_style))

        gift_data = [["ลำดับ", "รหัสสินค้า", "ชื่อสินค้า", "จำนวน", "ราคา"]]

        for i, (_, row) in enumerate(gifts_df.iterrows(), start=1):
            gift_data.append([
                str(i),
                str(row["รหัสสินค้า"]),
                Paragraph(str(row["ชื่อสินค้า"]), gift_product_style),
                str(int(row["จำนวน"])),
                "Free",
            ])
            
        gift_widths = [
            usable_width * 0.07,
            usable_width * 0.12,
            usable_width * 0.53,
            usable_width * 0.08,
            usable_width * 0.20,
        ]

        gift_table = Table(gift_data, colWidths=gift_widths)
        gift_table.setStyle(TableStyle([
            ("GRID",       (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgreen),

            ("FONTNAME",   (0, 0), (-1, -1), "THSarabunNew"),
            ("FONTSIZE",   (0, 0), (-1, -1), 14),

            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),

            ("ALIGN",      (0, 0), (-1, 0), "CENTER"),

            ("ALIGN",      (0, 1), (0, -1), "CENTER"),
            ("ALIGN",      (1, 1), (1, -1), "CENTER"),
            ("ALIGN",      (2, 1), (2, -1), "LEFT"),
            ("ALIGN",      (3, 1), (3, -1), "CENTER"),
            ("ALIGN",      (4, 1), (4, -1), "CENTER"),
            
            ("TOPPADDING",    (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ]))

        content.append(gift_table)

    content.append(Spacer(1, 20))
    content.append(Paragraph(
        "ทดลองทำเพื่อให้สะดวกต่อการทำงาน และ เพื่อใช้งานส่วนตัวเท่านั้น<br/>อิwอิ",
        right_style,
    ))

    doc.build(content)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


# ─────────────────────────────────────────────
# CUSTOMER INFO
# ─────────────────────────────────────────────

st.subheader("👤 ข้อมูลผู้สั่งซื้อ")

c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
with c1:
    member_id = st.text_input("รหัสสมาชิก", placeholder="เช่น 1234567")
with c2:
    customer_name = st.text_input("ชื่อผู้สั่งซื้อ", placeholder="ชื่อ-นามสกุล")
with c3:
    Tai_name = st.text_input("ၸိုဝ်ႈၵူၼ်းသင်ႇသိုဝ်ႉ", placeholder="ภาษาไทใหญ่")
with c4:
    order_date = st.date_input("วันที่สั่งซื้อ", value=date.today(), format="DD/MM/YYYY")

st.divider()

# ─────────────────────────────────────────────
# TITLE
# ─────────────────────────────────────────────

st.markdown("""
<div class="header-card">
    <h1>📦 ระบบสร้างใบสั่งซื้อสินค้า Giffarine โดย พพ&AI เพื่อนรัก </h1>
    <p>Order Management System</p>
</div>
""", unsafe_allow_html=True)
st.divider()

# ─────────────────────────────────────────────
# ADD PRODUCT  (Regular orders)
# ─────────────────────────────────────────────

st.subheader("➕ เพิ่มสินค้า")

tab_code, tab_search = st.tabs(["🔢 ค้นหาด้วยรหัสสินค้า", "🔍 ค้นหาด้วยชื่อสินค้า"])

with tab_code:
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        product_code = st.text_input("รหัสสินค้า", placeholder="เช่น 16965", key="input_code")
    with c2:
        qty_code = st.number_input("จำนวน", min_value=1, value=1, key="qty_code")
    with c3:
        st.write(""); st.write("")
        if st.button("เพิ่มสินค้า", use_container_width=True, key="btn_code"):
            found = products[products["product_code"] == product_code.strip()]
            if found.empty:
                st.error(f"❌ ไม่พบรหัสสินค้า **{product_code}**")
            else:
                add_item(found.iloc[0], qty_code, is_gift=False)
                st.rerun()

with tab_search:
    search_term = st.text_input("ชื่อสินค้า", placeholder="แต่ชื่อต้องตรงเป้ะนะ ไม่ขึ้นให้หรอก ไม่ทำ วะฮ่า", key="search_name")
    if search_term:
        results = products[products["product_name"].str.contains(search_term, case=False, na=False)]
        if results.empty:
            st.warning("ไม่พบสินค้าที่ตรงกัน")
        else:
            st.caption(f"พบ {len(results):,} รายการ (แสดง 10 อันดับแรก)")
            for _, row in results.head(10).iterrows():
                ca, cb, cc = st.columns([4, 2, 1])
                with ca:
                    st.write(f"**{row['product_name']}** — รหัส `{row['product_code']}`")
                with cb:
                    st.write(f"ราคาสมาชิก ฿{row['member_price_thb']:,.0f}")
                with cc:
                    if st.button("เพิ่ม", key=f"srch_{row['product_code']}"):
                        add_item(row, 1, is_gift=False)
                        st.rerun()

st.divider()

# ─────────────────────────────────────────────
# FREE GIFT SECTION
# ─────────────────────────────────────────────

st.subheader("🎁 เพิ่มของแถม (Free Gift)")

gift_tab_code, gift_tab_search = st.tabs(["🔢 ค้นหาด้วยรหัสสินค้า", "🔍 ค้นหาด้วยชื่อสินค้า"])

with gift_tab_code:
    g1, g2, g3 = st.columns([2, 1, 1])
    with g1:
        gift_code = st.text_input("รหัสสินค้า", placeholder="เช่น 16965", key="gift_input_code")
    with g2:
        gift_qty_code = st.number_input("จำนวน", min_value=1, value=1, key="gift_qty_code")
    with g3:
        st.write(""); st.write("")
        if st.button("เพิ่มของแถม", use_container_width=True, key="gift_btn_code"):
            found = products[products["product_code"] == gift_code.strip()]
            if found.empty:
                st.error(f"❌ ไม่พบรหัสสินค้า **{gift_code}**")
            else:
                add_item(found.iloc[0], gift_qty_code, is_gift=True)
                st.rerun()

with gift_tab_search:
    gift_search_term = st.text_input("ชื่อสินค้า", placeholder="ค้นหาสินค้าที่ต้องการเป็นของแถม", key="gift_search_name")
    if gift_search_term:
        gift_results = products[products["product_name"].str.contains(gift_search_term, case=False, na=False)]
        if gift_results.empty:
            st.warning("ไม่พบสินค้าที่ตรงกัน")
        else:
            st.caption(f"พบ {len(gift_results):,} รายการ (แสดง 10 อันดับแรก)")
            for _, row in gift_results.head(10).iterrows():
                ca, cb, cc = st.columns([4, 2, 1])
                with ca:
                    st.write(f"**{row['product_name']}** — รหัส `{row['product_code']}`")
                with cb:
                    st.write(f"ราคาสมาชิก ฿{row['member_price_thb']:,.0f}")
                with cc:
                    if st.button("เพิ่มแถม", key=f"gift_srch_{row['product_code']}"):
                        add_item(row, 1, is_gift=True)
                        st.rerun()

st.divider()

# ─────────────────────────────────────────────
# ORDER TABLE
# ─────────────────────────────────────────────

st.subheader("🛒 รายการสั่งซื้อ")

if len(st.session_state.orders) == 0:
    st.warning("ยังไม่มีรายการสินค้า")

df = pd.DataFrame(st.session_state.orders)

if not df.empty:
    df.insert(0, "ลำดับ", range(1, len(df) + 1))
    df["ลบ"] = False

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ลำดับ":      st.column_config.NumberColumn(disabled=True, width="small"),
            "รหัสสินค้า": st.column_config.TextColumn(disabled=True, width="small"),
            "ชื่อสินค้า": st.column_config.TextColumn(disabled=True),
            # FIX 1: remove format string so numeric values display correctly left-aligned
            "ราคาเต็ม":   st.column_config.NumberColumn(disabled=True),
            "ราคาสมาชิก": st.column_config.NumberColumn(disabled=True),
            "จำนวน":      st.column_config.NumberColumn(min_value=1, step=1, width="small"),
            "ยอดรวม":     st.column_config.NumberColumn(disabled=True),
            "ลบ":         st.column_config.CheckboxColumn("🗑", width="small"),
        },
    )

    edited["ยอดรวม"] = edited["ราคาสมาชิก"] * edited["จำนวน"]
    clean = edited[edited["ลบ"] == False].drop(columns=["ลบ", "ลำดับ"])
    st.session_state.orders = clean.to_dict("records")
else:
    clean = df

col_del, col_clear, _ = st.columns([1, 1, 4])
with col_del:
    if st.button("🗑 ลบรายการที่เลือก", use_container_width=True):
        st.rerun()
with col_clear:
    if st.button("❌ ล้างทั้งหมด", use_container_width=True):
        st.session_state.orders = []
        st.rerun()

# ─────────────────────────────────────────────
# SUMMARY METRICS
# ─────────────────────────────────────────────

total_items = int(clean["จำนวน"].sum()) if not clean.empty else 0
total_thb   = float(clean["ยอดรวม"].sum()) if not clean.empty else 0.0

m1, m2, m3 = st.columns(3)
m1.metric("รายการสินค้า",  f"{len(clean)} รายการ")
m2.metric("จำนวนชิ้นรวม",  f"{total_items} ชิ้น")
m3.metric("ยอดรวมทั้งหมด", f"฿{total_thb:,.2f}")

st.divider()

# ─────────────────────────────────────────────
# FREE GIFT TABLE
# ─────────────────────────────────────────────

st.subheader("🎁 รายการของแถม")

gift_df = pd.DataFrame(st.session_state.gifts)

if gift_df.empty:
    st.info("ยังไม่มีรายการของแถม")
    clean_gifts = gift_df
else:
    gift_df.insert(0, "ลำดับ", range(1, len(gift_df) + 1))
    gift_df["ลบ"] = False

    edited_gifts = st.data_editor(
        gift_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ลำดับ":      st.column_config.NumberColumn(disabled=True, width="small"),
            "รหัสสินค้า": st.column_config.TextColumn(disabled=True, width="small"),
            "ชื่อสินค้า": st.column_config.TextColumn(disabled=True),
            "ราคาเต็ม":   st.column_config.NumberColumn(disabled=True),
            "ราคาสมาชิก": st.column_config.NumberColumn(disabled=True),
            "จำนวน":      st.column_config.NumberColumn(min_value=1, step=1, width="small"),
            "ยอดรวม":     st.column_config.NumberColumn(disabled=True),
            "ลบ":         st.column_config.CheckboxColumn("🗑", width="small"),
        },
    )

    clean_gifts = edited_gifts[edited_gifts["ลบ"] == False].drop(columns=["ลบ", "ลำดับ"])
    st.session_state.gifts = clean_gifts.to_dict("records")

gcol_del, gcol_clear, _ = st.columns([1, 1, 4])
with gcol_del:
    if st.button("🗑 ลบของแถมที่เลือก", use_container_width=True):
        st.rerun()
with gcol_clear:
    if st.button("❌ ล้างของแถมทั้งหมด", use_container_width=True):
        st.session_state.gifts = []
        st.rerun()

st.divider()

# ─────────────────────────────────────────────
# ORDER STATUS  (FIX 4)
# ─────────────────────────────────────────────

st.subheader("📋 สถานะการสั่งซื้อ")

status_options = ["ปกติ  ", "ปิดยอด"]
order_status = st.selectbox(
    "เลือกสถานะ",
    options=status_options,
    index=0,
    key="order_status",
)


st.divider()

# ─────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────

st.subheader("📤 ส่งออกเอกสาร")

col_xl, col_pdf = st.columns(2)

# ── Excel ──────────────────────────────────────
with col_xl:
    xl_buf = BytesIO()
    with pd.ExcelWriter(xl_buf, engine="xlsxwriter") as writer:
        info_df = pd.DataFrame([
            ["รหัสสมาชิก",    member_id],
            ["ชื่อผู้สั่งซื้อ", customer_name],
            ["ชื่อเล่น",       Tai_name],
            ["วันที่สั่งซื้อ",  order_date.strftime("%d/%m/%Y")],
            ["สถานะ",          order_status],
        ])
        info_df.to_excel(writer, sheet_name="Order", startrow=0, index=False, header=False)
        if not clean.empty:
            clean.to_excel(writer, sheet_name="Order", startrow=6, index=False)
            ws = writer.sheets["Order"]
            for i, col in enumerate(clean.columns):
                col_width = max(len(str(col)), clean[col].astype(str).str.len().max()) + 4
                ws.set_column(i, i, min(col_width, 45))
        if not clean_gifts.empty:
            start_row = 6 + len(clean) + 3
            pd.DataFrame([["ของแถม (Free Gift)"]]).to_excel(
                writer, sheet_name="Order", startrow=start_row, index=False, header=False
            )
            clean_gifts.to_excel(writer, sheet_name="Order", startrow=start_row + 1, index=False)

    st.download_button(
        "📥 Export Excel",
        data=xl_buf.getvalue(),
        file_name="order.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ── PDF ────────────────────────────────────────
with col_pdf:
    if clean.empty:
        st.button("📄 Export PDF", disabled=True, use_container_width=True,
                  help="กรุณาเพิ่มสินค้าก่อน Export PDF")
    else:
        if st.button("📄 สร้าง PDF", use_container_width=True):
            with st.spinner("กำลังสร้าง PDF..."):
                try:
                    gifts_for_pdf = pd.DataFrame(st.session_state.gifts) if st.session_state.gifts else pd.DataFrame()
                    pdf_bytes = build_pdf(
                        clean,
                        gifts_for_pdf,
                        member_id,
                        customer_name,
                        Tai_name,
                        order_date.strftime("%d/%m/%Y"),
                        order_status,
                    )
                    st.download_button(
                        "⬇️ ดาวน์โหลด PDF",
                        data=pdf_bytes,
                        file_name=f"order_{order_date.strftime('%d%m%Y')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"❌ สร้าง PDF ไม่สำเร็จ: {e}")
