# LLM Prompt Engineering Guide

## Prompt Design Philosophy

### Core Principles
1. **Task-specific prompts** - Not one giant prompt
2. **Structured output** - JSON when possible
3. **Explicit constraints** - Temperature, length, format
4. **Fallback handling** - System works even if LLM fails

## Prompt Templates

### 1. Job Description Analysis

**Use Case:** Determine if ambiguous job is a good fit

**System Prompt:**
```
You are a job analysis assistant.
Your user is a [TITLE] with [YEARS] years experience.
Skills: [SKILLS]

Analyze if this job is a good fit. Be critical but fair.
Respond in JSON format with keys:
- suitable (bool)
- reason (str, max 200 chars)
- concerns (list of str)
```

**User Prompt:**
```
Job: [ROLE] at [COMPANY]
Location: [LOCATION]

Description:
[FIRST 1000 CHARS OF DESCRIPTION]

Is this a good fit? Be specific about why or why not.
```

**Expected Output:**
```json
{
  "suitable": true,
  "reason": "Strong backend focus, uses Python extensively, early-stage startup",
  "concerns": ["On-call rotation mentioned", "Remote-first not clear"]
}
```

**Fallback if LLM fails:**
```python
return {
    "suitable": False,
    "reason": "LLM analysis unavailable",
    "concerns": []
}
```

### 2. Email Personalization

**Use Case:** Make cold emails feel human and specific

**System Prompt:**
```
You are writing a professional job application email.
Your name: [NAME]
Your title: [TITLE]
Your background: [YEARS] years in software engineering

Write a natural, confident email. Reference the specific company and role.
Avoid buzzwords like "excited", "passionate", "thrilled".
Be direct and professional. Keep it under 150 words.
```

**User Prompt:**
```
Personalize this email template for:

Company: [COMPANY]
Role: [ROLE]
To: [HIRING_MANAGER or "Hiring Manager"]

Template:
[BASE_TEMPLATE]

Write the complete email. Do not add subject line or signature.
```

**Example Output:**
```
Hi,

I'm [NAME], a [TITLE] with [YEARS] years of experience.

I came across the [ROLE] position at [COMPANY] and wanted to reach out directly.

I have experience with [relevant tech from job description] and have worked on 
[relevant achievement]. [COMPANY]'s approach to [specific thing about company] 
aligns with my experience in [relevant domain].

Would you be open to a conversation about this role?

Portfolio: [URL]
LinkedIn: [URL]
```

**Constraints:**
- Temperature: 0.7 (creative but consistent)
- Max tokens: 300
- Timeout: 30s

### 3. Key Requirements Extraction

**Use Case:** Understanding what really matters in a role

**System Prompt:**
```
Extract the top 5 key requirements from this job description.
Return as a bullet list. Be concise.
```

**User Prompt:**
```
Job description:
[FIRST 800 CHARS]
```

**Expected Output:**
```
- 5+ years Python backend development
- Experience with distributed systems
- PostgreSQL and Redis expertise
- Startup experience preferred
- On-call rotation participation
```

## When to Use LLM vs Rules

### Use Rules For:
- ✅ Keyword matching
- ✅ Salary filtering
- ✅ Location matching
- ✅ Date calculations
- ✅ String manipulation
- ✅ Data validation

### Use LLM For:
- ✅ Understanding ambiguous descriptions
- ✅ Email personalization
- ✅ Cultural fit assessment
- ✅ Extracting implicit requirements
- ✅ Founder/LinkedIn post interpretation

### Never Use LLM For:
- ❌ Filtering (too slow)
- ❌ Regex operations
- ❌ Deterministic logic
- ❌ Data transformation
- ❌ Decision thresholds

## Ollama Configuration

### Model Selection

**Current: llama3.1:8b**
- Fast (2-3s per query)
- Good quality
- Runs locally
- 4.9GB download

**Alternatives:**
```bash
# Faster but lower quality
ollama pull llama3.1:7b

# Higher quality but slower
ollama pull llama3.1:70b  # Requires 40GB RAM

# Specialized for coding
ollama pull codellama:7b
```

### Temperature Settings

```python
# Analysis (need consistency)
temperature: 0.3

# Email writing (need variety)
temperature: 0.7

# Creative tasks
temperature: 0.9
```

### Timeout Strategy

```python
# Default: 60 seconds
# If timeout: Use fallback, don't crash
try:
    result = ollama.generate(prompt, timeout=60)
except TimeoutError:
    logger.warning("LLM timeout, using fallback")
    return fallback_result
```

## Prompt Optimization

### Bad Prompt (Vague)
```
Tell me if this job is good.

Job: Software Engineer at Stripe
```

### Good Prompt (Specific)
```
You are analyzing jobs for a Senior Backend Engineer with 5 years Python experience.

Job: Backend Engineer at Stripe
Description: [full description]

Is this a good fit? Consider:
1. Technical stack match
2. Experience level
3. Role responsibilities

Respond in JSON: {suitable: bool, reason: str}
```

### Why It's Better:
- Provides context (who is applying)
- Specific evaluation criteria
- Structured output format
- Clear expectations

## Response Parsing

### JSON Parsing with Fallback
```python
def parse_llm_response(response: str) -> dict:
    """Parse LLM response with fallback."""
    try:
        # Try JSON first
        return json.loads(response)
    except json.JSONDecodeError:
        # Fallback: extract from text
        return {
            "suitable": "yes" in response.lower(),
            "reason": response[:200],
            "concerns": []
        }
```

### Extract Key-Value Pairs
```python
def extract_fields(response: str) -> dict:
    """Extract structured data from free-form text."""
    fields = {}
    
    # Look for patterns like "Field: Value"
    for line in response.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            fields[key.strip().lower()] = value.strip()
    
    return fields
```

## Caching Strategy

### Why Cache LLM Responses?
- Avoid redundant API calls
- Faster re-processing
- Cost savings (even for local LLMs)

### Implementation
```python
class Job:
    llm_analysis: Dict[str, Any] = field(default_factory=dict)

# Check cache first
if job.llm_analysis.get('job_suitability'):
    return job.llm_analysis['job_suitability']

# Call LLM
result = ollama.analyze_job_description(job)

# Cache result
job.llm_analysis['job_suitability'] = result
```

## Error Handling

### LLM Unavailable
```python
try:
    self.llm = OllamaClient()
except Exception as e:
    logger.warning(f"LLM unavailable: {e}")
    self.use_llm = False
```

### Individual Call Failures
```python
try:
    return self.llm.generate(prompt)
except Exception as e:
    logger.error(f"LLM call failed: {e}")
    return None  # Graceful degradation
```

### Timeout Handling
```python
response = self.client.post(
    url,
    json=payload,
    timeout=60  # Hard timeout
)
```

## Testing LLM Integration

### Manual Test
```bash
# Start Ollama
ollama serve

# Test in Python
python3 << EOF
from intelligence.llm import OllamaClient

client = OllamaClient()
result = client.generate("Say hello")
print(result)
EOF
```

### Unit Test (Mock)
```python
def test_analyze_with_llm_failure(mocker):
    """Test graceful degradation when LLM fails."""
    mock_llm = mocker.patch('intelligence.decider.OllamaClient')
    mock_llm.side_effect = Exception("LLM down")
    
    decider = JobDecider(use_llm=True)
    job = create_test_job()
    
    decider.decide(job)
    
    # Should still make a decision
    assert job.decision in [Decision.APPLY, Decision.SKIP, ...]
```

## Production Best Practices

### 1. Always Have Fallbacks
```python
if llm_available:
    body = llm.personalize_email(job, template)
else:
    body = template_engine.personalize(template, job)
```

### 2. Set Reasonable Timeouts
```python
OLLAMA_TIMEOUT = 60  # seconds
# Don't wait forever for LLM response
```

### 3. Log All LLM Calls
```python
logger.debug(f"LLM prompt: {prompt[:100]}...")
logger.debug(f"LLM response: {response[:100]}...")
```

### 4. Monitor LLM Performance
```python
start = time.time()
result = llm.generate(prompt)
duration = time.time() - start

metrics.record_llm_call(
    duration=duration,
    success=result is not None
)
```

### 5. Cache Aggressively
```python
# Store in Job.llm_analysis
# Saved to CSV
# Persisted across runs
```

## Prompt Versioning

Track prompt changes:
```python
PROMPT_VERSION = "v2"

prompt = f"""
[v2 - Added explicit constraints]

{actual_prompt}
"""
```

Save version in job record:
```python
job.llm_analysis['prompt_version'] = PROMPT_VERSION
```

## Summary

### LLM Usage Rules
1. ✅ Use for understanding, not filtering
2. ✅ Use for personalization, not decisions
3. ✅ Always have a fallback
4. ✅ Cache responses
5. ✅ Set timeouts
6. ✅ Log all calls
7. ✅ Handle errors gracefully

### What Makes a Good Prompt?
- Clear context
- Specific task
- Structured output
- Explicit constraints
- Examples (when helpful)

### Red Flags
- ❌ One giant prompt for everything
- ❌ No fallback when LLM fails
- ❌ Using LLM for simple regex
- ❌ No timeout configured
- ❌ Ignoring LLM errors
