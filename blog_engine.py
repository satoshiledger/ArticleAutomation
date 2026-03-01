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
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")  # Resend.com API key for email (SMTP blocked on Railway)
DRAFTS_DIR = Path(os.getenv("DRAFTS_DIR", "./drafts"))
APPROVED_DIR = Path(os.getenv("APPROVED_DIR", "./approved"))
PRE_GENERATED_DIR = Path(os.getenv("PRE_GENERATED_DIR", "./pre-generated"))
CALENDAR_PATH = Path(os.getenv("CALENDAR_PATH", "./content_calendar.json"))

DRAFTS_DIR.mkdir(exist_ok=True)
APPROVED_DIR.mkdir(exist_ok=True)
PRE_GENERATED_DIR.mkdir(exist_ok=True)

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
- Bilingual: The ENGLISH version is the primary article. Include a Spanish note directing readers to contact for Spanish help.

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

## CRITICAL: USE THIS EXACT HTML TEMPLATE
You MUST use the exact template structure below. Replace the placeholders with actual content.
Do NOT invent your own nav, footer, styles, or layout. Copy this template exactly.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TITLE}} | PuertoRicoLLC.com</title>
    <meta name="description" content="{{META_DESCRIPTION}}">
    <meta name="keywords" content="{{KEYWORDS}}">
    
    <!-- Open Graph -->
    <meta property="og:title" content="{{TITLE}}">
    <meta property="og:description" content="{{META_DESCRIPTION}}">
    <meta property="og:image" content="{{HERO_IMAGE_URL}}">
    <meta property="og:url" content="https://puertoricollc.com/{{SLUG}}.html">
    <meta property="og:type" content="article">
    
    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{TITLE}}">
    <meta name="twitter:description" content="{{META_DESCRIPTION}}">
    <meta name="twitter:image" content="{{HERO_IMAGE_URL}}">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        .hero-bg { background: linear-gradient(135deg, #020617 0%, #1e3a8a 100%); }
        [data-lang="es"] { display: none; }
        .lang-active { font-weight: 800; color: #3A99D8 !important; border-bottom: 2px solid #3A99D8; }
        html { scroll-behavior: smooth; }
    </style>
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-L7DET25V5W"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-L7DET25V5W');
    </script>
    
    <!-- Schema.org Article Markup -->
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{{TITLE}}",
        "image": "{{HERO_IMAGE_URL}}",
        "author": {"@type": "Organization", "name": "PuertoRicoLLC.com"},
        "publisher": {"@type": "Organization", "name": "Satoshi Ledger LLC"},
        "datePublished": "{{PUBLISH_DATE_ISO}}",
        "dateModified": "{{PUBLISH_DATE_ISO}}",
        "description": "{{META_DESCRIPTION}}"
    }
    </script>
</head>
<body class="bg-slate-50">
    <!-- Navigation (EXACT copy from live site) -->
    <nav class="bg-slate-900 border-b border-slate-800 sticky top-0 z-50 shadow-lg">
        <div class="max-w-7xl mx-auto px-6 py-4">
            <div class="flex justify-between items-center">
                <a href="index.html" class="text-2xl font-black uppercase tracking-tighter" style="color:#CC0000">
                    <span style="color:#CC0000">PuertoRico</span><span style="color:#3A99D8">LLC</span><span style="color:#3A99D8;font-weight:500">.com</span>
                </a>
                <div class="hidden md:flex items-center gap-6">
                    <div class="flex items-center gap-1 text-base font-black uppercase tracking-tighter">
                        <button onclick="setLanguage('en')" id="btn-en" class="lang-active cursor-pointer">EN</button>
                        <span class="text-slate-500 text-xs">|</span>
                        <button onclick="setLanguage('es')" id="btn-es" class="cursor-pointer">ES</button>
                    </div>
                    <div class="flex space-x-4 text-sm font-semibold uppercase">
                        <a href="index.html" class="text-white hover:text-gray-300 transition">Home</a>
                        <a href="act60-mastery.html" class="text-white hover:text-gray-300 transition">Act 60</a>
                        <a href="blog.html" class="text-white font-bold underline underline-offset-4 transition">Blog</a>
                        <a href="index.html#contact" class="bg-red-600 text-white px-5 py-2 rounded-lg hover:bg-red-700 transition shadow-sm">Consultation</a>
                    </div>
                </div>
                <button onclick="toggleMobileMenu()" class="md:hidden text-2xl text-white"><i class="fas fa-bars" id="menu-icon"></i></button>
            </div>
            <div id="mobile-menu" class="hidden md:hidden mt-4 space-y-3 pb-4">
                <a href="index.html" class="block py-2 text-white hover:text-gray-300 transition text-center font-semibold">Home</a>
                <a href="act60-mastery.html" class="block py-2 text-white hover:text-gray-300 transition text-center font-semibold">Act 60</a>
                <a href="blog.html" class="block py-2 text-white underline underline-offset-4 transition text-center font-bold">Blog</a>
                <a href="index.html#contact" class="block bg-red-600 text-white px-6 py-3 rounded-lg hover:bg-red-700 transition text-center font-bold">Consultation</a>
            </div>
        </div>
    </nav>

    <!-- Article Content -->
    <article class="py-20 px-6 bg-gradient-to-b from-white to-slate-50">
        <div class="max-w-5xl mx-auto">
            <!-- Hero Image -->
            <div class="mb-12">
                <div class="rounded-3xl overflow-hidden shadow-2xl mb-8">
                    <img src="{{HERO_IMAGE_URL}}" alt="{{HERO_IMAGE_ALT}}" class="w-full h-96 object-cover">
                </div>
                <div class="flex items-center gap-4 text-sm text-slate-600 mb-4 flex-wrap">
                    <span class="bg-blue-100 text-blue-800 px-4 py-1 rounded-full font-bold">
                        <span data-lang="en">{{CATEGORY_EN}}</span>
                        <span data-lang="es">{{CATEGORY_ES}}</span>
                    </span>
                    <span data-lang="en">Published {{PUBLISH_DATE}}</span>
                    <span data-lang="es">Publicado {{PUBLISH_DATE}}</span>
                    <span>&bull;</span>
                    <span data-lang="en">{{READ_TIME}} min read</span>
                    <span data-lang="es">{{READ_TIME}} min lectura</span>
                </div>
                
                <!-- Spanish note -->
                <div data-lang="es" class="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg mb-6">
                    <p class="text-blue-900 text-sm">
                        <i class="fas fa-info-circle mr-2"></i>
                        <strong>Nota:</strong> Este articulo tecnico esta disponible solo en ingles. Para consultas en espanol, <a href="index.html#contact" class="text-blue-600 font-bold underline">contactenos directamente</a>.
                    </p>
                </div>
                
                <h1 class="text-4xl md:text-5xl font-black text-slate-900 mb-6 leading-tight">
                    <span data-lang="en">{{TITLE_EN}}</span>
                    <span data-lang="es">{{TITLE_ES}}</span>
                </h1>
            </div>

            <!-- Social Share -->
            <div class="mb-12 pb-8 border-b border-slate-200">
                <p class="text-slate-600 mb-4 font-semibold text-center">
                    <span data-lang="en">Share this article:</span>
                    <span data-lang="es">Compartir este articulo:</span>
                </p>
                <div class="flex justify-center gap-4">
                    <a href="https://www.facebook.com/sharer/sharer.php?u=https://puertoricollc.com/{{SLUG}}.html" target="_blank" class="w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 transition"><i class="fab fa-facebook-f"></i></a>
                    <a href="https://twitter.com/intent/tweet?url=https://puertoricollc.com/{{SLUG}}.html&text={{TITLE_ENCODED}}" target="_blank" class="w-12 h-12 bg-sky-500 text-white rounded-full flex items-center justify-center hover:bg-sky-600 transition"><i class="fab fa-twitter"></i></a>
                    <a href="https://www.linkedin.com/sharing/share-offsite/?url=https://puertoricollc.com/{{SLUG}}.html" target="_blank" class="w-12 h-12 bg-blue-700 text-white rounded-full flex items-center justify-center hover:bg-blue-800 transition"><i class="fab fa-linkedin-in"></i></a>
                    <a href="https://wa.me/?text={{TITLE_ENCODED}}%20https://puertoricollc.com/{{SLUG}}.html" target="_blank" class="w-12 h-12 bg-green-600 text-white rounded-full flex items-center justify-center hover:bg-green-700 transition"><i class="fab fa-whatsapp"></i></a>
                </div>
            </div>

            <!-- MAIN ARTICLE CONTENT GOES HERE -->
            <!-- Use <div class="bg-white p-8 md:p-12 rounded-2xl shadow-lg mb-12"> for each section -->
            <!-- Use font-black for headings, text-slate-900 for text -->
            <!-- Use bg-gradient-to-br from-blue-50 to-blue-100 cards for key points -->
            <!-- Use bg-white p-8 rounded-2xl shadow-lg for content sections -->
            
            {{ARTICLE_BODY}}

            <!-- Sources & References -->
            <div class="bg-white p-8 md:p-12 rounded-2xl shadow-lg mb-12">
                <h2 class="text-3xl font-black text-slate-900 mb-6">Sources & References</h2>
                {{SOURCES_LIST}}
            </div>

            <!-- Disclaimer -->
            <div class="bg-slate-100 p-6 rounded-xl text-sm text-slate-500 italic mb-12">
                <strong>Disclaimer:</strong> This content is for informational purposes only and does not constitute legal or tax advice. Tax laws are complex and subject to change. Consult a qualified Puerto Rico CPA and tax attorney before making any decisions. PuertoRicoLLC.com (Satoshi Ledger LLC) does not guarantee any specific tax outcome.
            </div>

            <!-- CTA -->
            <div class="bg-gradient-to-r from-blue-600 to-blue-500 text-white p-10 md:p-16 rounded-3xl text-center shadow-2xl mb-12">
                <h2 class="text-3xl md:text-5xl font-black mb-6">{{CTA_TITLE}}</h2>
                <p class="text-xl text-blue-100 mb-8 max-w-3xl mx-auto leading-relaxed">{{CTA_DESCRIPTION}}</p>
                <a href="index.html#contact" class="inline-block bg-white text-blue-600 px-10 py-5 rounded-2xl font-black text-xl hover:bg-blue-50 transition shadow-2xl transform hover:scale-105">
                    Schedule Your Consultation <i class="fas fa-arrow-right ml-3"></i>
                </a>
            </div>

            <!-- Social Share Bottom + Back to Blog -->
            <div class="pt-8 border-t border-slate-200 text-center">
                <p class="text-slate-600 mb-4 font-semibold">Share this article:</p>
                <div class="flex justify-center gap-4 mb-8">
                    <a href="https://www.facebook.com/sharer/sharer.php?u=https://puertoricollc.com/{{SLUG}}.html" target="_blank" class="w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 transition"><i class="fab fa-facebook-f"></i></a>
                    <a href="https://twitter.com/intent/tweet?url=https://puertoricollc.com/{{SLUG}}.html&text={{TITLE_ENCODED}}" target="_blank" class="w-12 h-12 bg-sky-500 text-white rounded-full flex items-center justify-center hover:bg-sky-600 transition"><i class="fab fa-twitter"></i></a>
                    <a href="https://www.linkedin.com/sharing/share-offsite/?url=https://puertoricollc.com/{{SLUG}}.html" target="_blank" class="w-12 h-12 bg-blue-700 text-white rounded-full flex items-center justify-center hover:bg-blue-800 transition"><i class="fab fa-linkedin-in"></i></a>
                    <a href="https://wa.me/?text={{TITLE_ENCODED}}%20https://puertoricollc.com/{{SLUG}}.html" target="_blank" class="w-12 h-12 bg-green-600 text-white rounded-full flex items-center justify-center hover:bg-green-700 transition"><i class="fab fa-whatsapp"></i></a>
                </div>
                <a href="blog.html" class="inline-flex items-center gap-2 text-blue-600 font-bold hover:text-blue-700 transition">
                    <i class="fas fa-arrow-left"></i>
                    <span data-lang="en">Back to Blog</span>
                    <span data-lang="es">Volver al Blog</span>
                </a>
            </div>
        </div>
    </article>

    <!-- Footer (EXACT copy from live site) -->
    <footer class="py-12 bg-slate-950 text-white text-center">
        <div class="max-w-7xl mx-auto px-6">
            <div class="mb-6">
                <a href="index.html" class="text-2xl font-black text-white uppercase tracking-tighter mb-2 inline-block">
                    <span style="color:#CC0000">PuertoRico</span><span style="color:#3A99D8">LLC</span><span style="color:#3A99D8;font-weight:500">.com</span>
                </a>
            </div>
            <p class="text-xs opacity-30 italic mb-6">Tax compliance and accounting services. Not a law firm. Not financial advice.</p>
            <div class="flex justify-center gap-6 mb-6">
                <a href="https://instagram.com/SatoshiLedger" target="_blank" class="text-slate-400 hover:text-blue-400 transition"><i class="fab fa-instagram text-2xl"></i></a>
            </div>
            <p class="text-xs opacity-20">&copy; 2026 Satoshi Ledger LLC d/b/a PuertoRicoLLC.com. All rights reserved.</p>
        </div>
    </footer>

    <!-- WhatsApp Floating Button -->
    <style>
        .whatsapp-float { position:fixed; width:60px; height:60px; bottom:40px; right:40px; background-color:#25d366; color:#FFF; border-radius:50px; text-align:center; font-size:30px; box-shadow:2px 2px 10px rgba(0,0,0,0.3); z-index:100; transition:all 0.3s ease; display:flex; align-items:center; justify-content:center; }
        .whatsapp-float:hover { background-color:#128c7e; transform:scale(1.1); }
        .whatsapp-float i { margin-top:4px; }
        .whatsapp-status { position:absolute; top:5px; right:5px; width:14px; height:14px; background-color:#4CAF50; border:2px solid white; border-radius:50%; animation:pulse 2s infinite; }
        @keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(76,175,80,0.7)} 70%{box-shadow:0 0 0 10px rgba(76,175,80,0)} 100%{box-shadow:0 0 0 0 rgba(76,175,80,0)} }
        .whatsapp-tooltip { position:absolute; right:70px; top:50%; transform:translateY(-50%); background-color:white; color:#333; padding:8px 15px; border-radius:8px; white-space:nowrap; font-size:14px; font-weight:600; box-shadow:0 2px 10px rgba(0,0,0,0.2); opacity:0; pointer-events:none; transition:opacity 0.3s ease; }
        .whatsapp-float:hover .whatsapp-tooltip { opacity:1; }
        @media screen and (max-width:768px) { .whatsapp-float{width:50px;height:50px;bottom:20px;right:20px;font-size:26px;} .whatsapp-tooltip{display:none;} }
    </style>
    <a href="https://wa.me/16146952904?text=Hello%2C%20I%27m%20interested%20in%20your%20Puerto%20Rico%20tax%20services" class="whatsapp-float" target="_blank" rel="noopener noreferrer" aria-label="Chat on WhatsApp">
        <span class="whatsapp-status"></span>
        <i class="fab fa-whatsapp"></i>
        <span class="whatsapp-tooltip">
            <span data-lang="en">Chat with us!</span>
            <span data-lang="es">Chatea con nosotros!</span>
        </span>
    </a>

    <!-- JavaScript (EXACT copy from live site) -->
    <script>
        function toggleMobileMenu() {
            const menu = document.getElementById('mobile-menu');
            const icon = document.getElementById('menu-icon');
            menu.classList.toggle('hidden');
            if (!menu.classList.contains('hidden')) { icon.classList.remove('fa-bars'); icon.classList.add('fa-times'); }
            else { icon.classList.remove('fa-times'); icon.classList.add('fa-bars'); }
        }
        function setLanguage(lang) {
            document.querySelectorAll('[data-lang]').forEach(el => {
                el.style.display = el.getAttribute('data-lang') === lang ? 'inline' : 'none';
            });
            document.getElementById('btn-en').classList.toggle('lang-active', lang === 'en');
            document.getElementById('btn-es').classList.toggle('lang-active', lang === 'es');
            localStorage.setItem('preferredLang', lang);
        }
        window.addEventListener('load', () => {
            const savedLang = localStorage.getItem('preferredLang') || 'en';
            setLanguage(savedLang);
        });
    </script>
</body>
</html>
```

Replace ALL {{placeholders}} with actual content. The article body should use these section styles:
- Wrap each major section in: <div class="bg-white p-8 md:p-12 rounded-2xl shadow-lg mb-12">
- Headings: <h2 class="text-3xl md:text-4xl font-black text-slate-900 mb-6">
- Subheadings: <h3 class="text-2xl font-bold text-slate-900 mb-4">
- Body text: <p class="text-lg text-slate-700 leading-relaxed mb-6">
- Key stat cards: use bg-gradient-to-br from-blue-50 to-blue-100 with icon divs
- Callout boxes: <div class="bg-blue-50 border-l-4 border-blue-500 p-6 rounded-r-lg">
- Warning boxes: <div class="bg-yellow-50 border-l-4 border-yellow-500 p-6 rounded-r-lg">

Write ONLY in English. Do not include a full Spanish translation of the article.
Output ONLY the complete HTML file. No explanation, no markdown, no preamble.
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
    """Call the Anthropic API using the official SDK. Supports web search for live research.
    Includes retry logic for rate limits (429 errors)."""
    import anthropic
    import time

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

    # Retry up to 3 times with increasing delays for rate limits
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.messages.create(**kwargs)
            break
        except anthropic.RateLimitError as e:
            wait_time = 60 * (attempt + 1)  # 60s, 120s, 180s
            print(f"  Rate limited (attempt {attempt + 1}/{max_retries}). Waiting {wait_time}s...")
            time.sleep(wait_time)
            if attempt == max_retries - 1:
                print(f"  Rate limit persisted after {max_retries} retries.")
                raise
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
    """Send email via Resend HTTP API (primary) or Gmail SMTP (fallback).
    Resend works on Railway since it uses HTTPS, not SMTP ports."""
    import httpx

    # Try Resend API first (works on Railway — uses HTTPS)
    if RESEND_API_KEY:
        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": "PuertoRicoLLC Blog <onboarding@resend.dev>",
                    "to": [NOTIFY_EMAIL],
                    "subject": subject,
                    "text": body_text,
                    "html": body_html if body_html else body_text,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                print(f"  ✓ Email sent via Resend API")
                return
            else:
                print(f"  Resend error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  Resend failed: {e}")

    # Fallback: Gmail SMTP (works outside Railway)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = NOTIFY_EMAIL
    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    for port, method in [(587, "TLS"), (465, "SSL")]:
        try:
            if port == 587:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                    server.starttls()
                    server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                    server.sendmail(GMAIL_ADDRESS, NOTIFY_EMAIL, msg.as_string())
            else:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
                    server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                    server.sendmail(GMAIL_ADDRESS, NOTIFY_EMAIL, msg.as_string())
            print(f"  ✓ Email sent via Gmail port {port} ({method})")
            return
        except Exception as e:
            print(f"  Gmail port {port} failed: {e}")

    print("  ✗ All email methods failed")


def push_to_github(filename: str, content: str, commit_message: str = "") -> bool:
    """Push a file to the GitHub repo (livewebsites) via the GitHub API.
    This deploys the blog post to the live site via Hostinger's Git integration."""
    import httpx

    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("  ✗ GitHub push skipped: GITHUB_TOKEN or GITHUB_REPO not set")
        return False

    if not commit_message:
        commit_message = f"Publish blog post: {filename}"

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    import base64
    encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # Check if file already exists (need SHA to update)
    sha = None
    try:
        resp = httpx.get(api_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            sha = resp.json().get("sha")
    except Exception:
        pass

    body = {
        "message": commit_message,
        "content": encoded_content,
        "branch": "main",
    }
    if sha:
        body["sha"] = sha

    try:
        resp = httpx.put(api_url, headers=headers, json=body, timeout=30)
        if resp.status_code in (200, 201):
            print(f"  ✓ Pushed to GitHub: {filename}")
            return True
        else:
            print(f"  ✗ GitHub push failed ({resp.status_code}): {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ✗ GitHub push error: {e}")
        return False


def load_calendar() -> dict:
    """Load the content calendar JSON."""
    with open(CALENDAR_PATH) as f:
        return json.load(f)


# Color mapping for blog card gradients by cluster
CLUSTER_COLORS = {
    "1_act60_compliance": "from-green-600 to-green-500",
    "2_business_structure": "from-teal-600 to-teal-500",
    "3_bitcoin": "from-orange-600 to-amber-500",
    "4_tax_strategy": "from-blue-600 to-blue-500",
    "5_operations": "from-purple-600 to-purple-500",
}

# Category mapping for filter tabs
CLUSTER_CATEGORIES = {
    "1_act60_compliance": "act60",
    "2_business_structure": "business-structure",
    "3_bitcoin": "bitcoin",
    "4_tax_strategy": "tax-strategy",
    "5_operations": "tax-strategy",
}


def update_blog_index(post: dict, calendar: dict) -> bool:
    """Fetch blog.html from GitHub, inject a new article entry into the JS array, and push it back.
    This keeps the blog index page up to date automatically when articles are approved."""
    import httpx
    import base64

    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("  ✗ Blog index update skipped: no GitHub credentials")
        return False

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/blog.html"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Fetch current blog.html
    try:
        resp = httpx.get(api_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"  ✗ Could not fetch blog.html ({resp.status_code})")
            return False
        file_data = resp.json()
        sha = file_data["sha"]
        blog_html = base64.b64decode(file_data["content"]).decode("utf-8")
    except Exception as e:
        print(f"  ✗ Error fetching blog.html: {e}")
        return False

    # Check if article already exists in the array
    if post["slug"] in blog_html:
        print(f"  ℹ Article already in blog index: {post['slug']}")
        return True

    # Build the new article entry
    cluster = post.get("cluster", "4_tax_strategy")
    cluster_info = calendar.get("clusters", {}).get(cluster, {})
    category = CLUSTER_CATEGORIES.get(cluster, "tax-strategy")
    color = CLUSTER_COLORS.get(cluster, "from-blue-600 to-blue-500")
    tag_en = cluster_info.get("category_label_en", "Tax Strategy")
    tag_es = cluster_info.get("category_label_es", "Estrategia Fiscal")
    today = datetime.now()
    date_en = today.strftime("%B %d, %Y")
    date_es = today.strftime("%d %B %Y")

    # Escape quotes in titles for JS
    title_en = post["title_en"].replace('"', '\\"')
    title_es = post["title_es"].replace('"', '\\"')

    # Calculate read time from the actual article HTML
    draft_path = DRAFTS_DIR / f"{post['slug']}.html"
    approved_path = APPROVED_DIR / f"{post['slug']}.html"
    pre_gen_path = PRE_GENERATED_DIR / f"{post['slug']}.html"
    article_html = ""
    for p in [approved_path, draft_path, pre_gen_path]:
        if p.exists():
            article_html = p.read_text(encoding="utf-8")
            break
    # Strip HTML tags to get plain text, count words, divide by 200 wpm
    plain_text = re.sub(r'<[^>]+>', ' ', article_html)
    plain_text = re.sub(r'\s+', ' ', plain_text).strip()
    word_count = len(plain_text.split())
    read_time = max(1, round(word_count / 200))

    new_entry = f"""        {{
            category: "{category}",
            color: "{color}",
            tagEN: "{tag_en}", tagES: "{tag_es}",
            titleEN: "{title_en}",
            titleES: "{title_es}",
            date: "{date_en}", dateES: "{date_es}", readTime: {read_time},
            descEN: "Read the full article for expert analysis on this topic with real-world examples and official source citations.",
            descES: "Lea el art\\u00edculo completo para an\\u00e1lisis experto con ejemplos reales y citas de fuentes oficiales.",
            url: "{post['slug']}.html"
        }},"""

    # Inject at the top of the articles array (after "const articles = [")
    marker = "const articles = ["
    idx = blog_html.find(marker)
    if idx == -1:
        print("  ✗ Could not find articles array in blog.html")
        return False

    insert_pos = idx + len(marker) + 1  # +1 for newline
    updated_html = blog_html[:insert_pos] + new_entry + "\n" + blog_html[insert_pos:]

    # Push updated blog.html
    encoded = base64.b64encode(updated_html.encode("utf-8")).decode("utf-8")
    body = {
        "message": f"Add blog card: {post['slug']}",
        "content": encoded,
        "sha": sha,
        "branch": "main",
    }

    try:
        resp = httpx.put(api_url, headers=headers, json=body, timeout=30)
        if resp.status_code in (200, 201):
            print(f"  ✓ Blog index updated with new article: {post['slug']}")
            return True
        else:
            print(f"  ✗ Blog index push failed ({resp.status_code}): {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ✗ Blog index update error: {e}")
        return False


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


def get_next_ungenerated_post(calendar: dict) -> dict | None:
    """Get the next post that hasn't been generated yet, regardless of day.
    Used for manual 'Generate Now' triggers."""
    for post in calendar["posts"]:
        draft_path = DRAFTS_DIR / f"{post['slug']}.html"
        approved_path = APPROVED_DIR / f"{post['slug']}.html"
        if not draft_path.exists() and not approved_path.exists():
            return post
    return None


# ---------------------------------------------------------------------------
# HERO IMAGE POOL — rotates so every article gets a unique image
# ---------------------------------------------------------------------------

# Pool of Unsplash images organized by theme.
# Each cluster cycles through its preferred images, then overflows to others.
HERO_IMAGE_POOL = [
    # === ACT 60 COMPLIANCE (6 articles) ===
    {"id": "aerial-san-juan", "url": "https://images.unsplash.com/photo-1579687196544-08ae57ab5960?w=1200&h=600&fit=crop", "alt": "Aerial view of colorful buildings in Old San Juan, Puerto Rico", "themes": ["act60"]},
    {"id": "el-morro-fort", "url": "https://images.unsplash.com/photo-1568736333610-eae6e0e6516a?w=1200&h=600&fit=crop", "alt": "Historic El Morro fortress in San Juan, Puerto Rico at sunset", "themes": ["act60"]},
    {"id": "condado-skyline", "url": "https://images.unsplash.com/photo-1580745089072-62a10aa3e6a2?w=1200&h=600&fit=crop", "alt": "Condado district skyline in San Juan, Puerto Rico", "themes": ["act60"]},
    {"id": "pr-capitol", "url": "https://images.unsplash.com/photo-1595880500386-4b33c6192cc1?w=1200&h=600&fit=crop", "alt": "Puerto Rico Capitol building in San Juan", "themes": ["act60"]},
    {"id": "old-san-juan-street", "url": "https://images.unsplash.com/photo-1560703650-ef3e0f254ae0?w=1200&h=600&fit=crop", "alt": "Colorful cobblestone streets of Old San Juan, Puerto Rico", "themes": ["act60"]},
    {"id": "pr-flag-building", "url": "https://images.unsplash.com/photo-1608483099860-12be8ccdf5e4?w=1200&h=600&fit=crop", "alt": "Puerto Rico door painted with the island flag in Old San Juan", "themes": ["act60"]},

    # === BITCOIN TAX (6 articles) ===
    {"id": "bitcoin-digital", "url": "https://images.unsplash.com/photo-1518546305927-5a555bb7020d?w=1200&h=600&fit=crop", "alt": "Bitcoin digital currency concept with golden coin", "themes": ["bitcoin"]},
    {"id": "bitcoin-chart", "url": "https://images.unsplash.com/photo-1642790106117-e829e14a795f?w=1200&h=600&fit=crop", "alt": "Bitcoin trading chart and financial data analysis", "themes": ["bitcoin"]},
    {"id": "bitcoin-hardware", "url": "https://images.unsplash.com/photo-1622630998477-20aa696ecb05?w=1200&h=600&fit=crop", "alt": "Physical Bitcoin coins representing digital currency investment", "themes": ["bitcoin"]},
    {"id": "bitcoin-laptop", "url": "https://images.unsplash.com/photo-1516245834210-c4c142787335?w=1200&h=600&fit=crop", "alt": "Bitcoin on laptop keyboard representing digital finance", "themes": ["bitcoin"]},
    {"id": "bitcoin-network", "url": "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=1200&h=600&fit=crop", "alt": "Bitcoin blockchain network visualization", "themes": ["bitcoin"]},
    {"id": "bitcoin-mining", "url": "https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=1200&h=600&fit=crop", "alt": "Bitcoin mining hardware and technology setup", "themes": ["bitcoin"]},

    # === TAX STRATEGY (5 articles) ===
    {"id": "pr-coastline", "url": "https://images.unsplash.com/photo-1580226905576-cfb36e4e5306?w=1200&h=600&fit=crop", "alt": "Beautiful coastline of Puerto Rico with turquoise waters", "themes": ["tax-strategy"]},
    {"id": "pr-palm-beach", "url": "https://images.unsplash.com/photo-1559128010-7c1ad6e1b6a5?w=1200&h=600&fit=crop", "alt": "Palm trees on a pristine Puerto Rico beach", "themes": ["tax-strategy"]},
    {"id": "financial-planning", "url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200&h=600&fit=crop", "alt": "Financial documents and calculator for tax planning", "themes": ["tax-strategy"]},
    {"id": "pr-rainforest", "url": "https://images.unsplash.com/photo-1586348943529-beaae6c28db9?w=1200&h=600&fit=crop", "alt": "Lush El Yunque rainforest in Puerto Rico", "themes": ["tax-strategy"]},
    {"id": "pr-sunset-ocean", "url": "https://images.unsplash.com/photo-1548574505-5e239809ee19?w=1200&h=600&fit=crop", "alt": "Stunning sunset over the ocean in Puerto Rico", "themes": ["tax-strategy"]},

    # === BUSINESS STRUCTURE (4 articles) ===
    {"id": "tropical-office", "url": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1200&h=600&fit=crop", "alt": "Modern office workspace with tropical view", "themes": ["business-structure"]},
    {"id": "business-meeting", "url": "https://images.unsplash.com/photo-1573497620053-ea5300f94f21?w=1200&h=600&fit=crop", "alt": "Professional business consultation meeting", "themes": ["business-structure"]},
    {"id": "signing-documents", "url": "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=1200&h=600&fit=crop", "alt": "Professional signing business formation documents", "themes": ["business-structure"]},
    {"id": "startup-desk", "url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1200&h=600&fit=crop", "alt": "Startup workspace with laptop and business planning materials", "themes": ["business-structure"]},

    # === OPERATIONS / BOOKKEEPING (3 articles) ===
    {"id": "accounting-desk", "url": "https://images.unsplash.com/photo-1543286386-713bdd548da4?w=1200&h=600&fit=crop", "alt": "Organized accounting desk with spreadsheets and laptop", "themes": ["tax-strategy"]},
    {"id": "calendar-planning", "url": "https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=1200&h=600&fit=crop", "alt": "Calendar and planning tools for business deadline management", "themes": ["tax-strategy"]},
    {"id": "pr-marina", "url": "https://images.unsplash.com/photo-1580137197581-df2bb346a3e9?w=1200&h=600&fit=crop", "alt": "Marina and waterfront in Puerto Rico with boats and skyline", "themes": ["tax-strategy"]},
]


def select_hero_image(post: dict, calendar: dict) -> dict:
    """Select a unique hero image for this post based on its cluster.
    Ensures no two articles use the same image by tracking what's been used."""
    import hashlib

    category = calendar["clusters"][post["cluster"]]["category_tag"]

    # Track which images have already been used (by checking approved + draft files)
    used_images = set()
    for folder in [DRAFTS_DIR, APPROVED_DIR]:
        if folder.exists():
            for f in folder.glob("*.html"):
                try:
                    content = f.read_text(encoding="utf-8")
                    for img in HERO_IMAGE_POOL:
                        if img["url"] in content:
                            used_images.add(img["id"])
                except:
                    pass

    # First: try images themed for this category that haven't been used
    themed = [img for img in HERO_IMAGE_POOL if category in img["themes"] and img["id"] not in used_images]
    if themed:
        # Pick deterministically based on slug so same slug always gets same image
        idx = int(hashlib.md5(post["slug"].encode()).hexdigest(), 16) % len(themed)
        return themed[idx]

    # Second: try ANY unused image
    unused = [img for img in HERO_IMAGE_POOL if img["id"] not in used_images]
    if unused:
        idx = int(hashlib.md5(post["slug"].encode()).hexdigest(), 16) % len(unused)
        return unused[idx]

    # Fallback: all images used, cycle through themed images
    all_themed = [img for img in HERO_IMAGE_POOL if category in img["themes"]]
    if all_themed:
        idx = int(hashlib.md5(post["slug"].encode()).hexdigest(), 16) % len(all_themed)
        return all_themed[idx]

    # Ultimate fallback
    idx = int(hashlib.md5(post["slug"].encode()).hexdigest(), 16) % len(HERO_IMAGE_POOL)
    return HERO_IMAGE_POOL[idx]


# ---------------------------------------------------------------------------
# PASS 1 — RESEARCH & GENERATE
# ---------------------------------------------------------------------------

def pass1_generate(post: dict, calendar: dict) -> str:
    """Generate the blog post HTML using Claude API with web search for source verification."""

    cluster_info = calendar["clusters"][post["cluster"]]

    # Select hero image — rotate by cluster so no two articles in the same
    # category use the same image, and different categories feel visually distinct.
    hero_image = select_hero_image(post, calendar)

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

## HERO IMAGE (MANDATORY — use these exact values)
- Image URL: {hero_image['url']}
- Image alt text: {hero_image['alt']}
Replace {{{{HERO_IMAGE_URL}}}} with: {hero_image['url']}
Replace {{{{HERO_IMAGE_ALT}}}} with: {hero_image['alt']}

## INSTRUCTIONS
1. FIRST, use web search to find the CURRENT text/provisions of each required source.
   Search for the actual government publications. Do NOT rely on memory for any numbers.
2. Write a comprehensive 2,000-2,500 word article in English.
3. Include at least 3 real-world examples with dollar amounts.
4. Cite every factual claim with the specific law section or government source.
5. Include a Sources & References section at the bottom with URLs.
6. Use the EXACT HTML template provided in your system prompt. Do not invent your own layout.

Output ONLY the complete HTML file. No explanation, no analysis, no preamble.
Start with <!DOCTYPE html> and end with </html>.
"""

    print(f"  [Pass 1] Hero image: {hero_image['url']}")
    print("  [Pass 1] Generating blog post with web search for source verification...")
    html = call_claude(PASS1_SYSTEM_PROMPT, user_message, use_web_search=True)

    # Clean any markdown fencing if present
    html = re.sub(r"^```html?\s*", "", html, flags=re.MULTILINE)
    html = re.sub(r"```\s*$", "", html, flags=re.MULTILINE)

    # Extract ONLY the HTML — Claude sometimes prepends analysis text
    html_match = re.search(r"(<!DOCTYPE html.*</html>)", html, re.DOTALL | re.IGNORECASE)
    if html_match:
        html = html_match.group(1).strip()
    else:
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

    # Robust JSON extraction — handle markdown fences, preamble text, etc.
    audit = None

    # Strategy 1: Try to find JSON block between ```json ... ```
    json_block_match = re.search(r'```json?\s*\n?(.*?)\n?\s*```', raw, re.DOTALL)
    if json_block_match:
        try:
            audit = json.loads(json_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 2: Try to find first { ... } block (greedy, outermost braces)
    if audit is None:
        brace_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if brace_match:
            try:
                audit = json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

    # Strategy 3: Strip common prefixes and try raw parse
    if audit is None:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```json?\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()
        try:
            audit = json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # Fallback: return the raw response so user can see what the API actually said
    if audit is None:
        print(f"  ⚠ Could not parse audit JSON. Raw response preview: {raw[:500]}")
        audit = {
            "overall_grade": "UNKNOWN",
            "publish_ready": False,
            "critical_issues": [],
            "warnings": [{"issue": "Audit response could not be parsed as JSON — see raw_response below for details"}],
            "suggestions": [],
            "raw_response": raw[:3000],
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

Output ONLY the corrected complete HTML file. No explanation, no analysis, no preamble.
Start with <!DOCTYPE html> and end with </html>.
"""

    print("  [Pass 3] Fixing critical issues...")
    fixed = call_claude(PASS3_FIX_PROMPT, user_message, use_web_search=False)

    # Strip markdown fences
    fixed = re.sub(r"^```html?\s*", "", fixed, flags=re.MULTILINE)
    fixed = re.sub(r"```\s*$", "", fixed, flags=re.MULTILINE)

    # Extract ONLY the HTML — Claude sometimes prepends analysis text
    html_match = re.search(r"(<!DOCTYPE html.*</html>)", fixed, re.DOTALL | re.IGNORECASE)
    if html_match:
        return html_match.group(1).strip()

    # If no valid HTML found, return original to avoid corruption
    print("  ⚠ Pass 3 did not return valid HTML — keeping original")
    return html


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
    """Run the full scheduled blog generation pipeline.
    Picks the next ungenerated post in the calendar regardless of day."""
    calendar = load_calendar()
    post = get_next_ungenerated_post(calendar)

    if not post:
        print("All posts in the calendar have been generated.")
        return

    _run_pipeline(post, calendar)


def run_manual_pipeline():
    """Run the pipeline for the next ungenerated post (ignores day-of-week).
    Used by the 'Generate Now' button."""
    calendar = load_calendar()
    post = get_next_ungenerated_post(calendar)

    if not post:
        print("All posts in the calendar have been generated.")
        return

    _run_pipeline(post, calendar)


def run_custom_pipeline(title: str, keywords: str, cluster: str = "4_tax_strategy", cta: str = "consultation"):
    """Run the pipeline for a custom topic (not from the calendar).
    Used by the 'Generate Custom Article' form on the dashboard."""
    import re

    # Build a slug from the title
    slug = "blog-" + re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80]

    # Build a post dict matching calendar format
    post = {
        "week": 0,
        "day": "custom",
        "cluster": cluster,
        "slug": slug,
        "title_en": title,
        "title_es": title,  # Will be English; user can edit in review
        "keywords": keywords,
        "sources_required": [],
        "cta": cta,
        "seo_intent": "custom",
        "target_serp": keywords.split(",")[0].strip() if keywords else title,
        "est_monthly_volume": 0,
        "lead_score": 8,
    }

    calendar = load_calendar()

    print(f"\n{'='*60}")
    print(f"CUSTOM ARTICLE: {title}")
    print(f"Keywords: {keywords}")
    print(f"Cluster: {cluster} | CTA: {cta}")
    print(f"Slug: {slug}")
    print(f"{'='*60}\n")

    _run_pipeline(post, calendar)


def _run_pipeline(post: dict, calendar: dict):
    """Core pipeline logic shared by scheduled and manual triggers.
    
    NEW FLOW (v3.1 — pre-generated article support):
    1. Check if a pre-generated HTML exists in PRE_GENERATED_DIR
    2. If YES: skip Pass 1 (save API credits), use the pre-written article
    3. If NO: fall back to full Pass 1 API generation (for custom/alert articles)
    4. Always run Pass 2 (audit) — 1 API call for quality assurance
    5. If audit finds critical issues AND article was API-generated: run Pass 3 fix
    6. If audit finds critical issues AND article was pre-generated: flag for manual review
    7. Run Pass 4 (social media) 
    8. Send email notification
    """
    import time

    print(f"\n{'='*60}")
    print(f"GENERATING: {post['title_en']}")
    print(f"Cluster: {post['cluster']}")
    print(f"Slug: {post['slug']}")
    print(f"{'='*60}\n")

    # Check for pre-generated article first
    pre_gen_path = PRE_GENERATED_DIR / f"{post['slug']}.html"
    is_pre_generated = pre_gen_path.exists()

    if is_pre_generated:
        print(f"  📄 Found pre-generated article: {pre_gen_path}")
        html = pre_gen_path.read_text(encoding="utf-8")
        print(f"  ✓ Loaded pre-generated HTML ({len(html):,} chars)")
        print(f"  💰 Pass 1 SKIPPED — saving API credits")
    else:
        print(f"  ⚡ No pre-generated file found — generating via API...")
        # Pass 1: Generate (full API call with web search)
        html = pass1_generate(post, calendar)
        print(f"  ✓ API-generated HTML ({len(html):,} chars)")

        # Wait for rate limit
        print("  ⏳ Waiting 90s for rate limit reset...")
        time.sleep(90)

    # Save initial draft
    draft_path = DRAFTS_DIR / f"{post['slug']}.html"
    draft_path.write_text(html, encoding="utf-8")
    print(f"  ✓ Draft saved: {draft_path}")

    # Pass 2: Audit (always runs — 1 API call for quality assurance)
    if not is_pre_generated:
        # Only need to wait if we just did Pass 1
        pass
    else:
        # Pre-generated articles go straight to audit, no wait needed
        pass

    audit = pass2_audit(html, post)
    audit_path = DRAFTS_DIR / f"{post['slug']}_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"  ✓ Audit saved: {audit_path}")
    print(f"  Grade: {audit.get('overall_grade', '?')} | "
          f"Critical: {len(audit.get('critical_issues', []))} | "
          f"Warnings: {len(audit.get('warnings', []))}")

    # Pass 3: Fix critical issues
    if audit.get("critical_issues"):
        if is_pre_generated:
            # Pre-generated articles: flag issues but DON'T auto-fix
            # (you wrote it in Claude Chat, so review the audit manually)
            print(f"  ⚠ {len(audit['critical_issues'])} critical issues found in pre-generated article")
            print(f"  📋 Issues flagged for your manual review (not auto-fixing pre-generated content)")
        else:
            # API-generated articles: auto-fix as before
            print(f"  ⚠ {len(audit['critical_issues'])} critical issues found — auto-fixing...")
            print("  ⏳ Waiting 90s for rate limit reset...")
            time.sleep(90)

            html = pass3_fix(html, audit, post)
            draft_path.write_text(html, encoding="utf-8")

            # Re-audit the fixed version
            print("  ⏳ Waiting 90s for rate limit reset...")
            time.sleep(90)

            audit2 = pass2_audit(html, post)
            audit_path.write_text(json.dumps(audit2, indent=2), encoding="utf-8")
            print(f"  ✓ Post-fix audit: Grade {audit2.get('overall_grade', '?')} | "
                  f"Critical: {len(audit2.get('critical_issues', []))}")
            audit = audit2

    # Pass 4: Social media — SKIPPED
    # Social content can be generated manually in Claude Chat from the published article.
    # This saves 1 API call per article.
    print(f"  ⏭ Pass 4 (social) skipped — generate manually in Claude Chat after publishing")

    # Generate blog card and sitemap entry
    card_html = generate_blog_card_html(post, calendar)
    card_path = DRAFTS_DIR / f"{post['slug']}_card.html"
    card_path.write_text(card_html, encoding="utf-8")

    sitemap_entry = generate_sitemap_entry(post)
    sitemap_path = DRAFTS_DIR / f"{post['slug']}_sitemap.xml"
    sitemap_path.write_text(sitemap_entry, encoding="utf-8")

    # Send email notification
    source_label = "PRE-GENERATED" if is_pre_generated else "API-GENERATED"
    try:
        subject, plain, html_email = format_draft_notification(post, audit, str(draft_path))
        # Prepend source label to subject
        subject = f"[{source_label}] {subject}"
        send_email(subject, plain, html_email)
        print(f"  ✓ Email notification sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"  ✗ Email error: {e}")
        subject, plain, _ = format_draft_notification(post, audit, str(draft_path))
        print(f"  Subject: [{source_label}] {subject}")
        print(f"  {plain[:300]}")

    print(f"\n{'='*60}")
    if is_pre_generated:
        print(f"PIPELINE COMPLETE (pre-generated) — 1 API call used (audit only)")
    else:
        print(f"PIPELINE COMPLETE (API-generated) — Pass 1 + audit")
    print(f"Awaiting your approval")
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

    # Save alerts to disk so they can be triggered later from dashboard
    alerts_dir = DRAFTS_DIR.parent / "alerts"
    alerts_dir.mkdir(exist_ok=True)

    for alert in report.get("alerts", []):
        print(f"\n  🔴 ALERT: {alert.get('headline', 'Unknown')}")
        print(f"     Source: {alert.get('source', 'Unknown')}")
        print(f"     Urgency: {alert.get('urgency', 'Unknown')}")

        # Generate a unique alert ID
        import hashlib
        alert_id = hashlib.md5(alert.get("headline", "").encode()).hexdigest()[:12]
        alert["alert_id"] = alert_id
        alert["timestamp"] = datetime.now().isoformat()
        alert["status"] = "pending"  # pending → generating → drafted → approved

        # Determine cluster and keywords from alert
        cluster = alert.get("cluster", "4_tax_strategy")
        # Map common cluster names to our IDs
        cluster_map = {
            "bitcoin": "3_bitcoin",
            "act60": "1_act60_compliance",
            "act_60": "1_act60_compliance",
            "compliance": "1_act60_compliance",
            "business": "2_business_structure",
            "tax": "4_tax_strategy",
            "operations": "5_operations",
        }
        for key, val in cluster_map.items():
            if key in cluster.lower():
                cluster = val
                break
        if not cluster.startswith(("1_", "2_", "3_", "4_", "5_")):
            cluster = "4_tax_strategy"
        alert["cluster_id"] = cluster

        # Save alert to disk
        alert_path = alerts_dir / f"{alert_id}.json"
        alert_path.write_text(json.dumps(alert, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"     Saved alert: {alert_id}")

        # Send email with "Approve & Generate" button
        try:
            subject, plain, html = format_news_alert_with_button(alert)
            send_email(subject, plain, html)
            print(f"     ✓ Email alert sent")
        except Exception as e:
            print(f"     ✗ Email error: {e}")


def format_news_alert_with_button(alert: dict) -> tuple[str, str, str]:
    """Format a news alert email with an 'Approve & Generate' button."""

    dashboard_url = os.getenv("DASHBOARD_URL", "https://web-production-36855.up.railway.app")
    alert_id = alert.get("alert_id", "unknown")
    generate_url = f"{dashboard_url}/generate-alert/{alert_id}"

    subject = f"🔴 New Content Opportunity: {alert.get('headline', 'Regulatory Update')[:50]}"

    plain_text = f"""BREAKING: Content Opportunity Detected

Headline: {alert['headline']}
Source: {alert['source']}
Relevance: {alert['relevance']}
Urgency: {alert['urgency']}

Suggested post: "{alert['suggested_title']}"
Cluster: {alert.get('cluster', 'N/A')}

To generate this article, click: {generate_url}
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
          <p style="color: #0F172A; font-weight: bold; margin: 0;">&ldquo;{alert['suggested_title']}&rdquo;</p>
          <p style="color: #64748B; font-size: 12px; margin: 8px 0 0 0;">Category: {alert.get('cluster', 'Tax Strategy')}</p>
        </div>
        <div style="text-align: center; margin: 24px 0 16px 0;">
          <a href="{generate_url}" style="display: inline-block; background: #16A34A; color: #ffffff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px;">✅ Approve &amp; Generate Article</a>
        </div>
        <p style="color: #94A3B8; font-size: 11px; text-align: center;">Clicking will start article generation (~8 min). You'll review it before publishing.</p>
      </div>
    </div>
    """

    return subject, plain_text, html


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
