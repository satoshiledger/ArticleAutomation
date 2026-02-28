"""
PuertoRicoLLC.com — Blog Engine (All-in-One)
=============================================
Single Railway service that runs everything:
  1. Review dashboard (Flask web app)
  2. Blog generation on schedule (Mon/Wed/Fri 8AM EST)
  3. News monitor on schedule (Daily 6AM EST)
  4. Manual trigger endpoints

One service = one volume = no file sharing issues.
"""

import os
import json
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

from blog_engine import (
    run_scheduled_pipeline,
    run_news_monitor_pipeline,
    DRAFTS_DIR,
    APPROVED_DIR,
)

app = Flask(__name__)

DRAFTS_DIR.mkdir(exist_ok=True)
APPROVED_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# BACKGROUND SCHEDULER
# ---------------------------------------------------------------------------

def start_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler(daemon=True)

        # Blog generation: Mon/Wed/Fri at 12:00 UTC (8:00 AM EST)
        scheduler.add_job(
            run_scheduled_pipeline,
            CronTrigger(day_of_week="mon,wed,fri", hour=12, minute=0),
            id="blog_generation",
            name="Blog Generation",
            misfire_grace_time=3600,
        )

        # News monitor: Daily at 10:00 UTC (6:00 AM EST)
        scheduler.add_job(
            run_news_monitor_pipeline,
            CronTrigger(hour=10, minute=0),
            id="news_monitor",
            name="News Monitor",
            misfire_grace_time=3600,
        )

        scheduler.start()
        print("Scheduler started: Blog (Mon/Wed/Fri 12:00 UTC) + News (Daily 10:00 UTC)")

    except ImportError:
        print("APScheduler not installed. Cron jobs disabled. Use /trigger/blog and /trigger/news instead.")


# ---------------------------------------------------------------------------
# HTML TEMPLATES
# ---------------------------------------------------------------------------

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog Engine Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
</head>
<body class="bg-slate-950 text-white min-h-screen">
    <nav class="bg-slate-900 border-b border-slate-800 px-6 py-4">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <div class="flex items-center gap-3">
                <span class="text-2xl font-black" style="color:#CC0000">PuertoRico<span style="color:#3A99D8">LLC</span></span>
                <span class="text-slate-500 text-sm">Blog Engine</span>
            </div>
            <div class="flex items-center gap-4">
                <a href="/alerts" class="text-slate-400 hover:text-white text-sm transition">📡 Alerts</a>
                <span class="text-sm text-slate-400">{{ drafts|length }} drafts pending</span>
                <a href="/trigger/blog" class="bg-blue-600 text-white px-3 py-1 rounded-lg text-sm font-bold hover:bg-blue-700 transition"
                   onclick="this.textContent='Generating...'; this.style.opacity='0.5';">
                    ⚡ Generate Now
                </a>
            </div>
        </div>
    </nav>
    <main class="max-w-7xl mx-auto px-6 py-8">
        <h1 class="text-3xl font-black mb-8">📝 Pending Drafts</h1>
        {% if not drafts %}
        <div class="bg-slate-900 rounded-2xl p-12 text-center border border-slate-800">
            <i class="fas fa-check-circle text-green-500 text-5xl mb-4"></i>
            <p class="text-xl text-slate-400">All caught up! No pending drafts.</p>
            <p class="text-sm text-slate-600 mt-2">Next scheduled run: Mon/Wed/Fri at 8:00 AM EST</p>
            <a href="/trigger/blog" class="inline-block mt-4 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-blue-700 transition">⚡ Generate a Post Now</a>
        </div>
        {% endif %}
        <div class="grid gap-6">
        {% for draft in drafts %}
            <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800 hover:border-slate-600 transition">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center gap-3 mb-2">
                            {% if draft.audit.get('publish_ready') %}
                                <span class="bg-green-600 text-white text-xs font-bold px-3 py-1 rounded-full">READY</span>
                            {% else %}
                                <span class="bg-yellow-600 text-white text-xs font-bold px-3 py-1 rounded-full">REVIEW</span>
                            {% endif %}
                            <span class="text-slate-600 text-sm">Grade: {{ draft.audit.get('overall_grade', '?') }}</span>
                        </div>
                        <h2 class="text-xl font-bold mb-2">{{ draft.title }}</h2>
                        <div class="flex gap-4 text-sm text-slate-400">
                            <span>🔴 {{ draft.audit.get('critical_issues', [])|length }} critical</span>
                            <span>🟡 {{ draft.audit.get('warnings', [])|length }} warnings</span>
                            <span>🟢 {{ draft.audit.get('suggestions', [])|length }} suggestions</span>
                        </div>
                    </div>
                    <div class="flex gap-3">
                        <a href="/review/{{ draft.slug }}" class="bg-blue-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-blue-700 transition text-sm">Review & Edit</a>
                        <a href="/social/{{ draft.slug }}" class="bg-slate-700 text-white px-4 py-2 rounded-lg font-bold hover:bg-slate-600 transition text-sm">Social</a>
                    </div>
                </div>
                {% if draft.audit.get('warnings') %}
                <div class="mt-4 pt-4 border-t border-slate-800">
                    <p class="text-sm text-yellow-500 font-bold mb-2">Warnings:</p>
                    {% for w in draft.audit.get('warnings', [])[:3] %}
                    <p class="text-sm text-slate-400 ml-4">⚠️ {{ w.get('issue', '') or w.get('recommendation', '') }}</p>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
        {% endfor %}
        </div>
        {% if approved %}
        <h2 class="text-2xl font-black mt-12 mb-6">✅ Published</h2>
        <div class="grid gap-4">
        {% for post in approved %}
            <div class="bg-slate-900/50 rounded-xl p-4 border border-slate-800 flex justify-between items-center">
                <span class="text-slate-300">{{ post }}</span>
                <a href="https://puertoricollc.com/{{ post }}" target="_blank" class="text-blue-400 text-sm hover:underline">View live</a>
            </div>
        {% endfor %}
        </div>
        {% endif %}

        <!-- Custom Article Generator -->
        <h2 class="text-2xl font-black mt-12 mb-6">🚀 Generate Custom Article</h2>
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <p class="text-slate-400 text-sm mb-4">Generate an article on any topic — from news alerts, client questions, or trending topics. Runs independently from the content calendar.</p>
            <form action="/trigger/custom" method="POST" onsubmit="this.querySelector('button[type=submit]').textContent='⏳ Generating...'; this.querySelector('button[type=submit]').style.opacity='0.5';">
                <div class="grid md:grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="text-sm font-bold text-slate-300 block mb-1">Article Title *</label>
                        <input type="text" name="title" required placeholder="e.g. IRS Form 1099-DA: New Bitcoin Reporting Requirements for 2026"
                               class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none">
                    </div>
                    <div>
                        <label class="text-sm font-bold text-slate-300 block mb-1">Target Keywords</label>
                        <input type="text" name="keywords" placeholder="e.g. IRS 1099-DA, bitcoin reporting 2026, bitcoin cost basis"
                               class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none">
                    </div>
                </div>
                <div class="grid md:grid-cols-3 gap-4 mb-4">
                    <div>
                        <label class="text-sm font-bold text-slate-300 block mb-1">Category</label>
                        <select name="cluster" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none">
                            <option value="1_act60_compliance">Act 60 Compliance</option>
                            <option value="2_business_structure">Business Structure</option>
                            <option value="3_bitcoin">Bitcoin & Tax</option>
                            <option value="4_tax_strategy" selected>Tax Strategy</option>
                            <option value="5_operations">Bookkeeping & Operations</option>
                        </select>
                    </div>
                    <div>
                        <label class="text-sm font-bold text-slate-300 block mb-1">CTA Service</label>
                        <select name="cta" class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-white focus:border-blue-500 focus:outline-none">
                            <option value="consultation" selected>Consultation</option>
                            <option value="llc-formation">LLC Formation</option>
                            <option value="forensic-audit">Forensic Audit</option>
                            <option value="bookkeeping">Bookkeeping</option>
                            <option value="bitcoin-accounting">Bitcoin Accounting</option>
                        </select>
                    </div>
                    <div class="flex items-end">
                        <button type="submit" class="w-full bg-green-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-green-700 transition">
                            🚀 Generate Article
                        </button>
                    </div>
                </div>
            </form>
        </div>
    </main>
</body>
</html>
"""

REVIEW_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Review: {{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .editor-pane { font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; }
        .split-view { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; height: calc(100vh - 200px); }
    </style>
</head>
<body class="bg-slate-950 text-white">
    <nav class="bg-slate-900 border-b border-slate-800 px-6 py-3">
        <div class="max-w-full mx-auto flex justify-between items-center">
            <div class="flex items-center gap-4">
                <a href="/" class="text-slate-400 hover:text-white transition">← Dashboard</a>
                <span class="text-lg font-bold">{{ title }}</span>
                {% if audit.get('publish_ready') %}
                    <span class="bg-green-600 text-xs font-bold px-3 py-1 rounded-full">PASSED</span>
                {% else %}
                    <span class="bg-yellow-600 text-xs font-bold px-3 py-1 rounded-full">NEEDS REVIEW</span>
                {% endif %}
            </div>
            <div class="flex gap-3">
                <form action="/save/{{ slug }}" method="POST" style="display:inline">
                    <input type="hidden" name="html" id="save-html">
                    <button type="submit" onclick="document.getElementById('save-html').value=document.getElementById('editor').value"
                            class="bg-slate-700 text-white px-4 py-2 rounded-lg font-bold hover:bg-slate-600 transition text-sm">
                        💾 Save Draft
                    </button>
                </form>
                <form action="/approve/{{ slug }}" method="POST" style="display:inline">
                    <input type="hidden" name="html" id="approve-html">
                    <button type="submit" onclick="document.getElementById('approve-html').value=document.getElementById('editor').value"
                            class="bg-green-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-green-700 transition text-sm">
                        ✅ Approve & Publish
                    </button>
                </form>
                <form action="/reject/{{ slug }}" method="POST" style="display:inline">
                    <button type="submit" class="bg-red-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-red-700 transition text-sm">
                        ✗ Reject
                    </button>
                </form>
            </div>
        </div>
    </nav>
    <div class="bg-slate-900 px-6 py-3 border-b border-slate-800 flex gap-6 text-sm overflow-x-auto">
        <span class="text-slate-400">Grade: <strong class="text-white">{{ audit.get('overall_grade', '?') }}</strong></span>
        <span class="text-red-400">🔴 {{ audit.get('critical_issues', [])|length }} critical</span>
        <span class="text-yellow-400">🟡 {{ audit.get('warnings', [])|length }} warnings</span>
        <span class="text-green-400">🟢 {{ audit.get('suggestions', [])|length }} suggestions</span>
        {% for w in audit.get('warnings', [])[:3] %}
            <span class="text-yellow-500 border-l border-slate-700 pl-4">{{ w.get('issue', '') or w.get('recommendation', '') }}</span>
        {% endfor %}
    </div>
    <div class="px-4 py-4 split-view">
        <div class="flex flex-col">
            <p class="text-sm text-slate-500 mb-2 font-bold">HTML EDITOR</p>
            <textarea id="editor" class="editor-pane flex-1 bg-slate-900 text-green-300 p-4 rounded-xl border border-slate-700 resize-none outline-none focus:border-blue-500"
                      oninput="updatePreview()">{{ html_content }}</textarea>
        </div>
        <div class="flex flex-col">
            <p class="text-sm text-slate-500 mb-2 font-bold">LIVE PREVIEW</p>
            <iframe id="preview" class="flex-1 bg-white rounded-xl" style="border:none;"></iframe>
        </div>
    </div>
    <script>
        function updatePreview() {
            var html = document.getElementById('editor').value;
            var iframe = document.getElementById('preview');
            iframe.srcdoc = html;
        }
        window.addEventListener('load', updatePreview);
    </script>
</body>
</html>
"""

SOCIAL_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Social Content: {{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-white min-h-screen">
    <nav class="bg-slate-900 border-b border-slate-800 px-6 py-3">
        <div class="flex items-center gap-4">
            <a href="/" class="text-slate-400 hover:text-white transition">← Dashboard</a>
            <span class="text-lg font-bold">Social Content: {{ title }}</span>
        </div>
    </nav>
    <main class="max-w-4xl mx-auto px-6 py-8 space-y-8">
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold">LinkedIn Post</h2>
                <button onclick="copyText('linkedin')" class="bg-slate-700 px-3 py-1 rounded text-sm hover:bg-slate-600">📋 Copy</button>
            </div>
            <pre id="linkedin" class="text-slate-300 whitespace-pre-wrap text-sm leading-relaxed">{{ social.get('linkedin', 'Not generated') }}</pre>
        </div>
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold">Twitter/X Thread</h2>
                <button onclick="copyText('twitter')" class="bg-slate-700 px-3 py-1 rounded text-sm hover:bg-slate-600">📋 Copy All</button>
            </div>
            <div id="twitter" class="space-y-3">
            {% for tweet in social.get('twitter_thread', []) %}
                <div class="bg-slate-800 p-3 rounded-lg text-sm text-slate-300">{{ tweet }}</div>
            {% endfor %}
            {% if not social.get('twitter_thread') %}
                <p class="text-slate-500">Not generated</p>
            {% endif %}
            </div>
        </div>
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold">Email Newsletter</h2>
                <button onclick="copyText('email')" class="bg-slate-700 px-3 py-1 rounded text-sm hover:bg-slate-600">📋 Copy</button>
            </div>
            {% if social.get('email') %}
            <p class="text-yellow-400 text-sm mb-1">Subject: {{ social.email.get('subject', '') }}</p>
            <p class="text-slate-500 text-sm mb-3">Preview: {{ social.email.get('preview', '') }}</p>
            <pre id="email" class="text-slate-300 whitespace-pre-wrap text-sm">{{ social.email.get('body', '') }}</pre>
            {% else %}
            <p class="text-slate-500">Not generated</p>
            {% endif %}
        </div>
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold">Instagram Carousel</h2>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            {% for slide in social.get('instagram_slides', []) %}
                <div class="bg-slate-800 p-4 rounded-lg text-center text-sm text-slate-300 border border-slate-700">
                    <span class="text-xs text-slate-500 block mb-2">Slide {{ loop.index }}</span>
                    {{ slide }}
                </div>
            {% endfor %}
            </div>
        </div>
    </main>
    <script>
        function copyText(id) {
            var el = document.getElementById(id);
            var text = el ? el.innerText : '';
            navigator.clipboard.writeText(text);
        }
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

def load_draft(slug):
    html_path = DRAFTS_DIR / f"{slug}.html"
    audit_path = DRAFTS_DIR / f"{slug}_audit.json"
    social_path = DRAFTS_DIR / f"{slug}_social.json"
    if not html_path.exists():
        return None
    html = html_path.read_text(encoding="utf-8")
    try:
        audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    except Exception:
        audit = {}
    try:
        social = json.loads(social_path.read_text()) if social_path.exists() else {}
    except Exception:
        social = {}
    return {"html": html, "audit": audit, "social": social, "slug": slug}


@app.route("/")
def dashboard():
    drafts = []
    if DRAFTS_DIR.exists():
        for f in sorted(DRAFTS_DIR.glob("*.html")):
            if f.stem.endswith("_card"):
                continue
            slug = f.stem
            data = load_draft(slug)
            if data:
                title = slug.replace("blog-", "").replace("-", " ").title()
                drafts.append({
                    "slug": slug,
                    "title": title,
                    "cluster": data["audit"].get("cluster", ""),
                    "audit": data["audit"],
                })
    approved = [f.name for f in sorted(APPROVED_DIR.glob("*.html"))] if APPROVED_DIR.exists() else []
    return render_template_string(DASHBOARD_TEMPLATE, drafts=drafts, approved=approved)


@app.route("/review/<slug>")
def review(slug):
    data = load_draft(slug)
    if not data:
        return "Draft not found", 404
    title = slug.replace("blog-", "").replace("-", " ").title()
    return render_template_string(REVIEW_TEMPLATE, title=title, slug=slug, html_content=data["html"], audit=data["audit"])


@app.route("/approve/<slug>", methods=["POST"])
def approve(slug):
    html = request.form.get("html", "")
    if html:
        (DRAFTS_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
    src = DRAFTS_DIR / f"{slug}.html"
    dst = APPROVED_DIR / f"{slug}.html"
    if src.exists():
        content = src.read_text(encoding="utf-8")
        dst.write_text(content, encoding="utf-8")

        # Push to GitHub → triggers Hostinger deployment → goes live
        try:
            from blog_engine import push_to_github, update_blog_index, load_calendar
            filename = f"{slug}.html"
            push_to_github(filename, content, f"Publish: {slug}")
            print(f"  ✓ Approved and pushed to GitHub: {filename}")

            # Update blog.html index page with new article card
            try:
                calendar = load_calendar()
                # Find the post in the calendar by slug
                post = None
                for p in calendar.get("posts", []):
                    if p["slug"] == slug:
                        post = p
                        break
                if post:
                    update_blog_index(post, calendar)
                else:
                    print(f"  ⚠ Post {slug} not found in calendar — blog index not updated")
            except Exception as e:
                print(f"  ⚠ Blog index update failed: {e}")
        except Exception as e:
            print(f"  ✗ GitHub push failed: {e}")

        src.unlink()
        for extra in [f"{slug}_audit.json", f"{slug}_social.json", f"{slug}_card.html", f"{slug}_sitemap.xml"]:
            p = DRAFTS_DIR / extra
            if p.exists():
                p.unlink()
    return redirect("/")


@app.route("/reject/<slug>", methods=["POST"])
def reject(slug):
    src = DRAFTS_DIR / f"{slug}.html"
    if src.exists():
        src.unlink()
        for extra in [f"{slug}_audit.json", f"{slug}_social.json", f"{slug}_card.html", f"{slug}_sitemap.xml"]:
            p = DRAFTS_DIR / extra
            if p.exists():
                p.unlink()
    return redirect("/")


@app.route("/save/<slug>", methods=["POST"])
def save(slug):
    html = request.form.get("html", "")
    if html:
        (DRAFTS_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
    return redirect(f"/review/{slug}")


@app.route("/reset/<slug>")
def reset(slug):
    """Clear a post from both drafts and approved so it can be regenerated."""
    cleared = []
    for folder in [DRAFTS_DIR, APPROVED_DIR]:
        for pattern in [f"{slug}.html", f"{slug}_audit.json", f"{slug}_social.json", f"{slug}_card.html", f"{slug}_sitemap.xml"]:
            p = folder / pattern
            if p.exists():
                p.unlink()
                cleared.append(str(p))
    if cleared:
        return f"Cleared: {', '.join(cleared)} — post can now be regenerated"
    return f"No files found for {slug}"


@app.route("/reset-all")
def reset_all():
    """Clear all drafts and approved files."""
    cleared = 0
    for folder in [DRAFTS_DIR, APPROVED_DIR]:
        for f in folder.glob("*"):
            f.unlink()
            cleared += 1
    return f"Cleared {cleared} files. All posts can now be regenerated."


@app.route("/social/<slug>")
def social(slug):
    data = load_draft(slug)
    if not data:
        return "Draft not found", 404
    title = slug.replace("blog-", "").replace("-", " ").title()
    return render_template_string(SOCIAL_TEMPLATE, title=title, social=data["social"])


@app.route("/trigger/blog")
def trigger_blog():
    def run():
        try:
            from blog_engine import run_manual_pipeline
            run_manual_pipeline()
        except Exception as e:
            print(f"Blog generation error: {e}")
    threading.Thread(target=run, daemon=True).start()
    return redirect("/")


@app.route("/trigger/custom", methods=["POST"])
def trigger_custom():
    title = request.form.get("title", "").strip()
    keywords = request.form.get("keywords", "").strip()
    cluster = request.form.get("cluster", "4_tax_strategy")
    cta = request.form.get("cta", "consultation")
    if not title:
        return redirect("/")
    def run():
        try:
            from blog_engine import run_custom_pipeline
            run_custom_pipeline(title, keywords, cluster, cta)
        except Exception as e:
            print(f"Custom article error: {e}")
    threading.Thread(target=run, daemon=True).start()
    return redirect("/")


@app.route("/generate-alert/<alert_id>")
def generate_alert(alert_id):
    """One-click article generation from a news alert email."""
    alerts_dir = DRAFTS_DIR.parent / "alerts"
    alert_path = alerts_dir / f"{alert_id}.json"

    if not alert_path.exists():
        return f"Alert {alert_id} not found. It may have already been generated or expired.", 404

    alert = json.loads(alert_path.read_text(encoding="utf-8"))

    if alert.get("status") == "generating":
        return "⏳ This article is already being generated. Check your dashboard in ~8 minutes."

    if alert.get("status") == "drafted":
        return f'✅ Article already generated! <a href="/">Go to dashboard to review →</a>'

    # Mark as generating
    alert["status"] = "generating"
    alert_path.write_text(json.dumps(alert, indent=2, ensure_ascii=False), encoding="utf-8")

    def run():
        try:
            from blog_engine import run_custom_pipeline
            title = alert.get("suggested_title", alert.get("headline", "Untitled"))
            keywords = alert.get("suggested_keywords", alert.get("headline", ""))
            cluster = alert.get("cluster_id", "4_tax_strategy")

            # Map CTA from cluster
            cta_map = {
                "1_act60_compliance": "consultation",
                "2_business_structure": "llc-formation",
                "3_bitcoin": "bitcoin-accounting",
                "4_tax_strategy": "consultation",
                "5_operations": "bookkeeping",
            }
            cta = cta_map.get(cluster, "consultation")

            run_custom_pipeline(title, keywords, cluster, cta)

            # Mark as drafted
            alert["status"] = "drafted"
            alert_path.write_text(json.dumps(alert, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"Alert generation error: {e}")
            alert["status"] = "error"
            alert["error"] = str(e)
            alert_path.write_text(json.dumps(alert, indent=2, ensure_ascii=False), encoding="utf-8")

    threading.Thread(target=run, daemon=True).start()

    return f"""
    <html><head><meta charset="UTF-8"><title>Generating Article</title>
    <script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-slate-950 text-white flex items-center justify-center min-h-screen">
        <div class="text-center max-w-md">
            <div class="text-6xl mb-6">⚡</div>
            <h1 class="text-2xl font-black mb-4">Article Generation Started</h1>
            <p class="text-slate-400 mb-2"><strong>Topic:</strong> {alert.get('suggested_title', alert.get('headline', ''))}</p>
            <p class="text-slate-500 text-sm mb-6">The 4-pass pipeline is running (~8 minutes). You'll receive an email when the draft is ready for review.</p>
            <a href="/" class="bg-blue-600 text-white px-6 py-3 rounded-lg font-bold hover:bg-blue-700 transition">Go to Dashboard</a>
        </div>
    </body></html>
    """


@app.route("/alerts")
def view_alerts():
    """View all saved news alerts and their status."""
    alerts_dir = DRAFTS_DIR.parent / "alerts"
    alerts_dir.mkdir(exist_ok=True)
    alerts = []
    for f in sorted(alerts_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            alerts.append(json.loads(f.read_text(encoding="utf-8")))
        except:
            pass
    return render_template_string(ALERTS_TEMPLATE, alerts=alerts)


@app.route("/trigger/news")
def trigger_news():
    def run():
        try:
            run_news_monitor_pipeline()
        except Exception as e:
            print(f"News monitor error: {e}")
    threading.Thread(target=run, daemon=True).start()
    return redirect("/")


@app.route("/repush")
def repush_approved():
    """Re-push all approved files to GitHub (for files that were approved before GitHub push was added)."""
    from blog_engine import push_to_github
    results = []
    for f in APPROVED_DIR.glob("*.html"):
        try:
            content = f.read_text(encoding="utf-8")
            ok = push_to_github(f.name, content, f"Publish: {f.stem}")
            results.append(f"{f.name}: {'✓' if ok else '✗'}")
        except Exception as e:
            results.append(f"{f.name}: error - {e}")
    return "<br>".join(results) if results else "No approved files found"


ALERTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News Alerts</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-white min-h-screen">
    <nav class="bg-slate-900 border-b border-slate-800 px-6 py-4">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
            <div class="flex items-center gap-3">
                <a href="/" class="text-slate-400 hover:text-white transition">← Dashboard</a>
                <span class="text-lg font-bold">📡 News Alerts</span>
            </div>
        </div>
    </nav>
    <main class="max-w-7xl mx-auto px-6 py-8">
        {% if not alerts %}
        <div class="bg-slate-900 rounded-2xl p-12 text-center border border-slate-800">
            <p class="text-xl text-slate-400">No news alerts yet.</p>
            <p class="text-sm text-slate-600 mt-2">The news monitor runs daily at 6:00 AM EST.</p>
        </div>
        {% endif %}
        <div class="grid gap-4">
        {% for a in alerts %}
            <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center gap-3 mb-2">
                            {% if a.status == 'drafted' %}
                                <span class="bg-green-600 text-white text-xs font-bold px-3 py-1 rounded-full">DRAFTED</span>
                            {% elif a.status == 'generating' %}
                                <span class="bg-yellow-600 text-white text-xs font-bold px-3 py-1 rounded-full">GENERATING</span>
                            {% elif a.status == 'error' %}
                                <span class="bg-red-600 text-white text-xs font-bold px-3 py-1 rounded-full">ERROR</span>
                            {% else %}
                                <span class="bg-blue-600 text-white text-xs font-bold px-3 py-1 rounded-full">PENDING</span>
                            {% endif %}
                            <span class="text-red-400 text-xs font-bold">{{ a.urgency }}</span>
                            <span class="text-slate-600 text-xs">{{ a.timestamp[:16] }}</span>
                        </div>
                        <h3 class="text-lg font-bold text-white mb-1">{{ a.headline }}</h3>
                        <p class="text-slate-400 text-sm mb-2">{{ a.source }}</p>
                        <p class="text-slate-500 text-sm">Suggested: "{{ a.suggested_title }}"</p>
                    </div>
                    <div class="ml-4">
                        {% if a.status == 'pending' %}
                            <a href="/generate-alert/{{ a.alert_id }}" class="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-bold hover:bg-green-700 transition whitespace-nowrap">✅ Generate</a>
                        {% elif a.status == 'drafted' %}
                            <a href="/" class="text-green-400 text-sm hover:underline">View in drafts →</a>
                        {% endif %}
                    </div>
                </div>
            </div>
        {% endfor %}
        </div>
    </main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

start_scheduler()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
