# Deployment Guide - Job Intelligence OS

## Pre-Deployment Checklist

- [ ] Python 3.11+ installed
- [ ] Ollama installed and running
- [ ] Gmail app password created
- [ ] .env file configured
- [ ] Dry run tested successfully
- [ ] Test email sent and received
- [ ] Logs directory created
- [ ] Data directory created

## Local Deployment (Development)

### 1. Install Dependencies

```bash
cd /path/to/job_agentic

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install package
pip install -e .
```

### 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit configuration
nano .env
```

**Required fields:**
- SMTP credentials
- Personal profile (name, skills, etc.)
- Job preferences
- Enabled collectors

### 3. Verify Installation

```bash
# Check configuration
python cli.py config-check

# Test dry run
python cli.py run --dry-run

# View logs
tail -f logs/jobctl.log
```

## Production Deployment (macOS/Linux)

### 1. Setup Directory Structure

```bash
# Recommended location
sudo mkdir -p /opt/job_agentic
sudo chown $USER:$USER /opt/job_agentic

# Copy files
cp -r . /opt/job_agentic/
cd /opt/job_agentic
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e .
```

### 3. Configure Ollama as Service (macOS)

**Create LaunchAgent:**

```bash
# Create plist file
nano ~/Library/LaunchAgents/com.ollama.server.plist
```

**Content:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/ollama</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/ollama.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/ollama_error.log</string>
</dict>
</plist>
```

**Load service:**
```bash
launchctl load ~/Library/LaunchAgents/com.ollama.server.plist
launchctl start com.ollama.server
```

### 4. Configure Ollama as Service (Linux - systemd)

```bash
sudo nano /etc/systemd/system/ollama.service
```

**Content:**
```ini
[Unit]
Description=Ollama Server
After=network.target

[Service]
Type=simple
User=yourusername
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

### 5. Setup Cron Job

```bash
# Edit crontab
crontab -e
```

**Add daily job (9 AM):**
```bash
# Job Intelligence OS - Daily run
0 9 * * * cd /opt/job_agentic && /opt/job_agentic/venv/bin/python /opt/job_agentic/cli.py run --sources all >> /var/log/jobctl.log 2>&1

# Weekly stats report
0 10 * * 0 cd /opt/job_agentic && /opt/job_agentic/venv/bin/python /opt/job_agentic/cli.py stats --last 7d >> /var/log/jobctl_stats.log 2>&1
```

**Verify cron job:**
```bash
# List cron jobs
crontab -l

# Check cron logs (macOS)
log show --predicate 'eventMessage contains "cron"' --last 1h

# Check cron logs (Linux)
grep CRON /var/log/syslog
```

### 6. Setup Log Rotation

**Linux:**
```bash
sudo nano /etc/logrotate.d/jobctl
```

**Content:**
```
/opt/job_agentic/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0644 yourusername yourusername
}
```

**macOS (using newsyslog):**
```bash
sudo nano /etc/newsyslog.d/jobctl.conf
```

**Content:**
```
# logfilename          [owner:group]    mode count size when  flags [/pid_file] [sig_num]
/opt/job_agentic/logs/jobctl.log    644  30    10000 *     GZ
```

### 7. Setup Monitoring (Optional)

**Email notifications on failure:**

Create wrapper script:
```bash
nano /opt/job_agentic/run_with_notification.sh
```

**Content:**
```bash
#!/bin/bash

cd /opt/job_agentic
source venv/bin/activate

# Run job
python cli.py run --sources all 2>&1 | tee /tmp/jobctl_output.log

# Check exit code
if [ $? -ne 0 ]; then
    # Send notification (requires mail command)
    cat /tmp/jobctl_output.log | mail -s "Job Intelligence OS Failed" your-email@gmail.com
fi
```

**Make executable:**
```bash
chmod +x /opt/job_agentic/run_with_notification.sh
```

**Update cron to use wrapper:**
```bash
0 9 * * * /opt/job_agentic/run_with_notification.sh
```

## Docker Deployment (Advanced)

### Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Set working directory
WORKDIR /app

# Copy files
COPY . /app

# Install Python dependencies
RUN pip install -e .

# Create data directories
RUN mkdir -p /app/data /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Start Ollama and run job
CMD ["sh", "-c", "ollama serve & sleep 5 && ollama pull llama3.1:8b && python cli.py run --sources all"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  job-intelligence:
    build: .
    container_name: job_intelligence_os
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```

### Build and Run

```bash
# Build image
docker-compose build

# Run dry-run first
docker-compose run job-intelligence python cli.py run --dry-run

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f
```

## Cloud Deployment (Optional)

### AWS EC2

1. Launch Ubuntu instance (t3.medium or larger)
2. Install Python 3.11
3. Install Ollama
4. Clone repository
5. Configure .env
6. Setup cron
7. Configure security group (no inbound needed)

### Google Cloud Run (Not Recommended)

Cloud Run is serverless - not suitable for long-running scrapers.
Use Compute Engine instead.

### DigitalOcean Droplet

1. Create Ubuntu droplet ($12/month)
2. Follow Linux deployment steps
3. Configure firewall (no inbound needed)

## Security Hardening

### 1. Protect .env File

```bash
# Set restrictive permissions
chmod 600 .env

# Ensure not in git
grep .env .gitignore  # Should be there
```

### 2. Use Secrets Manager (Advanced)

Instead of .env, use:
- macOS Keychain
- AWS Secrets Manager
- HashiCorp Vault

### 3. Rotate Gmail App Password

```bash
# Every 90 days
# 1. Generate new app password
# 2. Update .env
# 3. Restart cron job
```

### 4. Limit File Permissions

```bash
# Restrict access to data directory
chmod 700 /opt/job_agentic/data

# Restrict access to logs
chmod 700 /opt/job_agentic/logs
```

## Backup Strategy

### Automated Backups

Built-in daily CSV backups (kept for 30 days).

### External Backups

**To Google Drive (macOS):**
```bash
# Add to cron
0 2 * * * cp -r /opt/job_agentic/data ~/Library/CloudStorage/GoogleDrive-.../job_agentic_backup/
```

**To S3 (AWS):**
```bash
# Install AWS CLI
pip install awscli

# Add to cron
0 2 * * * aws s3 sync /opt/job_agentic/data s3://your-bucket/job_agentic/
```

**To Dropbox:**
```bash
# Install Dropbox Uploader
# Add to cron
0 2 * * * /path/to/dropbox_uploader.sh upload /opt/job_agentic/data /job_agentic/
```

## Monitoring

### Check System Health

```bash
# Check if Ollama is running
ps aux | grep ollama

# Check last run
tail -n 100 /opt/job_agentic/logs/jobctl.log

# Check cron execution
grep jobctl /var/log/syslog  # Linux
log show --predicate 'process == "cron"' --last 1d  # macOS

# Check data files
ls -lh /opt/job_agentic/data/
```

### Health Check Script

```bash
nano /opt/job_agentic/healthcheck.sh
```

**Content:**
```bash
#!/bin/bash

echo "=== Job Intelligence OS Health Check ==="

# Check Ollama
if pgrep -x "ollama" > /dev/null; then
    echo "✓ Ollama is running"
else
    echo "✗ Ollama is NOT running"
fi

# Check last run
LAST_RUN=$(stat -f %Sm -t "%Y-%m-%d %H:%M" /opt/job_agentic/data/jobs.csv 2>/dev/null)
echo "Last data update: $LAST_RUN"

# Check log for errors
ERROR_COUNT=$(grep -c ERROR /opt/job_agentic/logs/jobctl.log 2>/dev/null || echo 0)
echo "Recent errors: $ERROR_COUNT"

# Check disk space
DISK_USAGE=$(df -h /opt/job_agentic | tail -1 | awk '{print $5}')
echo "Disk usage: $DISK_USAGE"
```

**Run daily:**
```bash
chmod +x /opt/job_agentic/healthcheck.sh

# Add to cron
0 18 * * * /opt/job_agentic/healthcheck.sh | mail -s "Job Intelligence Health" your-email@gmail.com
```

## Troubleshooting

### Issue: Cron job not running

**Check:**
```bash
# Verify cron service
sudo systemctl status cron  # Linux
sudo launchctl list | grep cron  # macOS

# Check cron logs
tail -f /var/log/syslog | grep CRON  # Linux

# Test command manually
cd /opt/job_agentic && /opt/job_agentic/venv/bin/python /opt/job_agentic/cli.py run --dry-run
```

### Issue: Ollama not starting

**Check:**
```bash
# Test Ollama
ollama list

# Check service status
sudo systemctl status ollama  # Linux
launchctl list | grep ollama  # macOS

# Restart service
sudo systemctl restart ollama  # Linux
launchctl restart com.ollama.server  # macOS
```

### Issue: Out of disk space

**Solution:**
```bash
# Clean old backups
cd /opt/job_agentic/data/backups
rm jobs_202401*.csv  # Delete old backups

# Clean logs
cd /opt/job_agentic/logs
> jobctl.log  # Truncate log file

# Or use log rotation
```

## Upgrade Procedure

### Update Code

```bash
cd /opt/job_agentic
git pull origin main  # If using git

# Or manually copy new files
```

### Update Dependencies

```bash
source venv/bin/activate
pip install --upgrade -e .
```

### Update Ollama Model

```bash
ollama pull llama3.1:8b
```

### Test After Upgrade

```bash
# Dry run
python cli.py run --dry-run

# Check logs
tail -f logs/jobctl.log
```

## Rollback Procedure

### If Update Breaks

```bash
# Restore from backup
cp data/backups/jobs_YYYYMMDD.csv data/jobs.csv

# Or revert code
git checkout previous-commit  # If using git

# Reinstall old dependencies
pip install -e .
```

## Production Checklist

- [ ] Ollama running as service
- [ ] Cron job scheduled
- [ ] Log rotation configured
- [ ] Backups automated
- [ ] Health checks in place
- [ ] Monitoring enabled
- [ ] Rate limits configured
- [ ] Tested dry run
- [ ] Tested real run with 1-2 jobs
- [ ] Documented any customizations

## Support

For issues:
1. Check logs: `tail -f logs/jobctl.log`
2. Run health check: `./healthcheck.sh`
3. Test components individually
4. Review SETUP.md for common issues
