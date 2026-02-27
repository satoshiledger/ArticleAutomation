# Blog Engine Setup Guide
### PuertoRicoLLC.com | Satoshi Ledger LLC
### Automated Content Pipeline — Step by Step

---

## What You're Building

A system that automatically generates A++ quality blog posts 3x per week, verifies every claim against official government sources, emails you the draft for review, lets you edit it in a web dashboard, and publishes it to your live site when you hit "Approve."

**Total setup time: ~60 minutes**
**Total monthly cost: ~$15-20** (Claude API + Railway)

---

## Prerequisites Checklist

Before starting, make sure you have:

- [ ] **Anthropic account** — console.anthropic.com (you already have this)
- [ ] **Gmail account** — for sending notification emails (you already have this)
- [ ] **GitHub account** — github.com (you already have this)
- [ ] **Railway account** — railway.app (sign up with GitHub, takes 30 seconds)
- [ ] **Hostinger access** — your existing hosting (already have this)

---

## Phase 1: Get Your API Keys Ready (15 minutes)

### Step 1: Claude API Key

1. Go to **console.anthropic.com**
2. Click **Settings** → **API Keys**
3. Click **Create Key**
4. Name it: `blog-engine`
5. Copy the key (starts with `sk-ant-`)
6. Save it somewhere safe — you can't see it again

> 💡 **Cost:** About $8-12/month for 12 blog posts with 4-pass quality checks

### Step 2: Gmail App Password

This is NOT your regular Gmail password. It's a special 16-character password that lets the script send emails through your Gmail.

1. Go to **myaccount.google.com**
2. Click **Security** (left sidebar)
3. Make sure **2-Step Verification** is turned ON (if it's not, turn it on first)
4. After 2-Step Verification is on, go to **myaccount.google.com/apppasswords**
5. At the bottom, under "App name", type: `Blog Engine`
6. Click **Create**
7. Google shows you a **16-character password** (looks like: `abcd efgh ijkl mnop`)
8. Copy it and save it — you won't see it again

> ⚠️ **Important:** If you don't see the "App passwords" option, it means 2-Step Verification is not turned on. Turn it on first, then come back.

### Step 3: GitHub Personal Access Token

This lets the script push approved blog posts to your website repo.

1. Go to **github.com/settings/tokens**
2. Click **Generate new token** → **Fine-grained token**
3. Name it: `blog-engine-deploy`
4. Expiration: **90 days** (set a calendar reminder to renew)
5. Under **Repository access**, select **Only select repositories** → pick your website repo
6. Under **Permissions** → **Repository permissions**:
   - **Contents**: Read and write
   - Everything else: No access
7. Click **Generate token**
8. Copy the token (starts with `github_pat_` or `ghp_`)

---

## Phase 2: Push the Code to GitHub (10 minutes)

### Step 4: Create the Blog Engine Repository

1. Go to **github.com/new**
2. Repository name: `puertoricollc-blog-engine`
3. Set to **Private**
4. Do NOT check "Add a README" (we already have one)
5. Click **Create repository**

### Step 5: Upload the Files

**Option A — If you're comfortable with Terminal/Command Line:**

```bash
# Create a folder and put all the downloaded files in it
mkdir puertoricollc-blog-engine
cd puertoricollc-blog-engine

# Copy all the files here (blog_engine.py, dashboard.py, etc.)

# Initialize and push
git init
git add .
git commit -m "Initial blog engine setup"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/puertoricollc-blog-engine.git
git push -u origin main
```

**Option B — If you prefer the browser (easier):**

1. Go to your new repo on GitHub
2. Click **uploading an existing file** (the link on the empty repo page)
3. Drag and drop ALL the files: `blog_engine.py`, `dashboard.py`, `content_calendar.json`, `cron_runner.py`, `requirements.txt`, `Procfile`, `railway.json`, `.env.example`, `README.md`
4. Click **Commit changes**

### Step 6: Verify

Refresh your repo page. You should see 9 files listed. If yes, move on.

---

## Phase 3: Deploy to Railway (20 minutes)

Railway will host 3 things: your review dashboard, the blog generation cron job, and the news monitor cron job.

### Step 7: Create the Dashboard Service

1. Go to **railway.app/dashboard**
2. Click **New Project**
3. Click **Deploy from GitHub repo**
4. Select your `puertoricollc-blog-engine` repository
5. Railway auto-detects Python and starts building
6. Wait for the build to finish (1-2 minutes)
7. Once deployed, Railway assigns a URL like: `your-app-production.up.railway.app`
8. Click that URL — you should see the Blog Engine Dashboard page

> 💡 **Write down this URL.** This is where you'll review and approve posts.

### Step 8: Create the Blog Generation Cron Service

1. In the SAME Railway project, click **+ New** → **Service**
2. Select **GitHub Repo** → pick `puertoricollc-blog-engine` again
3. Once it deploys, click on the service name to open settings
4. Go to the **Settings** tab
5. Under **Deploy** → **Start Command**, change it to:
   ```
   python cron_runner.py blog
   ```
6. Under **Deploy** → **Cron Schedule**, enter:
   ```
   0 12 * * 1,3,5
   ```
   This means: Run at 12:00 UTC (8:00 AM Eastern) every Monday, Wednesday, Friday
7. Rename this service to `blog-cron` (click the service name at the top)

### Step 9: Create the News Monitor Cron Service

1. Same process: **+ New** → **Service** → **GitHub Repo** → same repo
2. **Start Command:**
   ```
   python cron_runner.py news
   ```
3. **Cron Schedule:**
   ```
   0 10 * * *
   ```
   This means: Run daily at 10:00 UTC (6:00 AM Eastern)
4. Rename this service to `news-monitor`

> ✅ You should now have **3 services** in your Railway project: the dashboard (web), blog-cron, and news-monitor.

---

## Phase 4: Set Environment Variables (10 minutes)

These tell all 3 services how to connect to Claude, Gmail, and GitHub.

### Step 10: Add Shared Variables

1. In your Railway project, click the **project name** at the very top
2. Go to **Variables** tab
3. Click **New Variable** and add each of these:

| Variable | Value | Notes |
|----------|-------|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-your-key` | From Step 1 |
| `GMAIL_ADDRESS` | `your-email@gmail.com` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | `abcd efgh ijkl mnop` | From Step 2 (the 16-char code) |
| `NOTIFY_EMAIL` | `your-email@gmail.com` | Where to receive notifications (can be same or different) |
| `GITHUB_REPO` | `your-username/puertoricollc.com` | Your WEBSITE repo (not the blog engine repo) |
| `GITHUB_TOKEN` | `ghp_xxxxx` | From Step 3 |
| `DASHBOARD_URL` | `https://your-app.up.railway.app` | Your Railway dashboard URL from Step 7 |

### Step 11: Link Variables to Each Service

> ⚠️ **This step is critical — don't skip it!**

1. Click on your **dashboard** service
2. Go to its **Variables** tab
3. Click **Add Reference** → select each shared variable → **Add**
4. Repeat for the **blog-cron** service
5. Repeat for the **news-monitor** service

All 3 services will now redeploy with the variables injected.

---

## Phase 5: Connect Hostinger Auto-Deploy (5 minutes)

### Step 12: Verify Git Integration

1. Log into **Hostinger hPanel**
2. Go to **Advanced** → **Git**
3. Verify your website repo is connected and pulls from the `main` branch
4. If not connected: click **Create** and link your website GitHub repo
5. Set the directory to `public_html`

### Step 13: Test the Deploy

1. Make a tiny change to any file in your website GitHub repo (add a comment to `index.html`)
2. Commit and push to `main`
3. Wait 1-2 minutes
4. Check puertoricollc.com — if the change is live, auto-deploy works

> 💡 If Hostinger doesn't auto-pull from GitHub, you can manually click "Pull" in the Git section, or set up a GitHub Actions workflow to FTP files to Hostinger.

---

## Phase 6: Your First Test Run (5 minutes)

### Step 14: Trigger a Manual Run

1. In Railway, click on your **blog-cron** service
2. Go to **Deployments** tab
3. Click the **three dots menu** on the latest deployment → **Restart**
4. Or if Railway supports manual cron triggers: click **Trigger**
5. Watch the **Logs** in real time

You should see output like:

```
============================================================
GENERATING: The 183-Day Residency Myth: What the IRS Actually Tests
Cluster: 1_act60_compliance
============================================================

  [Pass 1] Generating blog post with web search for source verification...
  ✓ Draft saved: ./drafts/blog-183-day-residency-myth.html
  [Pass 2] Running adversarial fact-check audit...
  ✓ Audit saved. Grade: A | Critical: 0 | Warnings: 2
  [Pass 4] Generating social media derivatives...
  ✓ Email notification sent

PIPELINE COMPLETE — awaiting your approval
```

### Step 15: Check Your Email

You'll receive an email with:

- The blog post title
- Audit grade and issue counts
- Warning details
- A direct link to the review dashboard

### Step 16: Review, Edit, Approve

1. Click the link in the email → opens your Railway dashboard
2. You see a **split view**: HTML editor on the left, live preview on the right
3. Audit warnings are shown at the top — check each one
4. Edit the HTML directly if you want to fix wording, change a number, add a personal touch
5. The preview updates live as you type
6. When you're happy, click **✅ Approve & Publish**
7. The post gets pushed to your website repo → Hostinger picks it up → live on puertoricollc.com

---

## Your Weekly Routine

Once everything is set up, this is your workflow:

### Monday / Wednesday / Friday

| Time | What Happens |
|------|-------------|
| 8:00 AM | Email arrives with new blog draft + audit results |
| 8:01 AM | You tap the dashboard link, skim the preview |
| 8:03 AM | Check the 2-3 audit warnings, edit if needed |
| 8:05 AM | Hit Approve. Post goes live. |
| 8:06 AM | Grab the LinkedIn post from the Social tab, paste into LinkedIn |

**Total time per post: 5-10 minutes.**

### Every Morning

| Time | What Happens |
|------|-------------|
| 6:00 AM | News monitor silently scans government sources |
| — | If nothing found → no email, no interruption |
| — | If new IRS notice, Hacienda circular, or legislation detected → email alert |
| — | You decide whether to generate a reactive blog post about it |

---

## Monthly Cost Breakdown

| Service | Cost | Notes |
|---------|------|-------|
| Claude API (blog generation) | $8-12 | 12 posts × 4 passes each |
| Claude API (news monitor) | $3-5 | Daily government scans |
| Railway (3 services) | $5-7 | Hobby plan |
| Gmail | Free | App password, no API needed |
| GitHub | Free | Private repo |
| Hostinger | Already paying | No additional cost |
| **TOTAL** | **~$17-25/month** | **Well under your $200 API budget** |

---

## Troubleshooting

**Email not arriving?**
→ Check Railway logs for the blog-cron service. Look for "Email error" messages.
→ Verify your Gmail App Password is correct (not your regular password).
→ Check your spam/junk folder. Add your Gmail address to contacts to prevent this.
→ Test: In Railway, manually restart the blog-cron service and watch the logs.

**Railway build failing?**
→ Check deploy logs. Most common issue: missing `requirements.txt`.
→ Make sure all 9 files are in the repo root (not in a subfolder).
→ Railway uses Python 3.11+ by default — our code is compatible.

**Blog post quality not high enough?**
→ Edit the system prompts in `blog_engine.py` (lines ~55-175).
→ Add more examples of your writing style.
→ Add specific instructions about common mistakes to avoid.
→ The more specific you are in the prompt, the better the output.

**Audit keeps finding critical issues?**
→ This means the system is working. The audit is deliberately aggressive.
→ Pass 3 auto-fixes critical issues before sending you the draft.
→ If the same type of error keeps coming up, add a rule to the generation prompt to prevent it.

**Want to change the posting schedule?**
→ In Railway, click blog-cron → Settings → Cron Schedule
→ Use [crontab.guru](https://crontab.guru) to build the expression
→ Examples:
  - `0 12 * * 1,3,5` = Mon/Wed/Fri at 8AM EST
  - `0 12 * * 1,4` = Mon/Thu at 8AM EST
  - `0 14 * * 2,5` = Tue/Fri at 10AM EST

**Want to add more topics to the calendar?**
→ Edit `content_calendar.json` and add new entries to the `posts` array.
→ Follow the same format as existing entries.
→ Commit and push to GitHub — Railway auto-deploys the update.

---

## Need Help?

WhatsApp: +1 (614) 695-2904 | @SatoshiLedger

© 2026 Satoshi Ledger LLC d/b/a PuertoRicoLLC.com
