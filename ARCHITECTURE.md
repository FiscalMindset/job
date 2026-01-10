# System Architecture - Job Intelligence OS

## Overview

This is a production-ready, autonomous job application system. Not a chatbot, not a demo.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI (Typer)                         │
│           run | status | stats | audit | retry              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Core Engine                             │
│  Orchestrates: collect→clean→dedupe→enrich→score→decide     │
│                      →outreach→store                        │
└───┬─────────┬─────────┬─────────┬─────────┬────────┬────────┘
    │         │         │         │         │        │
    ▼         ▼         ▼         ▼         ▼        ▼
┌────────┐ ┌───────┐ ┌──────┐ ┌────────┐ ┌──────┐ ┌───────┐
│Collect │ │Enrich │ │Score │ │Decide  │ │Email │ │Store  │
│        │ │       │ │      │ │        │ │      │ │       │
│LinkedIn│ │Email  │ │Rules │ │Thresh  │ │Comp  │ │CSV    │
│YC      │ │Finder │ │      │ │        │ │Send  │ │SQLite │
│WellFnd │ │       │ │LLM   │ │        │ │      │ │       │
└────────┘ └───────┘ └──────┘ └────────┘ └──────┘ └───────┘
     │         │         │         │         │        │
     └─────────┴─────────┴─────────┴─────────┴────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   Observability        │
              │  Logs | Metrics | CB   │
              └────────────────────────┘
```

## Design Principles

### 1. Determinism Over Hype
- Rule-based logic first
- LLM only for ambiguity
- Same input → same output
- Fully reproducible

### 2. Reliability Over Novelty
- Circuit breakers for failing sources
- Retry with exponential backoff
- Partial failure tolerance
- Idempotent operations

### 3. Infrastructure Over Abstractions
- CSV as source of truth
- SQLite for queries
- No heavyweight frameworks
- Simple, inspectable state

### 4. Systems Engineering Over "Agent Magic"
- No agent frameworks
- Explicit state machine
- Clear error handling
- Auditable decisions

## Data Flow

### 1. Collection Phase
```python
for collector in enabled_collectors:
    jobs = collector.collect()  # Each source independently
    # Circuit breaker prevents cascading failures
```

**Collectors:**
- `LinkedInCollector`: Scrapes LinkedIn job search
- `YCombinatorCollector`: YC Work at a Startup
- `WellfoundCollector`: Wellfound (AngelList)

Each collector:
- Has a circuit breaker
- Returns List[Job] or []
- Never crashes the pipeline
- Logs all errors

### 2. Deduplication Phase
```python
job_id = sha256(company + role + url)  # Deterministic ID
existing_ids = csv_store.get_existing_job_ids()
new_jobs = [j for j in jobs if j.job_id not in existing_ids]
```

Why it works:
- Same job → same hash
- CSV is append-only
- Fast set lookup
- Idempotent re-runs

### 3. Enrichment Phase
```python
email_result = email_finder.find_email(job)
# Strategies:
# 1. Common patterns (jobs@company.com)
# 2. Scrape company website
# 3. Parse job posting page
# 4. Verify domain exists
```

### 4. Scoring Phase
```python
score = (
    role_match(30) +        # Does role match target?
    skills_match(20) +      # Skills in description?
    company_stage(15) +     # Preferred stage?
    location_match(10) +    # Location preference?
    recency_bonus(15) +     # How recent?
    salary_check(10)        # Meets minimum?
)
```

**Rule-based scoring:**
- Fast (< 1ms per job)
- Deterministic
- Explainable
- No API costs

### 5. LLM Analysis Phase (Optional)
```python
if score in [40, 75]:  # Ambiguous range
    analysis = ollama.analyze_job_description(job)
    if analysis['suitable'] == False:
        score -= 30  # Adjust based on LLM
```

**When LLM is used:**
- Ambiguous job descriptions
- Edge cases near thresholds
- Email personalization
- Never for filtering or regex

### 6. Decision Phase
```python
if score >= 75:        APPLY
elif score >= 50:      APPLY_LATER
elif score >= 30:      WATCH
else:                  SKIP
```

Every decision has a reason string:
```
"Role matches 'backend engineer'; 5 skills match; Posted within 3 days; Salary >= $120,000"
```

### 7. Outreach Phase
```python
if decision == APPLY and email:
    # Rate limiting (5/hour, 20/day)
    # Human-like delay (60s between emails)
    # Personalized with LLM
    send_email(job)
```

### 8. Storage Phase
```python
# Primary: CSV (source of truth)
csv_store.save_jobs(jobs)

# Secondary: SQLite (queryable)
sqlite_store.save_jobs(jobs)

# Backup: Daily snapshots
csv_store.backup()
```

## State Management

### Job States
```
NEW → ENRICHED → SCORED → DECIDED → EMAIL_SENT
                                   ↓
                              FAILED/SKIPPED
```

### Email States
```
NOT_SENT → SENT → [optional] FOLLOW_UP_SENT
         ↓
       FAILED/BOUNCED
```

## Error Handling

### Circuit Breaker Pattern
```python
class CircuitBreaker:
    CLOSED → OPEN → HALF_OPEN → CLOSED
    
# After 5 failures:
# - OPEN: Reject all requests
# - Wait 5 minutes
# - HALF_OPEN: Try one request
# - Success → CLOSED
# - Failure → OPEN again
```

### Retry Logic
```python
for attempt in range(MAX_RETRIES):
    try:
        return fetch_url()
    except:
        wait(RETRY_DELAY * (2 ** attempt))
```

### Partial Failure Tolerance
```python
# One collector fails → others continue
# One job fails enrichment → others continue
# One email fails → others continue
```

## Decision Intelligence

### Rule-Based Scoring (Fast Path)
- 80% of jobs handled by rules
- < 1ms per job
- Deterministic
- No API costs

### LLM Analysis (Slow Path)
- 20% of jobs near thresholds
- 2-5s per job
- For ambiguity
- Local (Ollama)

### Hybrid Approach
```python
score = rules.score(job)  # Always run

if needs_llm_analysis(score):
    llm_result = ollama.analyze(job)
    score = adjust_score(score, llm_result)

decision = score_to_decision(score)
```

## Email System

### Rate Limiting
- 5 emails per hour (avoid spam flags)
- 20 emails per day (reasonable volume)
- 60 seconds between emails (appear human)

### Personalization Strategy
```python
# Template-based fallback
template = get_template("initial")
body = personalize_template(template, job)

# LLM enhancement (if available)
if ollama_available:
    body = ollama.personalize_email(job, template)
```

### Follow-up Logic (Future)
```
Day 0: Initial email
Day 7: Follow-up (if no response)
Day 14: Final follow-up
Stop: After 2 follow-ups
```

## Observability

### Logging
- Console: INFO+ (human-readable)
- File: DEBUG+ (everything)
- Structured format
- Rotating logs (10MB, 5 backups)

### Metrics
- Pipeline runs
- Jobs per source
- Decision distribution
- Email success rate
- Error counts

### Circuit Breaker Status
- Per-collector health
- Failure counts
- Recovery attempts

## Storage Design

### CSV (Primary)
**Why CSV?**
- Human-readable
- Git-friendly
- Easy to backup
- No database required
- Inspectable in Excel

**Structure:**
```csv
job_id,company,role,source,score,decision,reason,...
abc123,Stripe,Backend Engineer,linkedin,85,APPLY,"Role matches..."
```

### SQLite (Secondary)
**Why SQLite?**
- Fast queries
- Aggregations
- Filtering
- Analytics

**Not a replacement for CSV** - just for querying.

### Backup Strategy
- Daily CSV snapshots
- Keep last 30 days
- Automatic cleanup

## Cron Automation

### Daily Run
```bash
0 9 * * * jobctl run --sources all
```

### Weekly Stats
```bash
0 10 * * 0 jobctl stats --last 7d
```

### Failure Recovery
- Jobs stored even if email fails
- Retry command for failed jobs
- Idempotent re-runs safe

## Scalability

### Current Design
- 100-500 jobs/day
- 20-50 emails/day
- Single machine
- No database server

### If Scaling Needed
- Add more collectors
- PostgreSQL instead of SQLite
- Redis for rate limiting
- Kubernetes deployment
- Separate email service

## Security

### Credentials
- Gmail app password (not main password)
- Stored in .env (gitignored)
- No secrets in code

### Data Privacy
- All data local
- No cloud APIs (except Ollama)
- CSV can be encrypted at rest

### Email Safety
- Rate limits prevent spam
- Human-like delays
- Personalized content
- Follow-up limits

## Testing Strategy

### Unit Tests
```python
# Test each component independently
test_scorer.py
test_decider.py
test_collectors.py
```

### Integration Tests
```python
# Test pipeline end-to-end
test_engine.py
```

### Dry Run Mode
```bash
jobctl run --dry-run
# No actual emails sent
# Perfect for testing
```

## Future Enhancements

### Short Term
- [ ] More collectors (GitHub Jobs, Stack Overflow)
- [ ] A/B test email templates
- [ ] Track application outcomes

### Medium Term
- [ ] ML-based scoring (trained on historical data)
- [ ] Interview scheduling automation
- [ ] Salary negotiation templates

### Long Term
- [ ] Multi-user support
- [ ] Web dashboard
- [ ] API for integrations
- [ ] Mobile notifications

## Philosophy

> "This system should run for 6 months without human intervention,
> make intelligent decisions, and never embarrass you with spam."

Built for **reliability**, not **novelty**.
Built for **production**, not **demos**.
Built to **work**, not to **impress**.
