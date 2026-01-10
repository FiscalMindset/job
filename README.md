# 🚀 Job Intelligence Operating System

**A production-ready, autonomous job application automation system powered by AI.**

[![Demo](https://img.shields.io/badge/▶️_Watch-Demo-red?style=for-the-badge&logo=youtube)](https://youtu.be/DP0ZvabylzM)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)](https://python.org)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-green?style=flat-square)](https://ollama.ai)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

## 📺 Demo

**Watch the system in action:**

[![Job Intelligence OS Demo](https://img.youtube.com/vi/DP0ZvabylzM/maxresdefault.jpg)](https://youtu.be/DP0ZvabylzM)

👉 [**Click to watch the full demo video**](https://youtu.be/DP0ZvabylzM) - See how the system collects jobs from LinkedIn, GitHub, Naukri, YCombinator, and Wellfound, scores them with AI, and generates personalized outreach emails.

## ✨ What This Is

- 🤖 **Fully Autonomous** - Backend automation system (no UI, no manual intervention)
- ⏰ **Runs Unattended** - Schedule via cron for daily/weekly execution
- 🧠 **AI-Powered Decisions** - APPLY / APPLY_LATER / WATCH / SKIP with reasoning
- 📧 **Personalized Outreach** - Auto-generates tailored emails for each job
- 🛡️ **Production-Grade** - Survives failures, maintains state, produces audit logs
- 📊 **Beautiful Terminal UI** - Rich progress bars, tables, and analytics

## 🚫 What This Is NOT

- ❌ Not an agent framework experiment
- ❌ Not a demo or prototype
- ❌ Not dependent on paid APIs (100% local LLM)
- ❌ Not a spam machine (intelligent filtering + rate limiting)

## 🏗️ Architecture Principles

1. **Rule-based first, LLM second** - Fast, deterministic logic before expensive inference
2. **Idempotent by design** - Same input → same output, safe to re-run
3. **Fail gracefully** - One broken source doesn't crash the pipeline
4. **Auditable** - Every decision has a reason, every action is logged
5. **Modular** - Each component is testable, replaceable, inspectable

## 🔄 System Flow

```
📥 Collect → 🧹 Clean → 🔍 Dedupe → 🎯 Enrich → 📊 Score → 🧠 Decide → 📧 Outreach → 💾 Store
```

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.11+ | Core runtime |
| **LLM** | Ollama (llama3.1:8b) | Local AI inference (no API costs) |
| **Storage** | CSV + SQLite | Primary + queryable storage |
| **Scraping** | httpx, BeautifulSoup, Playwright | Job data collection |
| **Email** | SMTP (Gmail) | Automated outreach |
| **Terminal UI** | Rich library | Beautiful CLI experience |
| **CLI** | Typer | Command-line interface |
| **Scheduler** | cron | Automated execution |

## 🎯 Key Features

### Multi-Source Job Collection
- **LinkedIn** - Scrapes new grad & early career positions
- **GitHub** - Careers page + repos with hiring in README + issues
- **Naukri.com** - India's largest job portal
- **YCombinator** - Startup job board
- **Wellfound (AngelList)** - Startup hiring platform

### Deep Profile Analysis
- **GitHub Analysis** - Analyzes all 92 repositories with AI insights
- **LinkedIn Scraping** - Uses Playwright for dynamic content
- **Auto-send Hiring Alerts** - Detects hiring posts and emails immediately
- **CSV Export** - Complete job data export for analysis

### Intelligent Decision Making
- **Rule-based Scoring** - Fast filtering based on experience, tech stack, location
- **AI Reasoning** - Uses Ollama for complex job description analysis
- **Match Scoring** - 0-100% compatibility score with detailed reasoning
- **Smart Decisions** - APPLY (75+), APPLY_LATER (50-74), WATCH (30-49), SKIP (<30)

### Beautiful Terminal Reports
- **All Jobs List** - Complete table with company, role, location, score, decision
- **Company Breakdown** - Top 15 companies with job counts and percentages
- **Location Analysis** - Top 10 locations with visual bars
- **Skills Analysis** - Most in-demand (top 15) and least common (bottom 10) skills
- **Score Distribution** - Excellent/Good/Fair/Poor ranges with counts
- **Summary Statistics** - Average score, remote jobs, email found, unique companies

### Enhanced Email Notifications
- **Job Cards with URLs** - Every job shows clickable "Apply Now" button
- **AI Reasoning** - "Why you should apply" for each position
- **Match Scores** - Color-coded badges (high/medium/low)
- **Visual Design** - Professional HTML email with gradient headers
- **Organized Sections** - APPLY jobs first, then other decisions

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/algsoch/job_agentic.git
cd job_agentic

# 2. Install Ollama and pull the model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b

# 3. Install Python dependencies
pip install -e .

# 4. Configure environment (create .env file)
cp .env.example .env
# Edit .env with your settings:
# - SMTP credentials (Gmail app password)
# - GitHub token (for 5000 requests/hour)
# - Job search preferences
# - Enabled collectors (linkedin,github,naukri,ycombinator,wellfound)

# 5. Dry run (no emails sent)
python3 cli.py run --dry-run

# 6. Real run (all sources)
python3 cli.py run

# 7. Check CSV output
cat jobs.csv

# 8. View detailed terminal report
# (automatically shown after pipeline completion)
```

## 📁 Directory Structure

```
job_agentic/
├── 🎯 core/              # Orchestration & state machine
│   ├── engine.py         # Main pipeline orchestrator
│   ├── models.py         # Data models (Job, Decision, PipelineResult)
│   └── state.py          # State management & persistence
├── 🌐 collectors/        # Job scrapers (one per source)
│   ├── base.py           # Abstract collector interface
│   ├── linkedin.py       # LinkedIn job scraper
│   ├── github.py         # GitHub careers + repos + issues
│   ├── naukri.py         # Naukri.com (India) scraper
│   ├── ycombinator.py    # YC job board
│   └── wellfound.py      # Wellfound/AngelList jobs
├── 🧠 intelligence/      # Decision engine
│   ├── rules.py          # Rule-based scoring logic
│   ├── scorer.py         # Job compatibility scoring
│   └── decider.py        # Final decision maker (APPLY/SKIP/etc)
├── 🎨 enrichment/        # Data enrichment & analysis
│   ├── email_finder.py   # Email discovery via Hunter.io/Clearbit
│   ├── profile_report.py # Deep GitHub + LinkedIn analysis
│   └── company_research.py # Company data enrichment
├── 📧 outreach/          # Email automation system
│   ├── composer.py       # Email template & personalization
│   ├── sender.py         # SMTP sending with rate limits
│   └── templates/        # Email templates (HTML/text)
├── 💾 storage/           # Persistence layer
│   ├── csv_store.py      # Primary CSV storage
│   ├── sqlite_store.py   # Queryable SQL database
│   └── backup.py         # Automated daily backups
├── 📊 observability/     # Monitoring & debugging
│   ├── logger.py         # Structured logging
│   ├── metrics.py        # Statistics tracking
│   ├── notifier.py       # Email notifications (completion/errors)
│   └── circuit_breaker.py # Failure protection
├── cli.py                # Typer CLI interface + Rich UI
├── config.py             # Configuration management
├── requirements.txt      # Python dependencies
└── .env.example          # Environment variables template
```

## 📊 Data Model

Each job record contains:

| Field | Type | Description |
|-------|------|-------------|
| **job_id** | str | Unique hash (prevents duplicates) |
| **company** | str | Company name |
| **role** | str | Job title |
| **source** | str | Collection source (linkedin, github, etc) |
| **job_url** | str | Application link |
| **description** | str | Job description text |
| **location** | str | Job location |
| **salary_min/max** | int | Salary range (if available) |
| **email** | str | Hiring manager email |
| **email_confidence** | float | Email validity score (0-1) |
| **score** | int | Match score (0-100) |
| **decision** | Decision | APPLY/APPLY_LATER/WATCH/SKIP |
| **reason** | str | AI-generated reasoning |
| **status** | JobStatus | NEW/ENRICHED/DECIDED/SENT |
| **applied_on** | datetime | Application timestamp |
| **scraped_at** | datetime | Collection timestamp |
| **updated_at** | datetime | Last update timestamp |

## 🧠 Decision Logic

### 1. Rule-Based Scoring (Fast ⚡)
```python
score = 0
+ 30 points  # Experience match (0-3 years)
+ 20 points  # Tech stack match (Python, React, FastAPI, etc)
+ 15 points  # Location match (Bengaluru, Remote, etc)
+ 10 points  # Company stage match
+ 15 points  # Posted recently (within 7 days)
= Total Score (0-100)
```

### 2. LLM Reasoning (When Needed 🤖)
- Ambiguous job descriptions → AI analysis
- Cultural fit assessment → Sentiment analysis
- Email personalization → Context-aware writing
- Profile matching → Deep skill comparison

### 3. Final Decision Tree
```
Score >= 75    → ✅ APPLY         (Send email immediately)
Score 50-74    → ⏰ APPLY_LATER   (Review manually first)
Score 30-49    → 👀 WATCH         (Monitor for changes)
Score < 30     → ⏭️ SKIP          (Not a good match)
```

## 🛡️ Reliability Features

| Feature | Implementation | Benefit |
|---------|---------------|---------|
| **Idempotency** | Job hash (MD5 of company+role+url) | No duplicate applications |
| **Circuit Breakers** | Pause failing sources after 3 errors | Prevent cascade failures |
| **Retry Logic** | Exponential backoff (1s, 2s, 4s, 8s) | Handle transient errors |
| **Partial Failures** | Continue pipeline if one step fails | Maximize job collection |
| **Daily Backups** | Automated CSV snapshots to `backups/` | Data loss prevention |
| **Rate Limiting** | Max 10 emails/hour (Gmail limits) | Avoid spam filters |
| **Error Logging** | Structured logs with traceback | Easy debugging |

## ⏰ Cron Automation

### Daily Job Search (Recommended)
```bash
# Run daily at 9 AM
0 9 * * * cd /path/to/job_agentic && /path/to/venv/bin/python3 cli.py run >> /var/log/jobctl.log 2>&1
```

### Weekly Analytics Report
```bash
# Weekly summary (Sundays at 10 AM)
0 10 * * 0 cd /path/to/job_agentic && /path/to/venv/bin/python3 cli.py stats --last 7d
```

### Hourly Profile Updates
```bash
# Update GitHub/LinkedIn profile every 6 hours
0 */6 * * * cd /path/to/job_agentic && /path/to/venv/bin/python3 cli.py analyze-profile
```

## ✅ Production Checklist

Before running in production, ensure:

- [ ] **Ollama Installed** - `ollama list` shows `llama3.1:8b`
- [ ] **Gmail App Password** - Created and added to `.env`
- [ ] **GitHub Token** - Personal access token for 5000 requests/hour
- [ ] **Environment Variables** - `.env` file configured with all settings
- [ ] **Playwright Browser** - `playwright install chromium` (for LinkedIn)
- [ ] **Test Run Completed** - `python3 cli.py run --dry-run` (no errors)
- [ ] **Email Sending Tested** - Verify emails reach inbox (not spam)
- [ ] **Cron Job Scheduled** - Automated daily execution configured
- [ ] **Log Rotation Configured** - Prevent disk space issues
- [ ] **Backup Location Verified** - `backups/` directory accessible
- [ ] **Resume File Present** - `resume.pdf` in project root

## 📈 Monitoring & Analytics

### Terminal Report (Auto-generated)
After each run, the system displays:
- **All Jobs Table** - Complete list with scores and decisions
- **Company Breakdown** - Top 15 hiring companies with percentages
- **Location Analysis** - Top 10 locations with visual distribution
- **Skills Demand** - Most/least in-demand technologies
- **Score Distribution** - Job quality breakdown (Excellent/Good/Fair/Poor)
- **Summary Stats** - Avg score, remote jobs, unique companies

### Key Metrics to Track
```python
jobs_scraped_per_source     # Collection efficiency
decision_distribution       # APPLY/SKIP ratio
email_send_success_rate     # Outreach effectiveness
source_failure_rate         # Scraper health
pipeline_execution_time     # Performance monitoring
```

### Log Files
- `logs/jobctl.log` - Main application log
- `logs/errors.log` - Error-only log
- `logs/email_sent.log` - Outreach audit trail

## 🔧 Configuration

### Environment Variables (.env)
```bash
# SMTP Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
EMAIL_FROM_NAME=Your Name

# GitHub API (for 5000 requests/hour)
GITHUB_TOKEN=ghp_your_personal_access_token

# Job Search Preferences
TARGET_ROLES=Software Engineer,Backend Engineer,AI Engineer
TARGET_LOCATIONS=Remote,Bengaluru,San Francisco
MIN_EXPERIENCE=0
MAX_EXPERIENCE=3
REQUIRED_SKILLS=Python,FastAPI,React,LangChain

# Enabled Collectors (comma-separated)
ENABLED_COLLECTORS=linkedin,github,naukri,ycombinator,wellfound

# Profile Information
YOUR_NAME=Vicky Kumar
YOUR_GITHUB=https://github.com/algsoch
YOUR_LINKEDIN=https://www.linkedin.com/in/algsoch/
YOUR_PORTFOLIO=https://ai-engineer-chatbot.onrender.com/
RESUME_PATH=./resume.pdf
```

## 🎨 Sample Output

### Pipeline Execution
```
╭─────────────────────────────────────────╮
│  🚀 JOB INTELLIGENCE OPERATING SYSTEM  │
│     Autonomous Job Application Agent    │
╰─────────────────────────────────────────╯

🔍 COLLECTING JOBS FROM ALL SOURCES

┌─ LinkedIn Collector ─────────────────┐
│ Found 35 jobs from LinkedIn         │
│ ✓ Software Engineering, New Grad    │
│ ✓ Backend Engineer - Early Career   │
│ ✓ Full Stack Developer (0-2 years) │
└──────────────────────────────────────┘

┌─ GitHub Collector ───────────────────┐
│ ✓ Scraping GitHub Careers Page      │
│ ✓ Searching repos with hiring       │
│ ✓ Searching GitHub issues            │
│ Found 12 jobs from GitHub            │
└──────────────────────────────────────┘

📊 Pipeline Complete in 69.1s

╭─ RESULTS ─────────────────────────╮
│ Jobs Collected:      35           │
│ Emails Sent:         0            │
│ Decisions Made:                   │
│   ✅ APPLY:          15           │
│   ⏭️ SKIP:           20           │
│ Success Rate:        42.9%        │
╰───────────────────────────────────╯

📋 ALL JOBS FOUND (35 total)

┌───┬─────────────┬──────────────────────────┬────────────┬──────┬──────────┐
│ # │ Company     │ Role                     │ Location   │ Score│ Decision │
├───┼─────────────┼──────────────────────────┼────────────┼──────┼──────────┤
│ 1 │ Stripe      │ Software Engineer, New.. │ Bengaluru  │  55  │ ✅ APPLY │
│ 2 │ Notion      │ Fullstack Early Career   │ Remote     │  45  │ ✅ APPLY │
│ 3 │ Clear       │ Backend Engineer         │ New York   │  14  │ ⏭️ SKIP  │
└───┴─────────────┴──────────────────────────┴────────────┴──────┴──────────┘

🏢 COMPANY BREAKDOWN (Top 15)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Stripe          3 jobs (8.6%)  ████████
Notion          2 jobs (5.7%)  █████
GitHub          2 jobs (5.7%)  █████
```

## 🚀 Future Enhancements

- [ ] **More Job Sources** - Indeed, Glassdoor, Stack Overflow Jobs
- [ ] **Application Tracking** - Monitor responses, interviews, rejections
- [ ] **A/B Testing** - Test different email templates and measure success
- [ ] **Telegram/Slack Notifications** - Real-time alerts for high-priority matches
- [ ] **ML-Based Scoring** - Train model on historical application outcomes
- [ ] **Resume Tailoring** - Auto-generate customized resumes per job
- [ ] **Interview Prep** - AI-generated company/role-specific prep materials
- [ ] **Salary Negotiation** - Data-driven compensation recommendations

## 📜 License

MIT License - See [LICENSE](LICENSE) file for details

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 💬 Support

- 📧 Email: vickyiitbombay2@gmail.com
- 🐙 GitHub: [@algsoch](https://github.com/algsoch)
- 💼 LinkedIn: [algsoch](https://www.linkedin.com/in/algsoch/)

## 🌟 Acknowledgments

Built with:
- [Ollama](https://ollama.ai) - Local LLM inference
- [Rich](https://github.com/Textualize/rich) - Beautiful terminal UI
- [Playwright](https://playwright.dev) - Browser automation
- [Typer](https://typer.tiangolo.com) - CLI framework

---

## 💭 Philosophy

> **"This system should run for 6 months without human intervention,**
> **make intelligent decisions, and never embarrass you with spam."**

Built for reliability, not novelty. Production-ready, not prototype.

---

<div align="center">

**⭐ Star this repo if you find it useful!**

Made with ❤️ by [Vicky Kumar](https://github.com/algsoch)

</div>
