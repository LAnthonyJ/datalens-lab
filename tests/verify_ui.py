"""Check the public demo in Edge at desktop and phone widths."""
import argparse
from pathlib import Path
import sys

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_demo import SQL_PROMPT, count_rows


def check_width(page, width):
    assert page.evaluate("document.documentElement.scrollWidth") <= width


def text_contrast(locator, pseudo=None):
    # Composite translucent ancestor backgrounds in paint order.
    return locator.evaluate("""(node, pseudo) => {
        function rgba(value) { return value.match(/[\\d.]+/g).map(Number); }
        function blend(top, bottom) {
            const a = top[3] ?? 1;
            return bottom.map((c, i) => a * top[i] + (1 - a) * c);
        }
        function luminance(rgb) {
            const [r, g, b] = rgb.map(v => {
                const s = v / 255;
                return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
            });
            return .2126*r + .7152*g + .0722*b;
        }
        let bg = [255,255,255];
        const chain = [];
        for (let el=node; el; el=el.parentElement) chain.unshift(el);
        for (const el of chain) bg = blend(rgba(getComputedStyle(el).backgroundColor), bg);
        const fg = blend(rgba(getComputedStyle(node, pseudo).color), bg);
        const values = [luminance(fg), luminance(bg)].sort((a,b)=>b-a);
        return (values[0]+.05)/(values[1]+.05);
    }""", pseudo)


def check_contrast(page, items):
    for selector, pseudo in items:
        item = page.locator(selector).first
        expect(item).to_be_visible()
        ratio = text_contrast(item, pseudo)
        assert ratio >= 4.5, f"{selector} {pseudo or ''}: {ratio:.2f}:1"


def check_chat(browser, url, width, height, theme, capture):
    context = browser.new_context(
        viewport={"width": width, "height": height}, locale="en-US", color_scheme=theme,
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
        assert page.locator("body").evaluate("e => e.classList.contains('dark')") == (theme == "dark")
        check_contrast(page, [("#lab-heading h2", None), (".lab-brand h1", None),
                              (".lab-model span", None), ("#lab-input textarea", "::placeholder")])
        starter.click()
        code = page.locator("#lab-chat code.language-sql")
        expect(code).to_contain_text("FROM sales", timeout=120000)
        retry = page.get_by_role("button", name="Retry", exact=True).last
        retry.wait_for()
        expect(page.get_by_test_id("stop-button")).to_be_hidden(timeout=120000)
        expect(page.get_by_text(SQL_PROMPT, exact=True)).to_have_count(1)
        expect(starter).to_be_hidden()
        check_width(page, width)
        check_contrast(page, [("#lab-chat .message.user p", None), ("pre:has(code.language-sql)", "::before"),
                              ("code.language-sql", None), ("code .keyword", None), ("code .function", None)])
        copy = page.locator('#lab-chat button[title="copy"]')
        copy.click()
        copied = page.evaluate("navigator.clipboard.readText()")
        assert copied.strip() == code.inner_text().strip()
        count_rows(copied)
        if capture and width == 1280 and theme == "light":
            page.mouse.move(0, 0)
            page.locator(".gradio-container").first.screenshot(path=capture)
        retry.click()
        page.get_by_test_id("stop-button").wait_for()
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
        print(f"PASS {width}x{height} {theme}, copied SQL returned 3. Conversation:", page.locator("#lab-chat").inner_text(), flush=True)
    finally:
        context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge")
        for theme in ("dark", "light"):
            for width, height in ((680, 548), (390, 800), (1280, 800)):
                check_chat(browser, args.url, width, height, theme, args.capture)
        browser.close()
