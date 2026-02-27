"""
PuertoRicoLLC.com — Blog Review Dashboard
==========================================
A lightweight Flask app hosted on Railway that lets you:
- View all drafts with their audit results
- Preview posts exactly as they'll appear on the site
- Edit post HTML inline before approving
- Approve or reject posts
- View social media derivatives ready to copy/paste or auto-post

Endpoints:
  GET  /                       → Dashboard home (list all drafts)
  GET  /review/<slug>          → Preview + edit a specific draft
  POST /approve/<slug>         → Approve and deploy
  POST /reject/<slug>          → Reject with notes
  POST /save/<slug>            → Save edits without approving
  GET  /social/<slug>          → View social media derivatives
  POST /webhook/whatsapp       → Twilio webhook for WhatsApp replies
"""

import os
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

app = Flask(__name__)

DRAFTS_DIR = Path(os.getenv("DRAFTS_DIR", "./drafts"))
APPROVED_DIR = Path(os.getenv("APPROVED_DIR", "./approved"))
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "change-this-in-production")

# ---------------------------------------------------------------------------
# HTML TEMPLATES (inline for single-file deployment on Railway)
# ---------------------------------------------------------------------------

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog Engine Dashboard — PuertoRicoLLC.com</title>
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
            <div class="text-sm text-slate-400">
                {{ drafts|length }} drafts pending
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-6 py-8">
        <h1 class="text-3xl font-black mb-8">📝 Pending Drafts</h1>
        
        {% if not drafts %}
        <div class="bg-slate-900 rounded-2xl p-12 text-center border border-slate-800">
            <i class="fas fa-check-circle text-green-500 text-5xl mb-4"></i>
            <p class="text-xl text-slate-400">All caught up! No pending drafts.</p>
        </div>
        {% endif %}

        <div class="grid gap-6">
        {% for draft in drafts %}
            <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800 hover:border-slate-600 transition">
                <div class="flex justify-between items-start">
                    <div class="flex-1">
                        <div class="flex items-center gap-3 mb-2">
                            {% if draft.audit.publish_ready %}
                                <span class="bg-green-600 text-white text-xs font-bold px-3 py-1 rounded-full">✅ READY</span>
                            {% else %}
                                <span class="bg-yellow-600 text-white text-xs font-bold px-3 py-1 rounded-full">⚠️ REVIEW</span>
                            {% endif %}
                            <span class="text-slate-500 text-sm">{{ draft.cluster }}</span>
                            <span class="text-slate-600 text-sm">Grade: {{ draft.audit.overall_grade }}</span>
                        </div>
                        <h2 class="text-xl font-bold mb-2">{{ draft.title }}</h2>
                        <div class="flex gap-4 text-sm text-slate-400">
                            <span>🔴 {{ draft.audit.critical_issues|length }} critical</span>
                            <span>🟡 {{ draft.audit.warnings|length }} warnings</span>
                            <span>🟢 {{ draft.audit.suggestions|length }} suggestions</span>
                        </div>
                    </div>
                    <div class="flex gap-3">
                        <a href="/review/{{ draft.slug }}" 
                           class="bg-blue-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-blue-700 transition text-sm">
                            Review & Edit
                        </a>
                        <a href="/social/{{ draft.slug }}"
                           class="bg-slate-700 text-white px-4 py-2 rounded-lg font-bold hover:bg-slate-600 transition text-sm">
                            Social
                        </a>
                    </div>
                </div>

                {% if draft.audit.warnings %}
                <div class="mt-4 pt-4 border-t border-slate-800">
                    <p class="text-sm text-yellow-500 font-bold mb-2">Warnings:</p>
                    {% for w in draft.audit.warnings[:3] %}
                    <p class="text-sm text-slate-400 ml-4">⚠️ {{ w.issue or w.recommendation }}</p>
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
                <a href="https://puertoricollc.com/{{ post }}" target="_blank" class="text-blue-400 text-sm hover:underline">View live →</a>
            </div>
        {% endfor %}
        </div>
        {% endif %}
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
    <title>Review: {{ title }} — Blog Engine</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        .editor-pane { font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 13px; }
        .split-view { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; height: calc(100vh - 200px); }
        .preview-frame { border: none; width: 100%; height: 100%; background: white; border-radius: 12px; }
    </style>
</head>
<body class="bg-slate-950 text-white">
    <nav class="bg-slate-900 border-b border-slate-800 px-6 py-3">
        <div class="max-w-full mx-auto flex justify-between items-center">
            <div class="flex items-center gap-4">
                <a href="/" class="text-slate-400 hover:text-white transition">← Dashboard</a>
                <span class="text-lg font-bold">{{ title }}</span>
                {% if audit.publish_ready %}
                    <span class="bg-green-600 text-xs font-bold px-3 py-1 rounded-full">PASSED AUDIT</span>
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
                    <button type="submit" 
                            class="bg-red-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-red-700 transition text-sm">
                        ✗ Reject
                    </button>
                </form>
            </div>
        </div>
    </nav>

    <!-- Audit Summary Bar -->
    <div class="bg-slate-900 px-6 py-3 border-b border-slate-800 flex gap-6 text-sm overflow-x-auto">
        <span class="text-slate-400">Grade: <strong class="text-white">{{ audit.overall_grade }}</strong></span>
        <span class="text-red-400">🔴 {{ audit.critical_issues|length }} critical</span>
        <span class="text-yellow-400">🟡 {{ audit.warnings|length }} warnings</span>
        <span class="text-green-400">🟢 {{ audit.suggestions|length }} suggestions</span>
        {% for w in audit.warnings[:5] %}
            <span class="text-yellow-500 border-l border-slate-700 pl-4">{{ w.issue or w.recommendation }}</span>
        {% endfor %}
    </div>

    <!-- Split View: Editor + Preview -->
    <div class="px-4 py-4 split-view">
        <div class="flex flex-col">
            <p class="text-sm text-slate-500 mb-2 font-bold">HTML EDITOR (edit directly)</p>
            <textarea id="editor" class="editor-pane flex-1 bg-slate-900 text-green-300 p-4 rounded-xl border border-slate-700 resize-none outline-none focus:border-blue-500"
                      oninput="updatePreview()">{{ html_content }}</textarea>
        </div>
        <div class="flex flex-col">
            <p class="text-sm text-slate-500 mb-2 font-bold">LIVE PREVIEW</p>
            <iframe id="preview" class="preview-frame flex-1"></iframe>
        </div>
    </div>

    <script>
        function updatePreview() {
            const html = document.getElementById('editor').value;
            const iframe = document.getElementById('preview');
            iframe.srcdoc = html;
        }
        // Load initial preview
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
        <!-- LinkedIn -->
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold"><i class="fab fa-linkedin text-blue-400 mr-2"></i>LinkedIn Post</h2>
                <button onclick="copyText('linkedin')" class="bg-slate-700 px-3 py-1 rounded text-sm hover:bg-slate-600">📋 Copy</button>
            </div>
            <pre id="linkedin" class="text-slate-300 whitespace-pre-wrap text-sm leading-relaxed">{{ social.linkedin or 'Not generated' }}</pre>
        </div>

        <!-- Twitter Thread -->
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold"><i class="fab fa-twitter text-sky-400 mr-2"></i>Twitter/X Thread</h2>
                <button onclick="copyText('twitter')" class="bg-slate-700 px-3 py-1 rounded text-sm hover:bg-slate-600">📋 Copy All</button>
            </div>
            <div id="twitter" class="space-y-3">
            {% for tweet in social.twitter_thread or [] %}
                <div class="bg-slate-800 p-3 rounded-lg text-sm text-slate-300">{{ tweet }}</div>
            {% endfor %}
            </div>
        </div>

        <!-- Email Newsletter -->
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold"><i class="fas fa-envelope text-purple-400 mr-2"></i>Email Newsletter</h2>
                <button onclick="copyText('email')" class="bg-slate-700 px-3 py-1 rounded text-sm hover:bg-slate-600">📋 Copy</button>
            </div>
            {% if social.email %}
            <p class="text-yellow-400 text-sm mb-1">Subject: {{ social.email.subject }}</p>
            <p class="text-slate-500 text-sm mb-3">Preview: {{ social.email.preview }}</p>
            <pre id="email" class="text-slate-300 whitespace-pre-wrap text-sm">{{ social.email.body }}</pre>
            {% else %}
            <p class="text-slate-500">Not generated</p>
            {% endif %}
        </div>

        <!-- Instagram Carousel -->
        <div class="bg-slate-900 rounded-2xl p-6 border border-slate-800">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-bold"><i class="fab fa-instagram text-pink-400 mr-2"></i>Instagram Carousel</h2>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            {% for slide in social.instagram_slides or [] %}
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
            const el = document.getElementById(id);
            const text = el ? el.innerText : '';
            navigator.clipboard.writeText(text);
        }
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# ROUTE HANDLERS
# ---------------------------------------------------------------------------

def load_draft(slug):
    """Load a draft and its associated audit/social files."""
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
    for f in sorted(DRAFTS_DIR.glob("*.html")):
        if f.stem.endswith("_card"):
            continue
        slug = f.stem
        data = load_draft(slug)
        if data:
            # Extract title from filename
            title = slug.replace("blog-", "").replace("-", " ").title()
            drafts.append({
                "slug": slug,
                "title": title,
                "cluster": data["audit"].get("cluster", ""),
                "audit": data["audit"],
            })

    approved = [f.name for f in sorted(APPROVED_DIR.glob("*.html"))]

    return render_template_string(DASHBOARD_TEMPLATE, drafts=drafts, approved=approved)


@app.route("/review/<slug>")
def review(slug):
    data = load_draft(slug)
    if not data:
        return "Draft not found", 404

    title = slug.replace("blog-", "").replace("-", " ").title()
    return render_template_string(
        REVIEW_TEMPLATE,
        title=title,
        slug=slug,
        html_content=data["html"],
        audit=data["audit"],
    )


@app.route("/approve/<slug>", methods=["POST"])
def approve(slug):
    html = request.form.get("html", "")
    if html:
        # Save the edited version
        (DRAFTS_DIR / f"{slug}.html").write_text(html, encoding="utf-8")

    # Move to approved
    src = DRAFTS_DIR / f"{slug}.html"
    dst = APPROVED_DIR / f"{slug}.html"
    if src.exists():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # TODO: trigger GitHub deploy here (git commit + push)

    return redirect("/")


@app.route("/reject/<slug>", methods=["POST"])
def reject(slug):
    # Move to a rejected folder or just delete
    src = DRAFTS_DIR / f"{slug}.html"
    if src.exists():
        rejected_dir = Path("./rejected")
        rejected_dir.mkdir(exist_ok=True)
        (rejected_dir / f"{slug}.html").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        src.unlink()

    return redirect("/")


@app.route("/save/<slug>", methods=["POST"])
def save(slug):
    html = request.form.get("html", "")
    if html:
        (DRAFTS_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
    return redirect(f"/review/{slug}")


@app.route("/social/<slug>")
def social(slug):
    data = load_draft(slug)
    if not data:
        return "Draft not found", 404

    title = slug.replace("blog-", "").replace("-", " ").title()
    return render_template_string(SOCIAL_TEMPLATE, title=title, social=data["social"])


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
