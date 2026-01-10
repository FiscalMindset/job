# Setup Guide - Job Intelligence OS

## Prerequisites

- Python 3.11 or higher
- Ollama installed and running
- Gmail account with app password
- macOS, Linux, or WSL

## Step-by-Step Setup

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Or download from https://ollama.ai

# Start Ollama service
ollama serve

# In another terminal, pull the model
ollama pull llama3.1:8b

# Verify
ollama list
```

### 2. Clone/Setup Project

```bash
cd /path/to/job_agentic

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or: venv\Scripts\activate  # On Windows

# Install dependencies
pip install -e .
```

### 3. Configure Gmail App Password

1. Go to https://myaccount.google.com/apppasswords
2. Sign in to your Google Account
3. Select "Mail" and your device
4. Click "Generate"
5. Copy the 16-character password (you'll use this in .env)

### 4. Create .env File

```bash
# Copy example config
cp .env.example .env

# Edit .env file
nano .env  # or use any editor
```

**Minimum required fields:**

```bash
# Gmail
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password-here
EMAIL_FROM=your-email@gmail.com
EMAIL_FROM_NAME=Your Name

# Personal profile
YOUR_NAME=Your Full Name
YOUR_TITLE=Senior Software Engineer
YOUR_SKILLS=Python,React,TypeScript,PostgreSQL,AWS,Docker
YOUR_EXPERIENCE_YEARS=5
YOUR_LOCATION=San Francisco, CA
YOUR_LINKEDIN=https://linkedin.com/in/yourprofile
YOUR_GITHUB=https://github.com/yourusername

# Job preferences
TARGET_ROLES=Software Engineer,Backend Engineer,Full Stack Engineer
PREFERRED_COMPANY_STAGES=seed,series-a,series-b
PREFERRED_LOCATIONS=San Francisco,Remote,New York
MIN_SALARY=120000

# Collectors
ENABLED_COLLECTORS=linkedin,ycombinator,wellfound
```

### 5. Verify Configuration

```bash
python cli.py config-check
```

This will validate your configuration and show any errors.

### 6. Run Test (Dry Run)

```bash
# This won't send any emails
python cli.py run --dry-run
```

You should see:
- Jobs being collected from sources
- Deduplication happening
- Scoring and decisions being made
- "Would send email to..." messages (but no actual emails)

### 7. First Real Run (Limited)

Start with a small test:

```bash
# Run with just one source
python cli.py run --sources ycombinator
```

Check your sent emails to verify:
- Emails look professional
- Personalization is working
- No errors in the logs

### 8. Schedule with Cron

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 9 AM)
0 9 * * * cd /path/to/job_agentic && /path/to/job_agentic/venv/bin/python /path/to/job_agentic/cli.py run --sources all >> /var/log/jobctl.log 2>&1
```

**Find your paths:**

```bash
# Project path
pwd

# Python path
which python
```

### 9. Monitor

```bash
# Check status
python cli.py status

# View stats
python cli.py stats --last 7d

# Audit decisions
python cli.py audit --decision APPLY
```

## Common Issues

### Issue: "Ollama connection failed"

**Solution:**
```bash
# Make sure Ollama is running
ollama serve

# In another terminal, verify
ollama list
```

### Issue: "SMTP authentication failed"

**Solution:**
- Make sure you're using an App Password, not your regular Gmail password
- Enable 2FA on your Google account first
- Generate new app password at https://myaccount.google.com/apppasswords

### Issue: "No jobs collected"

**Solution:**
- Check internet connection
- Sources may be blocking automated requests
- Check logs: `tail -f logs/jobctl.log`
- Try different sources

### Issue: "ModuleNotFoundError"

**Solution:**
```bash
# Make sure venv is activated
source venv/bin/activate

# Reinstall dependencies
pip install -e .
```

## Logging

Logs are written to:
- Console: INFO level and above
- File: `logs/jobctl.log` (all levels)

View logs:
```bash
# Follow live logs
tail -f logs/jobctl.log

# Search for errors
grep ERROR logs/jobctl.log

# View last 100 lines
tail -n 100 logs/jobctl.log
```

## Data Files

- Jobs: `data/jobs.csv` (primary source of truth)
- Database: `data/jobs.db` (for querying)
- Backups: `data/backups/jobs_*.csv` (automatic daily backups)
- Metrics: `data/metrics.jsonl` (performance tracking)

## Backup Strategy

Automatic backups are created daily and kept for 30 days.

Manual backup:
```bash
cp data/jobs.csv backups/jobs_$(date +%Y%m%d).csv
```

## Rate Limits

Default limits (configurable in .env):
- 5 emails per hour
- 20 emails per day
- 60 seconds between emails

These limits prevent:
- Gmail from flagging you as spam
- Recipients from receiving too many emails
- Overwhelming hiring teams

## Next Steps

1. ✅ Run dry-run and verify output
2. ✅ Send 1-2 test emails manually
3. ✅ Review emails in sent folder
4. ✅ Adjust scoring thresholds if needed
5. ✅ Schedule cron job
6. ✅ Monitor for 1 week
7. ✅ Add more sources as needed

## Productionization Checklist

- [ ] Tested dry-run mode
- [ ] Sent test emails successfully
- [ ] Reviewed and adjusted scoring rules
- [ ] Set appropriate rate limits
- [ ] Scheduled cron job
- [ ] Set up log rotation
- [ ] Configured backups
- [ ] Documented any customizations
- [ ] Added monitoring/alerting (optional)

## Getting Help

Check logs first:
```bash
tail -n 200 logs/jobctl.log | grep -E "ERROR|WARNING"
```

Common log locations:
- Application logs: `logs/jobctl.log`
- Cron logs: `/var/log/syslog` or check cron output

## Performance Tuning

If the system is too slow:
- Reduce `REQUEST_TIMEOUT` in .env
- Disable Playwright (set `ENABLE_PLAYWRIGHT=false`)
- Limit collectors (only enable fast sources)

If decisions are wrong:
- Adjust thresholds in .env
- Modify scoring rules in `intelligence/scorer.py`
- Check LLM is working: `ollama list`

## Security Notes

- Never commit `.env` file to git
- Keep app password secure
- Regularly rotate app password
- Review sent emails periodically
- Don't share CSV files (contain personal data)
