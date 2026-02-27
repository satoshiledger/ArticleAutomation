"""
PuertoRicoLLC.com — Automated Blog Engine
==========================================
Satoshi Ledger LLC | @SatoshiLedger

Multi-pass AI content pipeline:
  Pass 1: Research & Generate (Claude API + Web Search)
  Pass 2: Adversarial Fact-Check Audit (separate Claude call)
  Pass 3: Auto-Fix Critical Issues (if any found)
  Pass 4: Generate Social Media Derivatives
  → Gmail notification → You review/edit → Approve → Deploy

Stack: Railway (cron) → Claude API → GitHub → Hostinger
Notifications: Gmail SMTP (free, no extra accounts needed)

Usage:
  python blog_engine.py --mode scheduled    # Runs the next scheduled post
  python blog_engine.py --mode reactive     # Runs the daily news monitor
  python blog_engine.py --mode generate --topic "Custom topic here"
"""

import os
import json
import hashlib
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
import argparse

# ---------------------------------------------------------------------------
# CONFIGURATION — set these as environment variables on Railway
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "your-email@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # 16-char app password, NOT your regular password
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "your-email@gmail.com")  # where to receive notifications
GITHUB_REPO = os.getenv("GITHUB_REPO", "your-username/puertoricollc.com")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://your-railway-app.up.railway.app")
DRAFTS_DIR = Path(os.getenv("DRAFTS_DIR", "./drafts"))
APPROVED_DIR = Path(os.getenv("APPROVED_DIR", "./approved"))
CALENDAR_PATH = Path(os.getenv("CALENDAR_PATH", "./content_calendar.json"))

DRAFTS_DIR.mkdir(exist_ok=True)
APPROVED_DIR.mkdir(exist_ok=True)

SITE_URL = "https://puertoricollc.com"
GA_TRACKING_ID = "G-L7DET25V5W"

# ---------------------------------------------------------------------------
# SYSTEM PROMPTS — the core of the quality pipeline
# ---------------------------------------------------------------------------

PASS1_SYSTEM_PROMPT = """You are the senior content writer for PuertoRicoLLC.com (Satoshi Ledger LLC), 
a Puerto Rico-based tax compliance and accounting firm specializing in Act 60 decree management, 
LLC formation, bookkeeping, forensic audits, and Bitcoin/crypto tax accounting.

## YOUR WRITING STANDARD
You write at the A++ gold standard of accounting content. Every claim must be:
- Sourced from official government publications (IRS, Hacienda, DDEC, FinCEN, SEC)
- Cited with the specific section of law, notice number, or regulation
- Accurate to the letter — a wrong number or outdated rate could cost readers real money

## VOICE & TONE
- Authoritative but approachable — like a senior CPA who explains things clearly
- Never condescending. Your readers are smart business owners and investors.
- Use real examples with dollar amounts to illustrate tax concepts
- Bilingual: produce both English and Spanish versions in the same HTML file

## BITCOIN POLICY (CRITICAL)
- Bitcoin ONLY. Never mention altcoins, Ethereum, DeFi tokens, NFTs, or any other cryptocurrency.
- When discussing Bitcoin, focus on: long-term holding, business treasury, capital gains, 
  mining operations, and tax compliance.
- No speculation, no price predictions, no trading advice.

## CONTENT RULES
1. Every tax rate MUST cite the specific law section (e.g., "Section 2031.01(b) of Act 60-2019")
2. Every filing fee MUST cite the government agency's published fee schedule
3. Every deadline MUST cite the specific regulation or form instructions
4. If you CANNOT verify a specific number from an official source, write: 
   "Verify current rate at [source URL]" — NEVER guess
5. Include a "Sources & References" section at the bottom with direct links
6. Include the disclaimer: "This content is for informational purposes only and does not 
   constitute legal or tax advice. Consult a qualified attorney or CPA for advice specific 
   to your situation."
7. Every post MUST have a clear CTA linking to the appropriate PuertoRicoLLC.com service

## HTML TEMPLATE REQUIREMENTS
- Use the exact same HTML structure, Tailwind classes, nav, footer, WhatsApp button, 
  and language toggle as existing PuertoRicoLLC.com blog posts
- Include: Open Graph meta tags, Twitter Card meta, Schema.org Article markup, 
  Google Analytics (G-L7DET25V5W)
- All content MUST be bilingual with data-lang="en" and data-lang="es" attributes
- Hero image: use a relevant Unsplash URL with ?w=1200&h=600&fit=crop&q=80
- Category badge, publish date, estimated read time
- Social share buttons (Facebook, Twitter, LinkedIn, WhatsApp)
- Internal links to other PuertoRicoLLC.com pages where relevant

## AVAILABLE INTERNAL LINKS
- index.html (homepage + contact form)
- act60-mastery.html (Act 60 comprehensive page)
- llc-formation.html (LLC formation service)
- forensic-audit.html (forensic audit service)
- bookkeeping-payroll.html (bookkeeping service)
- blog.html (blog index)
- blog-4percent-strategy.html (4% tax strategy article)
- blog-llc-vs-corp-reasonable-salary.html (reasonable salary article)
- blog-llc-vs-scorp-savings.html (LLC vs Corp savings article)
- blog-optional-tax-method.html (optional tax method article)
- blog-young-entrepreneur.html (young entrepreneur article)

You MUST output ONLY the complete HTML file. No explanation, no markdown, no preamble.
Start with <!DOCTYPE html> and end with </html>.
"""

PASS2_AUDIT_PROMPT = """You are a senior CPA and tax attorney conducting a pre-publication 
compliance audit of a blog post for PuertoRicoLLC.com. Your professional reputation is on the 
line. This content will be read by IRS auditors, CPAs, and high-net-worth individuals making 
six-figure financial decisions based on it.

## YOUR AUDIT CHECKLIST

For EVERY factual claim in the post:

1. VERIFY CITATIONS: Does the cited law section/notice/ruling actually say what the post claims?
   Flag any incorrect or nonexistent citations.

2. VERIFY NUMBERS: Are all tax rates, fees, thresholds, and deadlines accurate?
   Cross-reference against official sources. Flag any that may be outdated.

3. VERIFY BITCOIN TREATMENT: Does the post correctly distinguish between:
   - Capital gains vs. ordinary income
   - Pre-move vs. post-move appreciation 
   - Personal investment vs. business activity
   - Chapter 2 (individual) vs. Chapter 3 (export services) treatment
   Flag any conflation or oversimplification.

4. CHECK FOR MISSING CITATIONS: Flag any factual claim that lacks a specific source reference.

5. CHECK DISCLAIMERS: Does the post include proper "not legal/tax advice" disclaimers?
   Does it avoid language that could be construed as personalized advice?

6. CHECK SPANISH ACCURACY: Do the Spanish translations accurately convey the same 
   technical meaning? Are legal/tax terms translated correctly?
   (e.g., "capital gains" = "ganancias de capital", not "ganancias capitales")

7. CHECK FOR STALE INFORMATION: Flag any claim about pending legislation, rates, or 
   rules that may have changed. Note what needs to be verified against current sources.

8. CHECK INTERNAL CONSISTENCY: Do the numbers in examples add up? Are percentages applied correctly?

## OUTPUT FORMAT (respond ONLY in this JSON structure)

{
  "overall_grade": "A/B/C/F",
  "publish_ready": true/false,
  "critical_issues": [
    {
      "severity": "CRITICAL",
      "location": "paragraph/section description",
      "issue": "what's wrong",
      "fix": "suggested correction",
      "source_to_verify": "URL or document name"
    }
  ],
  "warnings": [
    {
      "severity": "WARNING",
      "location": "paragraph/section description",
      "issue": "what's concerning",
      "recommendation": "what to check or change"
    }
  ],
  "suggestions": [
    {
      "severity": "SUGGESTION",
      "location": "paragraph/section description",
      "suggestion": "improvement idea"
    }
  ],
  "sources_verified": [
    {"claim": "summary of claim", "source": "citation", "status": "VERIFIED/UNVERIFIED/OUTDATED"}
  ],
  "spanish_issues": [
    {"location": "where", "issue": "translation problem", "fix": "corrected text"}
  ]
}
"""

PASS3_FIX_PROMPT = """You are correcting a blog post for PuertoRicoLLC.com based on audit findings.

You will receive:
1. The original HTML blog post
2. The audit report with CRITICAL issues that must be fixed

Your job:
- Fix EVERY critical issue identified in the audit
- Verify corrections against the source documents cited
- Do NOT change anything that wasn't flagged
- Maintain the exact same HTML structure and formatting
- Output ONLY the corrected complete HTML file

Start with <!DOCTYPE html> and end with </html>.
"""

SOCIAL_MEDIA_PROMPT = """You generate social media derivative content from a published blog post 
for PuertoRicoLLC.com (@SatoshiLedger).

Generate ALL of the following from the blog post provided:

## 1. LINKEDIN POST (200-300 words)
- Written as the founder of Satoshi Ledger LLC, first person
- Professional but not corporate — knowledgeable and direct
- Opens with a hook that would stop a scrolling Act 60 holder or potential relocator
- Ends with a link to the full article
- Include 3-5 relevant hashtags

## 2. TWITTER/X THREAD (5-7 tweets)
- Thread format: "🧵 1/7: [hook]"
- Each tweet under 280 characters
- Last tweet links to the full article
- Mix of insight, data points, and practical takeaways

## 3. EMAIL NEWSLETTER SNIPPET (3 paragraphs)
- Subject line (compelling, under 60 characters)
- Preview text (under 100 characters)
- 3-paragraph summary with "Read the full analysis →" CTA

## 4. INSTAGRAM CAROUSEL TEXT (6-8 slides)
- Slide 1: Bold headline/hook
- Slides 2-6: Key points (short, visual-friendly text)
- Slide 7: CTA to visit the blog
- Slide 8: Brand slide — PuertoRicoLLC.com | @SatoshiLedger

Output as JSON with keys: linkedin, twitter_thread (array), email (with subject, preview, body), 
instagram_slides (array of slide text).
"""

NEWS_MONITOR_PROMPT = """You are a regulatory news monitor for PuertoRicoLLC.com, a Puerto Rico 
tax compliance firm specializing in Act 60 and Bitcoin tax accounting.

Your job: Scan the provided search results and determine if any contain NEW regulatory 
developments that would be relevant to the firm's audience (Act 60 decree holders, PR business 
owners, Bitcoin investors in PR).

Relevant triggers include:
- New IRS guidance, notices, or revenue rulings affecting US territories or digital assets
- New Hacienda circulars or administrative determinations
- Changes to DDEC decree application requirements
- New legislation passed or signed affecting PR tax incentives
- FinCEN updates on FBAR or BSA reporting for Bitcoin
- SEC actions affecting Bitcoin ETFs or digital asset classification
- FASB updates on Bitcoin accounting standards
- Federal court decisions affecting Act 60 or territorial tax treatment

For each relevant development found, output JSON:
{
  "alerts": [
    {
      "headline": "short description",
      "source": "official source name and URL",
      "relevance": "why this matters to Act 60 holders / Bitcoin investors in PR",
      "urgency": "HIGH/MEDIUM/LOW",
      "suggested_title": "blog post title that would cover this",
      "suggested_slug": "blog-url-slug",
      "cluster": "which of the 5 clusters this fits"
    }
  ],
  "no_alerts": true/false
}

If nothing relevant was found, return: {"alerts": [], "no_alerts": true}
"""


# ---------------------------------------------------------------------------
# CORE ENGINE
# ---------------------------------------------------------------------------

def call_claude(system_prompt: str, user_message: str, use_web_search: bool = False) -> str:
    """Call the Anthropic API using the official SDK. Supports web search for live research."""
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    model = "claude-sonnet-4-5-20250929"

    print(f"  Calling Claude API (model: {model}, web_search: {use_web_search})...")

    kwargs = {
        "model": model,
        "max_tokens": 16000,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }

    # Web search: lets Claude research current laws, IRS notices, Hacienda circulars
    # in real time — critical for tax/legal accuracy
    if use_web_search:
        kwargs["tools"] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 10,
        }]

    try:
        response = client.messages.create(**kwargs)
    except anthropic.APIError as e:
        print(f"  API Error: {e}")
        raise

    # Extract text from content blocks
    text_parts = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)

    print(f"  API response received ({len(text_parts)} text blocks, "
          f"stop_reason: {response.stop_reason})")
    return "\n".join(text_parts)


def send_email(subject: str, body_text: str, body_html: str = ""):
    """Send an email notification via Gmail SMTP.
    Tries TLS on port 587 first (works on Railway), falls back to SSL on 465."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = NOTIFY_EMAIL

    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    # Try port 587 (STARTTLS) first — Railway blocks port 465
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, NOTIFY_EMAIL, msg.as_string())
            print(f"  ✓ Email sent via port 587 (TLS)")
            return
    except Exception as e:
        print(f"  Port 587 failed: {e}, trying port 465...")

    # Fallback: port 465 (SSL)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, NOTIFY_EMAIL, msg.as_string())
            print(f"  ✓ Email sent via port 465 (SSL)")
    except Exception as e:
        print(f"  ✗ Email error (both ports failed): {e}")
        raise


def load_calendar() -> dict:
    """Load the content calendar JSON."""
    with open(CALENDAR_PATH) as f:
        return json.load(f)


def get_next_scheduled_post(calendar: dict) -> dict | None:
    """Determine which post to generate based on today's date and day of week."""
    today = datetime.now()
    day_name = today.strftime("%A").lower()

    day_map = {"monday": "monday", "wednesday": "wednesday", "friday": "friday"}
    if day_name not in day_map:
        return None

    # Find posts for today's day that haven't been generated yet
    for post in calendar["posts"]:
        if post["day"] == day_name:
            draft_path = DRAFTS_DIR / f"{post['slug']}.html"
            approved_path = APPROVED_DIR / f"{post['slug']}.html"
            if not draft_path.exists() and not approved_path.exists():
                return post

    return None


# ---------------------------------------------------------------------------
# PASS 1 — RESEARCH & GENERATE
# ---------------------------------------------------------------------------

def pass1_generate(post: dict, calendar: dict) -> str:
    """Generate the blog post HTML using Claude API with web search for source verification."""

    cluster_info = calendar["clusters"][post["cluster"]]

    user_message = f"""Generate a complete blog post HTML file for PuertoRicoLLC.com.

## POST DETAILS
- Title (EN): {post['title_en']}
- Title (ES): {post['title_es']}
- URL slug: {post['slug']}
- Category tag: {cluster_info['category_tag']}
- Category label (EN): {cluster_info['category_label_en']}
- Category label (ES): {cluster_info['category_label_es']}
- Target keywords: {post['keywords']}
- Required sources to cite: {json.dumps(post['sources_required'])}
- CTA service: {post.get('cta', cluster_info['cta_service'])}
- Publish date: {datetime.now().strftime('%B %d, %Y')}
- Full URL: {SITE_URL}/{post['slug']}.html

## INSTRUCTIONS
1. FIRST, use web search to find the CURRENT text/provisions of each required source.
   Search for the actual government publications. Do NOT rely on memory for any numbers.
2. Write a comprehensive 2,000-2,500 word article (English) with full Spanish translation.
3. Include at least 3 real-world examples with dollar amounts.
4. Cite every factual claim with the specific law section or government source.
5. Include a Sources & References section at the bottom with URLs.
6. Match the exact HTML template structure of existing PuertoRicoLLC.com blog posts
   (Tailwind CSS, slate-900 nav, bilingual data-lang attributes, WhatsApp float button, 
   social share buttons, GA tracking code {GA_TRACKING_ID}).

Output ONLY the complete HTML file. No explanation.
"""

    print("  [Pass 1] Generating blog post with web search for source verification...")
    html = call_claude(PASS1_SYSTEM_PROMPT, user_message, use_web_search=True)

    # Clean any markdown fencing if present
    html = re.sub(r"^```html?\s*", "", html, flags=re.MULTILINE)
    html = re.sub(r"```\s*$", "", html, flags=re.MULTILINE)
    html = html.strip()

    return html


# ---------------------------------------------------------------------------
# PASS 2 — ADVERSARIAL FACT-CHECK AUDIT
# ---------------------------------------------------------------------------

def pass2_audit(html: str, post: dict) -> dict:
    """Run an adversarial fact-check audit on the generated blog post."""

    user_message = f"""Audit the following blog post for factual accuracy and compliance.

## POST METADATA
- Title: {post['title_en']}
- Target keywords: {post['keywords']}
- Required sources: {json.dumps(post['sources_required'])}

## BLOG POST HTML
{html}

Conduct your full audit and respond ONLY with the JSON audit report.
"""

    print("  [Pass 2] Running adversarial fact-check audit...")
    raw = call_claude(PASS2_AUDIT_PROMPT, user_message, use_web_search=True)

    # Parse JSON from response
    raw = re.sub(r"^```json?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)

    try:
        audit = json.loads(raw.strip())
    except json.JSONDecodeError:
        audit = {
            "overall_grade": "UNKNOWN",
            "publish_ready": False,
            "critical_issues": [{"severity": "CRITICAL", "issue": "Audit response was not valid JSON — manual review required"}],
            "warnings": [],
            "suggestions": [],
            "raw_response": raw[:2000],
        }

    return audit


# ---------------------------------------------------------------------------
# PASS 3 — AUTO-FIX CRITICAL ISSUES
# ---------------------------------------------------------------------------

def pass3_fix(html: str, audit: dict, post: dict) -> str:
    """Fix critical issues found during the audit."""

    if not audit.get("critical_issues"):
        return html

    user_message = f"""Fix the following critical issues in this blog post.

## CRITICAL ISSUES TO FIX
{json.dumps(audit['critical_issues'], indent=2)}

## ORIGINAL HTML
{html}

Output ONLY the corrected complete HTML file.
"""

    print("  [Pass 3] Fixing critical issues...")
    fixed = call_claude(PASS3_FIX_PROMPT, user_message, use_web_search=True)

    fixed = re.sub(r"^```html?\s*", "", fixed, flags=re.MULTILINE)
    fixed = re.sub(r"```\s*$", "", fixed, flags=re.MULTILINE)

    return fixed.strip()


# ---------------------------------------------------------------------------
# PASS 4 — SOCIAL MEDIA DERIVATIVES
# ---------------------------------------------------------------------------

def pass4_social(html: str, post: dict) -> dict:
    """Generate social media derivative content from the approved blog post."""

    user_message = f"""Generate social media derivatives for this blog post.

## POST INFO
- Title: {post['title_en']}
- URL: {SITE_URL}/{post['slug']}.html
- Keywords: {post['keywords']}

## BLOG POST HTML
{html[:8000]}

Generate LinkedIn post, Twitter thread, email newsletter snippet, and Instagram carousel text.
Output as JSON only.
"""

    print("  [Pass 4] Generating social media derivatives...")
    raw = call_claude(SOCIAL_MEDIA_PROMPT, user_message)

    raw = re.sub(r"^```json?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)

    try:
        social = json.loads(raw.strip())
    except json.JSONDecodeError:
        social = {"error": "Could not parse social media content", "raw": raw[:2000]}

    return social


# ---------------------------------------------------------------------------
# NEWS MONITOR — reactive content detection
# ---------------------------------------------------------------------------

def run_news_monitor():
    """Daily scan of government sources for new developments."""

    search_queries = [
        "IRS new guidance Puerto Rico territory 2026",
        "Hacienda Puerto Rico nueva circular 2026",
        "DDEC Puerto Rico decree update 2026",
        "bitcoin tax IRS new ruling 2026",
        "FinCEN cryptocurrency reporting update 2026",
        "Puerto Rico Act 60 legislation 2026",
        "Congress Puerto Rico tax incentive bill 2026",
    ]

    user_message = f"""Search for recent regulatory developments using these queries:

{json.dumps(search_queries, indent=2)}

For each query, search the web and evaluate the results. 
Report ONLY genuinely NEW developments from the past 7 days that would affect:
- Act 60 decree holders in Puerto Rico
- Bitcoin investors/holders in Puerto Rico  
- PR business owners (LLCs, corporations)
- US tax obligations for PR residents

Do NOT report routine news, opinion pieces, or old information. 
Only official government actions: new laws signed, new IRS guidance published, 
new Hacienda circulars, new FinCEN rules, court decisions, etc.

Output ONLY the JSON report.
"""

    print("[News Monitor] Scanning government sources...")
    raw = call_claude(NEWS_MONITOR_PROMPT, user_message, use_web_search=True)

    raw = re.sub(r"^```json?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)

    try:
        report = json.loads(raw.strip())
    except json.JSONDecodeError:
        report = {"alerts": [], "no_alerts": True, "parse_error": True}

    return report


# ---------------------------------------------------------------------------
# WHATSAPP NOTIFICATION FORMATTING
# ---------------------------------------------------------------------------

def format_draft_notification(post: dict, audit: dict, draft_path: str) -> tuple[str, str, str]:
    """Format an email notification for a new draft. Returns (subject, plain_text, html)."""

    grade = audit.get("overall_grade", "?")
    critical = len(audit.get("critical_issues", []))
    warnings = len(audit.get("warnings", []))
    suggestions = len(audit.get("suggestions", []))

    status = "✅ PASSED" if audit.get("publish_ready") else "⚠️ NEEDS REVIEW"
    review_url = f"{DASHBOARD_URL}/review/{post['slug']}"
    social_url = f"{DASHBOARD_URL}/social/{post['slug']}"

    subject = f"{'✅' if audit.get('publish_ready') else '⚠️'} Blog Draft: {post['title_en'][:60]}"

    plain_text = f"""{status} — Blog Draft Ready for Review

Title: {post['title_en']}
Cluster: {post['cluster']}
Audit Grade: {grade}
Critical: {critical} | Warnings: {warnings} | Suggestions: {suggestions}

Review & Edit: {review_url}
Social Content: {social_url}
"""

    for w in audit.get("warnings", [])[:5]:
        plain_text += f"\n⚠️ {w.get('issue', w.get('recommendation', ''))[:120]}"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: #0F172A; padding: 20px 24px; border-radius: 12px 12px 0 0;">
        <span style="color: #CC0000; font-weight: 900; font-size: 18px;">PuertoRico</span><span style="color: #3A99D8; font-weight: 900; font-size: 18px;">LLC</span>
        <span style="color: #64748B; font-size: 14px; margin-left: 8px;">Blog Engine</span>
      </div>
      <div style="background: #ffffff; border: 1px solid #E2E8F0; padding: 24px; border-radius: 0 0 12px 12px;">
        <div style="background: {'#F0FDF4' if audit.get('publish_ready') else '#FFFBEB'}; border-left: 4px solid {'#16A34A' if audit.get('publish_ready') else '#EAB308'}; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 20px;">
          <strong style="font-size: 16px;">{status}</strong>
          <span style="color: #64748B; font-size: 14px; margin-left: 8px;">Audit Grade: {grade}</span>
        </div>

        <h2 style="color: #0F172A; font-size: 20px; margin: 0 0 8px 0;">{post['title_en']}</h2>
        <p style="color: #64748B; font-size: 14px; margin: 0 0 20px 0;">Cluster: {post['cluster']} &nbsp;|&nbsp; 🔴 {critical} critical &nbsp;|&nbsp; 🟡 {warnings} warnings &nbsp;|&nbsp; 🟢 {suggestions} suggestions</p>

        {''.join(f'<p style="color: #92400E; background: #FFFBEB; padding: 8px 12px; border-radius: 6px; font-size: 13px; margin: 4px 0;">⚠️ {w.get("issue", w.get("recommendation", ""))[:150]}</p>' for w in audit.get("warnings", [])[:5])}

        <div style="margin-top: 24px; text-align: center;">
          <a href="{review_url}" style="display: inline-block; background: #1E3A8A; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px; margin-right: 8px;">✏️ Review & Edit</a>
          <a href="{social_url}" style="display: inline-block; background: #475569; color: white; padding: 14px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px;">📱 Social Content</a>
        </div>

        <p style="color: #94A3B8; font-size: 12px; text-align: center; margin-top: 24px;">Satoshi Ledger LLC | PuertoRicoLLC.com</p>
      </div>
    </div>
    """

    return subject, plain_text, html


def format_news_alert(alert: dict) -> tuple[str, str, str]:
    """Format an email notification for a news alert. Returns (subject, plain_text, html)."""

    subject = f"🔴 New Content Opportunity: {alert.get('headline', 'Regulatory Update')[:50]}"

    plain_text = f"""BREAKING: Content Opportunity Detected

Headline: {alert['headline']}
Source: {alert['source']}
Relevance: {alert['relevance']}
Urgency: {alert['urgency']}

Suggested post: "{alert['suggested_title']}"
Cluster: {alert['cluster']}

To generate a draft, trigger manually in Railway or reply to this email.
"""

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: #0F172A; padding: 20px 24px; border-radius: 12px 12px 0 0;">
        <span style="color: #CC0000; font-weight: 900; font-size: 18px;">PuertoRico</span><span style="color: #3A99D8; font-weight: 900; font-size: 18px;">LLC</span>
        <span style="color: #EF4444; font-size: 14px; margin-left: 8px;">⚡ ALERT</span>
      </div>
      <div style="background: #ffffff; border: 1px solid #E2E8F0; padding: 24px; border-radius: 0 0 12px 12px;">
        <div style="background: #FEF2F2; border-left: 4px solid #EF4444; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 20px;">
          <strong style="font-size: 14px; color: #991B1B;">🔴 Urgency: {alert['urgency']}</strong>
        </div>
        <h2 style="color: #0F172A; font-size: 20px; margin: 0 0 12px 0;">{alert['headline']}</h2>
        <p style="color: #475569; font-size: 14px;"><strong>Source:</strong> {alert['source']}</p>
        <p style="color: #475569; font-size: 14px;"><strong>Why it matters:</strong> {alert['relevance']}</p>
        <div style="background: #F8FAFC; padding: 16px; border-radius: 8px; margin: 16px 0;">
          <p style="color: #64748B; font-size: 13px; margin: 0 0 4px 0;">Suggested blog post:</p>
          <p style="color: #0F172A; font-weight: bold; margin: 0;">"{alert['suggested_title']}"</p>
        </div>
        <p style="color: #94A3B8; font-size: 12px; text-align: center; margin-top: 24px;">To generate this post, trigger a manual run in Railway dashboard.</p>
      </div>
    </div>
    """

    return subject, plain_text, html


# ---------------------------------------------------------------------------
# BLOG.HTML & SITEMAP UPDATER
# ---------------------------------------------------------------------------

def generate_blog_card_html(post: dict, calendar: dict) -> str:
    """Generate the HTML card snippet for blog.html."""
    cluster = calendar["clusters"][post["cluster"]]
    date_str = datetime.now().strftime("%B %d, %Y")
    date_str_es = datetime.now().strftime("%d %B %Y")

    return f"""
                <!-- {post['slug']} -->
                <article class="blog-card bg-white rounded-2xl shadow-lg overflow-hidden border border-slate-100"
                         data-category="{cluster['category_tag']}">
                    <div class="p-8">
                        <div class="flex items-center gap-3 mb-4">
                            <span class="bg-{cluster['color']}-100 text-{cluster['color']}-800 px-3 py-1 rounded-full text-xs font-bold">
                                <span data-lang="en">{cluster['category_label_en']}</span>
                                <span data-lang="es">{cluster['category_label_es']}</span>
                            </span>
                            <span class="text-slate-400 text-xs">
                                <span data-lang="en">{date_str}</span>
                                <span data-lang="es">{date_str_es}</span>
                            </span>
                        </div>
                        <h3 class="text-xl font-black text-slate-900 mb-3 hover:text-blue-600 transition">
                            <a href="{post['slug']}.html">
                                <span data-lang="en">{post['title_en']}</span>
                                <span data-lang="es">{post['title_es']}</span>
                            </a>
                        </h3>
                        <a href="{post['slug']}.html" class="inline-flex items-center gap-2 text-blue-600 font-bold text-sm hover:text-blue-700 transition">
                            <span data-lang="en">Read Full Article</span>
                            <span data-lang="es">Leer Artículo Completo</span>
                            <i class="fas fa-arrow-right text-xs"></i>
                        </a>
                    </div>
                </article>"""


def generate_sitemap_entry(post: dict) -> str:
    """Generate a sitemap.xml entry for the new post."""
    date = datetime.now().strftime("%Y-%m-%d")
    return f"""  <url>
    <loc>{SITE_URL}/{post['slug']}.html</loc>
    <lastmod>{date}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>"""


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def run_scheduled_pipeline():
    """Run the full scheduled blog generation pipeline."""
    calendar = load_calendar()
    post = get_next_scheduled_post(calendar)

    if not post:
        print("No scheduled post for today or all posts already generated.")
        return

    print(f"\n{'='*60}")
    print(f"GENERATING: {post['title_en']}")
    print(f"Cluster: {post['cluster']}")
    print(f"Slug: {post['slug']}")
    print(f"{'='*60}\n")

    # Pass 1: Generate
    html = pass1_generate(post, calendar)
    draft_path = DRAFTS_DIR / f"{post['slug']}.html"
    draft_path.write_text(html, encoding="utf-8")
    print(f"  ✓ Draft saved: {draft_path}")

    # Pass 2: Audit
    audit = pass2_audit(html, post)
    audit_path = DRAFTS_DIR / f"{post['slug']}_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"  ✓ Audit saved: {audit_path}")
    print(f"  Grade: {audit.get('overall_grade', '?')} | "
          f"Critical: {len(audit.get('critical_issues', []))} | "
          f"Warnings: {len(audit.get('warnings', []))}")

    # Pass 3: Fix critical issues (if any)
    if audit.get("critical_issues"):
        print(f"  ⚠ {len(audit['critical_issues'])} critical issues found — auto-fixing...")
        html = pass3_fix(html, audit, post)
        draft_path.write_text(html, encoding="utf-8")

        # Re-audit the fixed version
        audit2 = pass2_audit(html, post)
        audit_path.write_text(json.dumps(audit2, indent=2), encoding="utf-8")
        print(f"  ✓ Post-fix audit: Grade {audit2.get('overall_grade', '?')} | "
              f"Critical: {len(audit2.get('critical_issues', []))}")
        audit = audit2

    # Pass 4: Social media derivatives
    social = pass4_social(html, post)
    social_path = DRAFTS_DIR / f"{post['slug']}_social.json"
    social_path.write_text(json.dumps(social, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✓ Social content saved: {social_path}")

    # Generate blog card and sitemap entry
    card_html = generate_blog_card_html(post, calendar)
    card_path = DRAFTS_DIR / f"{post['slug']}_card.html"
    card_path.write_text(card_html, encoding="utf-8")

    sitemap_entry = generate_sitemap_entry(post)
    sitemap_path = DRAFTS_DIR / f"{post['slug']}_sitemap.xml"
    sitemap_path.write_text(sitemap_entry, encoding="utf-8")

    # Send email notification
    try:
        subject, plain, html = format_draft_notification(post, audit, str(draft_path))
        send_email(subject, plain, html)
        print(f"  ✓ Email notification sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"  ✗ Email error: {e}")
        subject, plain, _ = format_draft_notification(post, audit, str(draft_path))
        print(f"  Subject: {subject}")
        print(f"  {plain[:300]}")

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE — awaiting your approval")
    print(f"{'='*60}\n")


def run_news_monitor_pipeline():
    """Run the daily news monitoring scan."""
    print(f"\n{'='*60}")
    print(f"NEWS MONITOR — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    report = run_news_monitor()

    if report.get("no_alerts", True) and not report.get("alerts"):
        print("  No new regulatory developments detected today.")
        return

    for alert in report.get("alerts", []):
        print(f"\n  🔴 ALERT: {alert.get('headline', 'Unknown')}")
        print(f"     Source: {alert.get('source', 'Unknown')}")
        print(f"     Urgency: {alert.get('urgency', 'Unknown')}")

        try:
            subject, plain, html = format_news_alert(alert)
            send_email(subject, plain, html)
            print(f"     ✓ Email alert sent")
        except Exception as e:
            print(f"     ✗ Email error: {e}")
            subject, plain, _ = format_news_alert(alert)
            print(f"     Subject: {subject}")


# ---------------------------------------------------------------------------
# APPROVAL & DEPLOY (called by the dashboard or webhook)
# ---------------------------------------------------------------------------

def approve_and_deploy(slug: str):
    """Deploy an approved blog post to GitHub."""
    import subprocess

    draft_path = DRAFTS_DIR / f"{slug}.html"
    if not draft_path.exists():
        print(f"Draft not found: {draft_path}")
        return False

    # Move to approved
    approved_path = APPROVED_DIR / f"{slug}.html"
    html = draft_path.read_text(encoding="utf-8")
    approved_path.write_text(html, encoding="utf-8")

    # In production, this would:
    # 1. git clone the repo (or pull latest)
    # 2. Copy the HTML file to the repo root
    # 3. Update blog.html with the new card
    # 4. Update sitemap.xml with the new entry
    # 5. git add, commit, push
    # 6. Hostinger auto-deploys from GitHub

    print(f"✓ Post approved and deployed: {slug}")
    print(f"  Blog file: {SITE_URL}/{slug}.html")

    # Send confirmation
    try:
        send_email(
            f"✅ Published: {slug}",
            f"Your blog post is live!\n\n{SITE_URL}/{slug}.html\n\nSocial content ready in dashboard: {DASHBOARD_URL}/social/{slug}",
            f'<p>Your blog post is live!</p><p><a href="{SITE_URL}/{slug}.html">{SITE_URL}/{slug}.html</a></p><p><a href="{DASHBOARD_URL}/social/{slug}">View social content →</a></p>',
        )
    except Exception:
        pass

    return True


# ---------------------------------------------------------------------------
# CLI ENTRY POINT
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PuertoRicoLLC.com Blog Engine")
    parser.add_argument("--mode", choices=["scheduled", "reactive", "generate", "approve"],
                        required=True, help="Pipeline mode")
    parser.add_argument("--topic", type=str, help="Custom topic for 'generate' mode")
    parser.add_argument("--slug", type=str, help="Post slug for 'approve' mode")

    args = parser.parse_args()

    if args.mode == "scheduled":
        run_scheduled_pipeline()
    elif args.mode == "reactive":
        run_news_monitor_pipeline()
    elif args.mode == "approve":
        if not args.slug:
            print("--slug required for approve mode")
            return
        approve_and_deploy(args.slug)
    elif args.mode == "generate":
        # Custom topic generation — creates a one-off post
        if not args.topic:
            print("--topic required for generate mode")
            return
        custom_post = {
            "slug": f"blog-{args.topic.lower().replace(' ', '-')[:50]}",
            "title_en": args.topic,
            "title_es": args.topic,  # Will be translated by Claude
            "keywords": args.topic,
            "sources_required": [],
            "cluster": "4_tax_strategy",
            "cta": "consultation",
        }
        calendar = load_calendar()
        html = pass1_generate(custom_post, calendar)
        path = DRAFTS_DIR / f"{custom_post['slug']}.html"
        path.write_text(html, encoding="utf-8")
        print(f"Draft saved: {path}")


if __name__ == "__main__":
    main()
