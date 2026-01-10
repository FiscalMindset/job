# Getting Started - Job Intelligence OS

## 🎯 What You've Built

A **production-ready, autonomous job application system** that:
- ✅ Scrapes jobs from multiple sources (LinkedIn, YC, Wellfound)
- ✅ Makes intelligent decisions (APPLY/APPLY_LATER/WATCH/SKIP)
- ✅ Sends personalized emails automatically
- ✅ Runs unattended via cron
- ✅ Maintains full audit trail
- ✅ Survives failures gracefully

## 🚀 Quick Start (5 Minutes)

### 1. Install Ollama

```bash
# You already have llama3.1:8b installed
ollama list  # Should show llama3.1:8b

# If not running, start it
ollama serve
```

### 2. Install Python Dependencies

```bash
cd /Users/viclkykumar/Library/CloudStorage/GoogleDrive-vickyiitbombay2@gmail.com/My\ Drive/job_agentic

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install
pip install -e .
```

### 3. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit with your details
nano .env
```

**Minimum required:**
```bash
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
YOUR_NAME=Your Name
YOUR_SKILLS=Python,JavaScript,AWS  # Your actual skills
TARGET_ROLES=Software Engineer,Backend Engineer
```

### 4. Verify Setup

```bash
# Check configuration
python cli.py config-check

# Should output: "Configuration is valid!"
```

### 5. Test Run (No Emails)

```bash
# Dry run - no emails sent
python cli.py run --dry-run
```

**Expected output:**
```
Job Intelligence OS
Mode: DRY RUN
Sources: all

linkedin: Collected 25 jobs
ycombinator: Collected 15 jobs
wellfound: Collected 20 jobs

After deduplication: 60 new jobs
Enriched 60 jobs
Scored 60 jobs

Decisions:
  APPLY: 5
  APPLY_LATER: 12
  WATCH: 18
  SKIP: 25

[DRY RUN] Would send email to jobs@stripe.com for Stripe
[DRY RUN] Would send email to hiring@linear.app for Linear
...

Pipeline completed in 45.2s
```

### 6. Real Run (Start Small)

```bash
# Run with just one source first
python cli.py run --sources ycombinator

# Check sent emails in your Gmail
```

## 📊 CLI Commands

### Run Pipeline
```bash
# All sources
python cli.py run --sources all

# Specific sources
python cli.py run --sources linkedin,ycombinator

# Dry run (testing)
python cli.py run --dry-run
```

### Check Status
```bash
# Last 7 days summary
python cli.py status

# Last 30 days statistics
python cli.py stats --last 30d
```

### Audit Decisions
```bash
# All decisions
python cli.py audit

# Only APPLY decisions
python cli.py audit --decision APPLY

# Limited to 10 results
python cli.py audit --limit 10
```

### Configuration
```bash
# Verify configuration
python cli.py config-check
```

## 📁 File Structure

```
job_agentic/
├── core/                    # Orchestration engine
│   ├── engine.py           # Main pipeline
│   ├── models.py           # Data models
│   └── state.py            # State management
│
├── collectors/              # Job scrapers
│   ├── base.py             # Base collector
│   ├── linkedin.py         # LinkedIn scraper
│   ├── ycombinator.py      # Y Combinator
│   └── wellfound.py        # Wellfound (AngelList)
│
├── intelligence/            # Decision engine
│   ├── scorer.py           # Rule-based scoring
│   ├── llm.py              # Ollama integration
│   └── decider.py          # Final decisions
│
├── enrichment/              # Data enrichment
│   └── email_finder.py     # Find contact emails
│
├── outreach/                # Email system
│   ├── composer.py         # Email templates
│   └── sender.py           # SMTP sending
│
├── storage/                 # Persistence
│   ├── csv_store.py        # Primary CSV storage
│   └── sqlite_store.py     # Queryable database
│
├── observability/           # Monitoring
│   ├── logger.py           # Structured logging
│   ├── metrics.py          # Performance tracking
│   └── circuit_breaker.py  # Fault tolerance
│
├── cli.py                   # CLI interface
├── config.py               # Configuration
├── main.py                 # Entry point
│
└── docs/
    ├── README.md           # Overview
    ├── SETUP.md            # Detailed setup
    ├── ARCHITECTURE.md     # System design
    ├── DEPLOYMENT.md       # Production deployment
    └── PROMPTS.md          # LLM prompt guide
```

## 🔧 Configuration Guide

### Essential Settings (.env)

```bash
# ===== YOUR PROFILE =====
YOUR_NAME=John Doe
YOUR_TITLE=Senior Backend Engineer
YOUR_SKILLS=Python,Go,PostgreSQL,Redis,Kubernetes,AWS
YOUR_EXPERIENCE_YEARS=7
YOUR_LOCATION=San Francisco, CA
YOUR_LINKEDIN=https://linkedin.com/in/johndoe
YOUR_GITHUB=https://github.com/johndoe

# ===== JOB PREFERENCES =====
TARGET_ROLES=Backend Engineer,Platform Engineer,Senior Software Engineer
PREFERRED_COMPANY_STAGES=seed,series-a,series-b
PREFERRED_LOCATIONS=San Francisco,Remote,New York
MIN_SALARY=150000

# ===== DECISION THRESHOLDS =====
APPLY_THRESHOLD=75         # Score >= 75 → APPLY
APPLY_LATER_THRESHOLD=50   # Score >= 50 → APPLY_LATER
WATCH_THRESHOLD=30         # Score >= 30 → WATCH

# ===== RATE LIMITS =====
MAX_EMAILS_PER_DAY=20      # Don't spam
MAX_EMAILS_PER_HOUR=5      # Appear human
EMAIL_DELAY_SECONDS=60     # Wait between emails
```

## 📈 Monitoring

### View Logs
```bash
# Follow live logs
tail -f logs/jobctl.log

# Recent errors
grep ERROR logs/jobctl.log | tail -20

# Last 100 lines
tail -n 100 logs/jobctl.log
```

### Check Data
```bash
# View CSV
cat data/jobs.csv | head -20

# Count jobs
wc -l data/jobs.csv

# Search for company
grep -i stripe data/jobs.csv
```

### View Backups
```bash
ls -lh data/backups/
```

## ⏰ Schedule Daily Runs

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 9 AM)
0 9 * * * cd /Users/viclkykumar/Library/CloudStorage/GoogleDrive-vickyiitbombay2@gmail.com/My\ Drive/job_agentic && /Users/viclkykumar/Library/CloudStorage/GoogleDrive-vickyiitbombay2@gmail.com/My\ Drive/job_agentic/venv/bin/python /Users/viclkykumar/Library/CloudStorage/GoogleDrive-vickyiitbombay2@gmail.com/My\ Drive/job_agentic/cli.py run --sources all >> /var/log/jobctl.log 2>&1
```

**Verify cron:**
```bash
crontab -l  # List scheduled jobs
```

## 🎯 Tuning the System

### If Too Many APPLY Decisions

Increase threshold:
```bash
APPLY_THRESHOLD=85  # Was 75
```

### If Too Few APPLY Decisions

Decrease threshold:
```bash
APPLY_THRESHOLD=65  # Was 75
```

### If Emails Too Generic

Enable LLM personalization (it's already enabled).
LLM will make emails more specific to each company.

### If System Too Slow

Disable slow collectors:
```bash
ENABLED_COLLECTORS=ycombinator,wellfound  # Skip LinkedIn
```

Or disable Playwright:
```bash
ENABLE_PLAYWRIGHT=false
```

## 🔍 Inspecting Decisions

### View APPLY Decisions
```bash
python cli.py audit --decision APPLY
```

Output:
```
Company         Role                    Decision  Score  Reason
Stripe          Backend Engineer        APPLY     85     Role matches 'backend engineer'; 6 skills match; Posted within 3 days
Linear          Full Stack Engineer     APPLY     78     Role matches; 5 skills match; Company stage: seed
```

### View SKIP Decisions
```bash
python cli.py audit --decision SKIP --limit 10
```

### Search Specific Company
```bash
grep -i "stripe" data/jobs.csv
```

## 📧 Email Troubleshooting

### Gmail App Password Setup

1. Go to https://myaccount.google.com/apppasswords
2. Sign in
3. Select "Mail" and your device
4. Click "Generate"
5. Copy 16-character password
6. Paste in .env as `SMTP_PASSWORD`

### Test Email Sending

```bash
# Send to just YC jobs (usually < 5)
python cli.py run --sources ycombinator

# Check sent emails in Gmail
```

### Rate Limit Hit

If you see "Rate limit exceeded":
- Check `MAX_EMAILS_PER_HOUR` and `MAX_EMAILS_PER_DAY` in .env
- Current: 5/hour, 20/day
- Increase if needed (but stay reasonable)

## 🐛 Common Issues

### "Ollama connection failed"

```bash
# Start Ollama
ollama serve

# In another terminal, verify
ollama list
curl http://localhost:11434/api/tags
```

### "No jobs collected"

- Check internet connection
- Check collector logs: `tail -f logs/jobctl.log`
- Try one source at a time: `python cli.py run --sources ycombinator`
- Some sources may block scrapers

### "Configuration errors"

```bash
# Run validation
python cli.py config-check

# Fix errors shown, then re-run
```

### "SMTP authentication failed"

- Use Gmail **app password**, not regular password
- Enable 2FA first
- Regenerate app password

## 📚 Documentation

- **[README.md](README.md)** - System overview
- **[SETUP.md](SETUP.md)** - Detailed setup guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design and philosophy
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment
- **[PROMPTS.md](PROMPTS.md)** - LLM prompt engineering

## 🎓 Next Steps

### Week 1: Testing
1. ✅ Run dry-run mode
2. ✅ Send 5-10 test emails
3. ✅ Review sent emails
4. ✅ Adjust scoring thresholds

### Week 2: Automation
5. ✅ Schedule cron job
6. ✅ Monitor for errors
7. ✅ Fine-tune rate limits
8. ✅ Review decisions daily

### Week 3: Optimization
9. ✅ Add more collectors if needed
10. ✅ Adjust scoring weights
11. ✅ Customize email templates
12. ✅ Track application outcomes

### Month 2: Production
13. ✅ Let it run autonomously
14. ✅ Check weekly stats
15. ✅ Respond to interviews
16. ✅ Refine based on results

## 🎉 Success Metrics

After 1 month, you should have:
- ✅ 500-1000 jobs collected
- ✅ 50-100 APPLY decisions
- ✅ 20-60 emails sent
- ✅ 5-15 responses
- ✅ 1-3 interviews

## 🚨 Important Notes

### DO:
- ✅ Start with dry-run
- ✅ Test with small batches first
- ✅ Monitor sent emails
- ✅ Keep rate limits reasonable
- ✅ Review decisions regularly

### DON'T:
- ❌ Send 100 emails/day
- ❌ Use generic templates
- ❌ Skip dry-run testing
- ❌ Ignore error logs
- ❌ Set thresholds too low

## 💡 Tips

1. **Start conservative** - Higher thresholds, fewer emails
2. **Review decisions** - Use `audit` command regularly
3. **Customize templates** - Edit `outreach/composer.py`
4. **Track outcomes** - Note which emails get responses
5. **Iterate** - Adjust scoring based on results

## 🔗 Quick Links

```bash
# Verify setup
python cli.py config-check

# Test run
python cli.py run --dry-run

# Real run (one source)
python cli.py run --sources ycombinator

# Check status
python cli.py status

# View decisions
python cli.py audit --decision APPLY

# View logs
tail -f logs/jobctl.log
```

## ✅ Pre-Launch Checklist

- [ ] Ollama running (`ollama list`)
- [ ] .env configured
- [ ] Dry run successful
- [ ] Config check passes
- [ ] Test email sent
- [ ] Sent email reviewed
- [ ] Rate limits set appropriately
- [ ] Scoring thresholds tuned
- [ ] Ready to schedule cron

## 🎯 You're Ready!

The system is **production-ready** and built to run **autonomously**.

Start with dry-run, send a few test emails, then let it run.

**Good luck with your job search! 🚀**
