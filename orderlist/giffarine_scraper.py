"""
Giffarine Product Scraper (Playwright edition)
===============================================
Uses a real browser so the JavaScript login form works correctly.
Logs in, then scrapes every product page for name, code, full price,
and member price. Saves results to giffarine_products.csv.

Requirements:
    pip install playwright beautifulsoup4
    playwright install chromium

Usage:
    python giffarine_scraper.py
"""

import csv, re, time, sys
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Configuration ─────────────────────────────────────────────────────────────

LOGIN_URL    = "https://www.giffarine.com/login"
PRODUCTS_URL = "https://www.giffarine.com/products"
OUTPUT_FILE  = "giffarine_products.csv"
TOTAL_PAGES  = 117
DELAY        = 0.8   # seconds between requests

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_listing(page_content: str):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_content, "html.parser")
    products = []
    for a in soup.find_all("a", href=re.compile(r"/product/")):
        text = a.get_text(" ", strip=True)
        code_m  = re.search(r"รหัส\s*(\d+)", text)
        price_m = re.search(r"ราคาเต็ม\s*([\d,]+\.?\d*)", text)
        if not code_m or not price_m:
            continue
        code  = code_m.group(1)
        price = price_m.group(1).replace(",", "")
        raw   = text.split("รหัส")[0]
        raw   = re.sub(r"^Giffarine\s+badge\s*", "", raw)
        raw   = re.sub(r"^New\s+", "", raw, flags=re.IGNORECASE).strip()
        parts = raw.split()
        half  = len(parts) // 2
        if half > 0 and parts[:half] == parts[half:half+half]:
            raw = " ".join(parts[half:])
        href = a["href"]
        url  = ("https://www.giffarine.com" + href
                if href.startswith("/") else href)
        products.append({"name": raw, "code": code,
                         "full_price": price, "url": url})
    return products


def get_member_price(page_content: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_content, "html.parser")
    text = soup.get_text(" ")
    m = re.search(r"ราคาสมาชิก\s*([\d,]+\.?\d*)", text)
    if m:
        return m.group(1).replace(",", "")
    m = re.search(r"สมาชิก\s*[:：]?\s*([\d,]+\.?\d*)", text)
    if m:
        return m.group(1).replace(",", "")
    return ""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Giffarine Product Scraper  (Playwright)")
    print("=" * 55)

    member_id = input("\nEnter your member ID: ").strip()
    password  = input("Enter your password:  ").strip()

    with sync_playwright() as pw:
        # Run with headless=False so the real browser window opens.
        # This ensures JavaScript (uuid, browser fields) runs fully,
        # exactly like a normal human login.
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="th-TH",
        )
        page = context.new_page()

        # ── Open login page ────────────────────────────────────────────────
        print("\nOpening login page…", end=" ", flush=True)
        page.goto(LOGIN_URL, wait_until="networkidle", timeout=30_000)
        print("loaded")

        # Let JS fully initialise (fills uuid/browser hidden fields)
        page.wait_for_timeout(2000)

        # ── Fill credentials ───────────────────────────────────────────────
        page.locator('input[name="username"]').fill(member_id)
        page.locator('input[name="password"]').fill(password)

        # Click the correct submit button — the one with text "เข้าสู่ระบบ"
        # (not the empty first submit button which belongs to the search bar)
        page.locator('button[type="submit"]:has-text("เข้าสู่ระบบ")').click()

        print("  Submitted login form, waiting for redirect…")

        # Wait for navigation away from /login
        try:
            page.wait_for_url(
                re.compile(r"giffarine\.com(?!/login)"),
                timeout=20_000
            )
        except PWTimeout:
            pass

        page.wait_for_load_state("networkidle", timeout=15_000)

        print(f"  URL after login: {page.url}")

        # Check success: redirected away OR logout link present
        page_text = page.inner_text("body")
        login_success = (
            "/login" not in page.url
            or "ออกจากระบบ" in page_text
            or "ล็อกเอาท์" in page_text
            or "dashboard" in page.url
        )

        if not login_success:
            page.screenshot(path="after_login.png", full_page=True)
            print("\n⚠  Login still failed. Screenshot saved → after_login.png")
            print("   The browser window is still open — check it for error messages.")
            input("   Press Enter to quit…")
            browser.close()
            sys.exit(1)

        print("Login OK ✓")

        # ── Scrape listing pages ───────────────────────────────────────────
        all_products = []
        print(f"\nScraping {TOTAL_PAGES} listing pages…\n")

        for pg_num in range(1, TOTAL_PAGES + 1):
            url = f"{PRODUCTS_URL}?sortby=new&page={pg_num}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            except PWTimeout:
                print(f"  Page {pg_num}: timeout, skipping")
                continue

            products = parse_listing(page.content())

            for prod in products:
                try:
                    page.goto(prod["url"], wait_until="domcontentloaded",
                              timeout=20_000)
                    member_price = get_member_price(page.content())
                    page.go_back(wait_until="domcontentloaded", timeout=10_000)
                except PWTimeout:
                    member_price = ""

                prod["member_price"] = member_price
                all_products.append(prod)

                label = f"฿{member_price}" if member_price else "—"
                print(
                    f"  [{pg_num:>3}/{TOTAL_PAGES}] "
                    f"{prod['code']}  {prod['name'][:38]:<38}  "
                    f"full: ฿{prod['full_price']:>8}  member: {label}"
                )
                time.sleep(DELAY)

            time.sleep(DELAY)

        browser.close()

    # ── Write CSV ─────────────────────────────────────────────────────────────
    fieldnames = ["product_name", "product_code", "full_price_thb",
                  "member_price_thb", "product_url"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in all_products:
            writer.writerow({
                "product_name":     p["name"],
                "product_code":     p["code"],
                "full_price_thb":   p["full_price"],
                "member_price_thb": p["member_price"],
                "product_url":      p["url"],
            })

    print(f"\n✓ Done! {len(all_products)} products saved to '{OUTPUT_FILE}'")
    print(f"  Finished at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()