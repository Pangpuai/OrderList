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

# All paths resolved relative to this file — works regardless of cwd when streamlit is launched
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="สร้างใบสั่งซื้อ Giffarine โดย พพ&AIเพื่อนรัก",
    page_icon="📦",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 0.5rem 1rem; }
</style>
""", unsafe_allow_html=True)

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

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def add_item(item, qty: int):
    """Add a product to the cart, or increment quantity if already present."""
    code = str(item["product_code"])
    for order in st.session_state.orders:
        if order["รหัสสินค้า"] == code:
            order["จำนวน"] += qty
            order["ยอดรวม"] = order["ราคาสมาชิก"] * order["จำนวน"]
            st.toast(f"เพิ่มจำนวน {item['product_name']} แล้ว ✅")
            return
    st.session_state.orders.append({
        "รหัสสินค้า": code,
        "ชื่อสินค้า": item["product_name"],
        "ราคาเต็ม":   float(item["full_price_thb"]),
        "ราคาสมาชิก": float(item["member_price_thb"]),
        "จำนวน":      int(qty),
        "ยอดรวม":    float(item["member_price_thb"]) * int(qty),
    })
    st.toast(f"เพิ่ม {item['product_name']} แล้ว ✅")


def build_pdf(orders_df, member_id, customer_name, order_date_str):

    pdf_buffer = BytesIO()

    # ฟอนต์ไทย
    font_path = os.path.join(BASE_DIR, "font", "THSarabunNew.ttf")

    pdfmetrics.registerFont(
        TTFont("THSarabunNew.ttf", font_path)
    )

    doc = SimpleDocTemplate(pdf_buffer)

    styles = getSampleStyleSheet()
    styles["Title"].fontName = "THSarabunNew.ttf"
    styles["Normal"].fontName = "THSarabunNew.ttf"

    styles["Title"].fontSize = 18
    styles["Normal"].fontSize = 14
    styles["Normal"].leading = 22

    content = []

    title = Paragraph(
        "ใบสั่งซื้อสินค้า GIFFARINE )",
        styles["Title"]
    )

    content.append(title)
    content.append(Spacer(1, 12))

    content.append(
        Paragraph(
            f"รหัสสมาชิก : {member_id or '-'}",
            styles["Normal"]
        )
    )

    content.append(
        Paragraph(
            f"ชื่อผู้สั่งซื้อ : {customer_name or '-'}",
            styles["Normal"]
        )
    )

    content.append(
        Paragraph(
            f"วันที่สั่งซื้อ : {order_date_str}",
            styles["Normal"]
        )
    )

    content.append(Spacer(1, 12))

    table_data = [[
        "ลำดับ",
        "รหัสสินค้า",
        "ชื่อสินค้า",
        "ราคาเต็ม",
        "ราคาสมาชิก",
        "จำนวน",
        "รวม"
    ]]

    for i, (_, row) in enumerate(
        orders_df.iterrows(),
        start=1
    ):

        table_data.append([
            str(i),
            str(row["รหัสสินค้า"]),
            str(row["ชื่อสินค้า"]),
            f"{row['ราคาเต็ม']:,.2f}",
            f"{row['ราคาสมาชิก']:,.2f}",
            str(int(row["จำนวน"])),
            f"{row['ยอดรวม']:,.2f}",
        ])

    table = Table(table_data)

    table.setStyle(
        TableStyle([
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("FONTNAME", (0,0), (-1,-1), "THSarabunNew.ttf"),
        ])
    )

    content.append(table)

    content.append(Spacer(1, 15))

    total_qty = int(
        orders_df["จำนวน"].sum()
    )

    total_amount = float(
        orders_df["ยอดรวม"].sum()
    )

    content.append(
        Paragraph(
            f"จำนวนสินค้ารวม : {total_qty:,} ชิ้น",
            styles["Normal"]
        )
    )

    content.append(
        Paragraph(
            f"ยอดรวมทั้งหมด : {total_amount:,.2f} บาท",
            styles["Normal"]
        )
    )

    doc.build(content)

    pdf_buffer.seek(0)

    return pdf_buffer.getvalue()
# ─────────────────────────────────────────────
# CUSTOMER INFO
# ─────────────────────────────────────────────

st.subheader("👤 ข้อมูลผู้สั่งซื้อ")

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    member_id = st.text_input("รหัสสมาชิก", placeholder="เช่น 1234567")
with c2:
    customer_name = st.text_input("ชื่อผู้สั่งซื้อ", placeholder="ชื่อ-นามสกุล")
with c3:
    order_date = st.date_input("วันที่สั่งซื้อ", value=date.today(), format="DD/MM/YYYY")

st.divider()

# ─────────────────────────────────────────────
# TITLE
# ─────────────────────────────────────────────

st.title("📦 ระบบสร้างใบสั่งซื้อสินค้า Giffarine")
st.divider()

# ─────────────────────────────────────────────
# ADD PRODUCT
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
                add_item(found.iloc[0], qty_code)
                st.rerun()

with tab_search:
    search_term = st.text_input("ชื่อสินค้า", placeholder="เช่น ครีม, แชมพู, วิตามิน", key="search_name")
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
                        add_item(row, 1)
                        st.rerun()

st.divider()

# ─────────────────────────────────────────────
# ORDER TABLE
# ─────────────────────────────────────────────

if len(st.session_state.orders) == 0:
    st.warning("ยังไม่มีรายการสินค้า")

st.subheader("🛒 รายการสั่งซื้อ")

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
            "ราคาเต็ม":   st.column_config.NumberColumn(disabled=True, format="฿%.0f"),
            "ราคาสมาชิก": st.column_config.NumberColumn(disabled=True, format="฿%.0f"),
            "จำนวน":      st.column_config.NumberColumn(min_value=1, step=1, width="small"),
            "ยอดรวม":    st.column_config.NumberColumn(disabled=True, format="฿%.2f"),
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
            ["วันที่สั่งซื้อ",  order_date.strftime("%d/%m/%Y")],
        ])
        info_df.to_excel(writer, sheet_name="Order", startrow=0, index=False, header=False)
        if not clean.empty:
            clean.to_excel(writer, sheet_name="Order", startrow=4, index=False)
            ws = writer.sheets["Order"]
            for i, col in enumerate(clean.columns):
                col_width = max(len(str(col)), clean[col].astype(str).str.len().max()) + 4
                ws.set_column(i, i, min(col_width, 45))

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
                    pdf_bytes = build_pdf(
                        clean,
                        member_id,
                        customer_name,
                        order_date.strftime("%d/%m/%Y"),
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
