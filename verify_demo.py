"""Exercise a running local demo. Run with the QA environment."""
import argparse
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import re
import sqlite3
from time import monotonic

from gradio_client import Client

SQL_PROMPT = "Write one SQLite SELECT statement to count every row in the table sales. Return only SQL."


def count_rows(response):
    match = re.search(r"\bselect\b[^;`]*?(?:;|(?=\s*```)|$)", response, re.I | re.S)
    if not match:
        raise AssertionError(f"No SELECT statement in {response!r}")
    with sqlite3.connect(":memory:") as conn:
        conn.executescript("CREATE TABLE sales(id INTEGER); INSERT INTO sales VALUES (3),(4),(5); PRAGMA query_only=ON;")
        result = conn.execute(match.group()).fetchall()
        assert result == [(3,)], (response, result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    def ask(client, prompt):
        started = monotonic()
        value = client.predict(prompt, api_name="/chat")
        if isinstance(value, dict):
            value = value["content"]
        if isinstance(value, list):
            value = "".join(x["text"] for x in value if x.get("type") == "text")
        assert isinstance(value, str) and value.strip(), repr(value)
        print(f"{monotonic()-started:.2f}s {value[:160]}", flush=True)
        return value
    for i in range(5):
        with closing(Client(args.url, verbose=False)) as first, closing(Client(args.url, verbose=False)) as second:
            with ThreadPoolExecutor(2) as pool:
                left = pool.submit(ask, first, SQL_PROMPT)
                right = pool.submit(ask, second, "用一句话说明如何处理缺失值。")
                count_rows(left.result())
                assert re.search(r"[\u3400-\u9fff]", right.result())
            assert "sales" in ask(first, "Using the same table as in your previous SQL statement, show its first two rows. Return only SQL.").lower()
            example = ask(second, "请举一个例子。")
            assert example.count(chr(96) * 3 + "python") < 4, "Repeated empty code fences"
    if args.browser:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            page.goto(args.url)
            box = page.get_by_role("textbox").last
            box.fill(SQL_PROMPT)
            box.press("Enter")
            page.wait_for_function("() => /select\\s+count\\s*\\(/i.test(document.body.innerText)", timeout=120000)
            retry = page.get_by_role("button", name=re.compile("Retry|重试", re.I))
            retry.wait_for(timeout=120000)
            retry.click()
            page.wait_for_function("() => /select\\s+count\\s*\\(/i.test(document.body.innerText)", timeout=120000)
            retry.wait_for(timeout=120000)
            page.get_by_role("button", name=re.compile("^Clear$|Clear conversation|Clear chat|清空对话|^清除$", re.I)).click()
            retry.wait_for(state="hidden")
            browser.close()


if __name__ == "__main__":
    main()
