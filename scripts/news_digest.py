#!/usr/bin/env python3
"""
Daily News Digest Bot
RSS fetch → Gemini 2.5 Flash (~10-min content per region) → HTML email via 163 SMTP
"""

import os
import re
import smtplib
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import feedparser
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash"
    f"?key={GEMINI_API_KEY}"
)
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.163.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER     = os.environ["SMTP_USER"]        # 163邮箱地址
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]    # 163邮箱授权码（非登录密码）
TO_EMAIL      = os.environ["TO_EMAIL"]
CST           = ZoneInfo("Asia/Shanghai")

# ── Regions & RSS ─────────────────────────────────────────────────────────────
REGIONS = [
    {
        "key": "china",
        "label": "🇨🇳 中国",
        "sources": [
            {"name": "新华网",       "url": "http://www.xinhuanet.com/politics/news_politics.xml"},
            {"name": "中国数字时代", "url": "https://chinadigitaltimes.net/chinese/feed/"},
        ],
        "prompt": (
            "你是一位专业的国际新闻播报员。今天是 {date}。\n"
            "以下是来自中国的今日热点新闻标题与摘要：\n\n{headlines}\n\n"
            "请用【简体中文】，从以上新闻中选取 3～5 条最重要的，逐条深度展开报道。\n"
            "每条结构：①【标题】 ②【背景介绍】 ③【详细报道】 ④【影响分析】 ⑤【各方观点】\n"
            "总内容须达到朗读约 10 分钟的篇幅（约 2200～2600 汉字）。\n"
            "输出纯 HTML（使用 <h3><p><ul><li>），禁止使用 markdown，不需要 <!DOCTYPE> 等外层标签。"
        ),
    },
    {
        "key": "taiwan",
        "label": "🇹🇼 台湾",
        "sources": [
            {"name": "自由时报", "url": "https://news.ltn.com.tw/rss/all.xml"},
        ],
        "prompt": (
            "你是一位专业的国际新闻播报员。今天是 {date}。\n"
            "以下是来自台湾的今日热点新闻标题与摘要：\n\n{headlines}\n\n"
            "请用【简体中文】，从以上新闻中选取 3～5 条最重要的，逐条深度展开报道。\n"
            "每条结构：①【标题】 ②【背景介绍】 ③【详细报道】 ④【政策与社会影响】 ⑤【各方观点】\n"
            "总内容须达到朗读约 10 分钟的篇幅（约 2200～2600 汉字）。\n"
            "输出纯 HTML（使用 <h3><p><ul><li>），禁止使用 markdown，不需要 <!DOCTYPE> 等外层标签。"
        ),
    },
    {
        "key": "japan",
        "label": "🇯🇵 日本",
        "sources": [
            {"name": "朝日新聞", "url": "https://www.asahi.com/rss/asahi/newsheadlines.rdf"},
        ],
        "prompt": (
            "あなたはプロのニュースキャスターです。今日は {date} です。\n"
            "以下は本日の日本のトップニュース見出しと概要です：\n\n{headlines}\n\n"
            "【日本語】で、上記から重要な 3〜5 件を選び、各記事を詳しく展開してください。\n"
            "各記事の構成：①【見出し】 ②【背景】 ③【詳細報道】 ④【影響分析】 ⑤【各方面の意見】\n"
            "重要：すべての漢字の直後に括弧でふりがなを付けること。例：政府（せいふ）、経済（けいざい）\n"
            "合計で約10分間の読み上げ量（約2200〜2600文字）にしてください。\n"
            "出力は純粋な HTML（<h3><p><ul><li>）のみ。markdown 不可、外側タグ不要。"
        ),
    },
    {
        "key": "us_uk",
        "label": "🇺🇸🇬🇧 US & UK",
        "sources": [
            {"name": "New York Times",  "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
            {"name": "Washington Post", "url": "https://feeds.washingtonpost.com/rss/world"},
            {"name": "BBC News",        "url": "http://feeds.bbci.co.uk/news/rss.xml"},
        ],
        "prompt": (
            "You are a professional international news presenter. Today is {date}.\n"
            "Below are today's top news headlines and summaries from the US and UK:\n\n{headlines}\n\n"
            "In [English], select 3–5 of the most important stories and expand each in depth.\n"
            "Structure per story: ①[Headline] ②[Background] ③[Detailed Report] ④[Impact Analysis] ⑤[Multiple Perspectives]\n"
            "Total content should be suitable for ~10 minutes of reading aloud (~1700–2000 words).\n"
            "Output pure HTML (<h3><p><ul><li> only). No markdown. No outer <!DOCTYPE> tags."
        ),
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "")


def fetch_headlines(sources: list[dict], max_per: int = 6) -> list[dict]:
    items = []
    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
            count = 0
            for entry in feed.entries:
                if count >= max_per:
                    break
                title   = strip_html(entry.get("title", "")).strip()
                summary = strip_html(
                    entry.get("summary", "") or entry.get("description", "")
                ).strip()[:600]
                if title:
                    items.append({"source": src["name"], "title": title, "summary": summary})
                    count += 1
            log.info(f"    ✓ {src['name']}: {count} items")
        except Exception as exc:
            log.warning(f"    ✗ {src['name']}: {exc}")
    return items


def call_gemini(prompt: str) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.75, "maxOutputTokens": 8192},
    }
    resp = requests.post(GEMINI_URL, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        log.error(f"Gemini unexpected response: {data}")
        raise RuntimeError("Gemini parse error") from exc


def generate_section(region: dict, date_str: str) -> str:
    headlines = fetch_headlines(region["sources"])
    if not headlines:
        return "<p><em>本日ニュースを取得できませんでした。</em></p>"
    hl_text = "\n".join(
        f"[{h['source']}] {h['title']}\n  概要: {h['summary']}" for h in headlines
    )
    prompt = region["prompt"].format(date=date_str, headlines=hl_text)
    log.info(f"  ⚡ Gemini generating {region['label']}...")
    return call_gemini(prompt)

# ── Email HTML ────────────────────────────────────────────────────────────────

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def build_html(sections: list[tuple], date_str: str) -> str:
    weekday = WEEKDAYS[datetime.now(CST).weekday()]
    toc = "".join(f"<li>{lbl}</li>" for lbl, _ in sections)
    body = "".join(
        f'<div class="section"><div class="sec-hd">{lbl}</div>'
        f'<div class="sec-bd">{content}</div></div>'
        for lbl, content in sections
    )
    return f"""<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日新闻精读 {date_str}</title>
<style>
body{{margin:0;padding:0;background:#eef1f7;font-family:'PingFang SC','Hiragino Sans','Microsoft YaHei',Arial,sans-serif;color:#1a1a2e;line-height:1.95}}
.wrap{{max-width:860px;margin:28px auto;background:#fff;border-radius:14px;box-shadow:0 6px 32px rgba(0,0,0,.10);overflow:hidden}}
.hero{{background:linear-gradient(120deg,#0d1b6e 0%,#1a3a8f 55%,#1565c0 100%);color:#fff;padding:36px 44px 28px}}
.hero h1{{margin:0 0 7px;font-size:27px;font-weight:800;letter-spacing:.5px}}
.hero p{{margin:0;font-size:14px;opacity:.83}}
.toc{{background:#e8edf8;padding:16px 44px;border-bottom:1px solid #c9d3ec}}
.toc b{{color:#1a3a8f;font-size:13px}}
.toc ul{{margin:6px 0 0;padding-left:20px}}
.toc li{{font-size:14px;color:#333;margin:3px 0}}
.section{{padding:36px 44px;border-bottom:1px solid #eef0f8}}
.section:last-child{{border:none}}
.sec-hd{{font-size:22px;font-weight:700;color:#0d1b6e;padding-bottom:13px;border-bottom:3px solid #1a3a8f;margin-bottom:22px}}
.sec-bd h3{{color:#1a3a8f;font-size:16.5px;margin:24px 0 9px;padding-left:12px;border-left:4px solid #5c8df6}}
.sec-bd p{{margin:8px 0 14px;font-size:15.5px}}
.sec-bd ul{{padding-left:22px}}
.sec-bd li{{margin:5px 0;font-size:15.5px}}
.foot{{background:#eef1f7;text-align:center;padding:18px;font-size:12px;color:#aaa}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <h1>📰 每日新闻精读</h1>
    <p>{date_str}（{weekday}）&nbsp;|&nbsp;北京时间 08:00 自动推送</p>
  </div>
  <div class="toc"><b>📋 今日版块</b><ul>{toc}</ul></div>
  {body}
  <div class="foot">Powered by Gemini 2.5 Flash · GitHub Actions · {date_str}</div>
</div>
</body>
</html>"""

# ── Send via 163 SMTP (SSL 465) ───────────────────────────────────────────────

def send_email(html: str, subject: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as srv:
        srv.login(SMTP_USER, SMTP_PASSWORD)
        srv.sendmail(SMTP_USER, [TO_EMAIL], msg.as_string())
    log.info(f"✉️  Sent → {TO_EMAIL}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    date_str = datetime.now(CST).strftime("%Y-%m-%d")
    log.info(f"=== Daily News Digest {date_str} ===")

    sections = []
    for region in REGIONS:
        log.info(f"\n▶ [{region['label']}]")
        content = generate_section(region, date_str)
        sections.append((region["label"], content))

    log.info("\n📧 Building & sending email...")
    html = build_html(sections, date_str)
    subject = f"📰 每日新闻精读 {date_str} | 中国·台湾·日本·US&UK"
    send_email(html, subject)
    log.info("=== ✅ Done ===")


if __name__ == "__main__":
    main()
