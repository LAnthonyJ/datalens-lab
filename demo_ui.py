"""Gradio presentation for the offline DataLens assistant."""
import logging
import re
from pathlib import Path

import gradio as gr

SQL_PROMPT = "Write one SQLite SELECT statement to count every row in the table sales. Return only SQL."
MISSING_PROMPT = "Seven packages arrived damaged. What percentage of shipments arrived damaged?"
EMPTY_REPLY = "The model returned no readable answer. Use Retry to generate another response."
CSS = Path(__file__).with_name("demo.css")

HEADER = """
<header class="lab-header">
  <div class="lab-brand"><span class="lab-mark" aria-hidden="true"></span>
  <h1>DataLens Lab</h1></div>
  <div class="lab-model"><span>Qwen3.5-0.8B</span><span>Local inference</span></div>
</header>
"""
WELCOME = '<h2 class="lab-welcome">What would you like to analyze?</h2>'


def completed_reply(text):
    """Only classify empty fences once the stream has finished."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or all(re.fullmatch(r"`{3,}(?:[\w+-]+)?|</?code>", line, re.I) for line in lines):
        logging.warning("No readable model output: %r", text)
        return EMPTY_REPLY
    wrapper = re.fullmatch(r"\s*<code>\s*(`{3}[^\n]*\n.*?\n`{3})\s*</code>\s*", text, re.S | re.I)
    if wrapper:
        return wrapper.group(1)
    if re.fullmatch(r"\s*SELECT\b[^;]*;\s*", text, re.S | re.I):
        return f"```sql\n{text.strip()}\n```"
    return text


def build_ui(assistant):
    def chat(message, history):
        last = ""
        try:
            for last in assistant.generate(message, history):
                yield last
        except (ValueError, RuntimeError) as exc:
            raise gr.Error(str(exc)) from exc
        final = completed_reply(last)
        if final != last:
            yield final

    with gr.Blocks(title="DataLens Lab") as ui:
        gr.HTML(HEADER, container=False)
        with gr.Column(elem_id="lab-workspace"):
            gr.Markdown("## Analysis workspace", elem_id="lab-heading")
            gr.ChatInterface(
                chat,
                chatbot=gr.Chatbot(
                    elem_id="lab-chat", placeholder=WELCOME, show_label=False,
                    buttons=["copy"], layout="bubble", height="clamp(290px, 48dvh, 510px)",
                ),
                textbox=gr.Textbox(
                    elem_id="lab-input", placeholder="Ask a data question…",
                    show_label=False, container=False, submit_btn=True, stop_btn=True,
                ),
                examples=[SQL_PROMPT, MISSING_PROMPT],
                example_labels=["Write a SQL query", "Ask about missing data"],
                cache_examples=False, concurrency_limit=1, api_name="chat",
            )
    return ui


def appearance():
    return gr.themes.Base(
        primary_hue="blue", neutral_hue="slate",
        font=["Segoe UI", "Arial", "sans-serif"],
        font_mono=["Consolas", "monospace"],
    )
