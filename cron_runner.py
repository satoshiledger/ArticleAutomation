"""
Cron Runner for Railway
=======================
Railway supports cron jobs via separate services. Deploy this as a cron service.

Schedule configuration in Railway dashboard:
  - Blog generation: "0 12 * * 1,3,5"  (Mon/Wed/Fri at 8AM EST = 12 UTC)
  - News monitor:    "0 10 * * *"       (Daily at 6AM EST = 10 UTC)

Usage:
  python cron_runner.py blog      # Generate next scheduled blog post
  python cron_runner.py news      # Run news monitor scan
"""

import sys
import os

# Ensure the blog engine is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blog_engine import run_scheduled_pipeline, run_news_monitor_pipeline


def main():
    if len(sys.argv) < 2:
        print("Usage: python cron_runner.py [blog|news]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "blog":
        print("=" * 60)
        print("CRON: Running scheduled blog generation pipeline")
        print("=" * 60)
        run_scheduled_pipeline()

    elif mode == "news":
        print("=" * 60)
        print("CRON: Running news monitor scan")
        print("=" * 60)
        run_news_monitor_pipeline()

    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python cron_runner.py [blog|news]")
        sys.exit(1)


if __name__ == "__main__":
    main()
