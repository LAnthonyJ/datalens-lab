"""Check the public demo in Edge at desktop and phone widths."""
import argparse
from pathlib import Path
import sys

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_demo import SQL_PROMPT, count_rows


def check_width(page, width):
    assert page.evaluate("document.documentElement.scrollWidth") <= width


def check_chat(browser, url, width, capture):
    context = browser.new_context(
        viewport={"width": width, "height": 800}, locale="en-US", color_scheme="light",
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = context.new_page()
    page.set_default_timeout(120000)
    try:
        page.goto(url)
        starter = page.get_by_text("Write a SQL query", exact=True)
        box = page.get_by_role("textbox").last
        expect(starter).to_be_in_viewport()
        expect(box).to_be_in_viewport()
        starter.click()
        code = page.locator("#lab-chat code.language-sql")
        expect(code).to_contain_text("FROM sales", timeout=120000)
        retry = page.get_by_role("button", name="Retry", exact=True).last
        retry.wait_for()
        expect(page.get_by_test_id("stop-button")).to_be_hidden(timeout=120000)
        expect(page.get_by_text(SQL_PROMPT, exact=True)).to_have_count(1)
        expect(starter).to_be_hidden()
        check_width(page, width)
        copy = page.locator('#lab-chat button[title="copy"]')
        copy.click()
        copied = page.evaluate("navigator.clipboard.readText()")
        assert copied.strip() == code.inner_text().strip()
        count_rows(copied)
        if capture and width == 1280:
            page.mouse.move(0, 0)
            page.locator(".gradio-container").first.screenshot(path=capture)
        retry.click()
        expect(code).to_contain_text("FROM sales", timeout=120000)
        retry.wait_for()
        expect(page.get_by_test_id("stop-button")).to_be_hidden(timeout=120000)
        expect(page.get_by_text(SQL_PROMPT, exact=True)).to_have_count(1)
        page.get_by_role("button", name="Clear", exact=True).click()
        expect(starter).to_be_visible()
        box.fill("Teach me about the p-value.")
        box.press("Enter")
        page.get_by_test_id("stop-button").click()
        expect(page.get_by_test_id("stop-button")).to_be_hidden(timeout=120000)
        expect(box).to_be_editable()
        if not starter.is_visible():
            page.get_by_role("button", name="Clear", exact=True).click()
        expect(starter).to_be_visible()
        page.get_by_text("Ask about missing data", exact=True).click()
        retry.wait_for()
        expect(page.get_by_test_id("stop-button")).to_be_hidden(timeout=120000)
        followup = "There were 100 shipments in total."
        box.fill(followup)
        box.press("Enter")
        expect(page.get_by_text(followup, exact=True)).to_be_visible()
        page.get_by_test_id("stop-button").wait_for()
        expect(page.get_by_test_id("stop-button")).to_be_hidden(timeout=120000)
        expect(page.get_by_text("Seven packages arrived damaged.", exact=False)).to_be_visible()
        retry.wait_for()
        expect(page.get_by_test_id("stop-button")).to_be_hidden(timeout=120000)
        expect(page.get_by_text(followup, exact=True)).to_have_count(1)
        check_width(page, width)
        print(f"PASS {width}px, copied SQL returned 3. Conversation:", page.locator("#lab-chat").inner_text(), flush=True)
    finally:
        context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        for width in (1280, 390):
            check_chat(browser, args.url, width, args.capture)
        browser.close()
