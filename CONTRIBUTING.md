# 🤝 Contributing to Job Intelligence OS

We love contributions! Here's how to get started.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Commit Conventions](#commit-conventions)
- [Adding a New Collector](#adding-a-new-collector)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

By participating, you agree to maintain a respectful, inclusive environment. Harassment or discriminatory behavior will not be tolerated.

---

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/fiscalmindset/job_agentic.git
cd job_agentic

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies (including dev)
pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Verify setup
python3 cli.py config-check
```

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| Ollama | Latest | Local LLM |
| Playwright | Latest | Browser scraping |
| Git | Any | Version control |

### Recommended Tools

- **VS Code** with Python, Ruff, and Mypy extensions
- **Ollama** with `llama3.1:8b` or similar model

---

## Project Structure

```
job_agentic/
├── cli.py                  # CLI entry point (Typer)
├── config.py               # Configuration management
├── core/                   # Pipeline orchestration
│   ├── engine.py           # Main pipeline orchestrator
│   ├── models.py           # Data models (Job, Decision, etc.)
│   └── state.py            # State management
├── collectors/             # Job scrapers
│   ├── base.py             # Abstract collector + circuit breaker
│   ├── linkedin.py         # LinkedIn jobs
│   ├── github.py           # GitHub jobs
│   ├── naukri.py           # Naukri jobs
│   ├── ycombinator.py      # YC jobs
│   └── wellfound.py        # Wellfound jobs
├── intelligence/           # Decision engine
│   ├── rules.py            # Rule-based scoring
│   ├── scorer.py           # Score calculation
│   └── decider.py          # Decision maker
├── enrichment/             # Data enrichment
│   ├── email_finder.py     # Email discovery
│   ├── profile_report.py   # Profile analysis
│   └── company_research.py # Company research
├── outreach/               # Email automation
│   ├── composer.py         # Email composition
│   ├── sender.py           # SMTP sending
│   └── templates/          # Email templates
├── storage/                # Persistence
│   ├── csv_store.py        # CSV storage
│   ├── sqlite_store.py     # SQLite storage
│   └── backup.py           # Backup management
└── observability/          # Monitoring
    ├── logger.py           # Logging
    ├── metrics.py          # Metrics
    ├── notifier.py         # Notifications
    └── circuit_breaker.py  # Circuit breaker
```

---

## Coding Standards

### Python Style

This project uses strict type checking and formatting:

```bash
# Format code
black .

# Lint
ruff check .

# Type check
mypy .
```

### Rules

| Rule | Standard |
|------|----------|
| **Line length** | 100 characters |
| **Quotes** | Double quotes for strings |
| **Typing** | Full type annotations required |
| **Docstrings** | Google-style docstrings |
| **Imports** | Grouped: stdlib → third-party → local |
| **Naming** | `snake_case` for functions/vars, `PascalCase` for classes |

### Example

```python
"""Module docstring."""
import hashlib
from typing import Optional

import httpx

from core.models import Job


def generate_job_id(company: str, role: str, url: str) -> str:
    """Generate deterministic job ID from core fields.
    
    Args:
        company: Company name
        role: Job title
        url: Job posting URL
        
    Returns:
        First 16 characters of SHA-256 hash
    """
    content = f"{company}|{role}|{url}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=.

# Specific test file
pytest tests/test_scorer.py

# Verbose
pytest -v
```

### What to Test

| Component | What to Test |
|-----------|--------------|
| **Scorer** | Score calculation with various inputs |
| **Decider** | Decision thresholds, edge cases |
| **Collectors** | HTML parsing, error handling |
| **EmailFinder** | Domain extraction, pattern matching |
| **Models** | Serialization, ID generation |
| **Engine** | Pipeline orchestration, dry-run mode |

### Testing Guidelines

1. **Unit test** each component in isolation
2. **Mock external APIs** (GitHub, LinkedIn, SMTP)
3. **Test edge cases** — empty results, malformed HTML, timeouts
4. **Test idempotency** — same input should produce same output
5. **Test error paths** — circuit breaker, retry logic

---

## Pull Request Process

### Step-by-Step

1. **Fork** the repository
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
   - Follow coding standards
   - Add tests for new code
   - Update docs if needed
4. **Run checks locally**
   ```bash
   black .
   ruff check .
   mypy .
   pytest
   ```
5. **Commit** with a descriptive message
6. **Push** to your fork
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Open a Pull Request** against `main`

### PR Checklist

- [ ] Code follows project style (black, ruff, mypy pass)
- [ ] Tests added/updated and passing
- [ ] Documentation updated (README, ARCHITECTURE, docs/)
- [ ] No new dependencies without discussion
- [ ] Changes are backward compatible
- [ ] Commit messages follow convention

### Review Process

1. At least one maintainer review required
2. All CI checks must pass
3. Address review feedback
4. Squash commits before merge

---

## Commit Conventions

Use conventional commits:

```
<type>(<scope>): <description>

[optional body]
```

### Types

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, linting |
| `refactor` | Code restructuring |
| `test` | Adding/updating tests |
| `chore` | Build, config, CI |

### Examples

```
feat(collector): add Indeed job source
fix(email_finder): handle companies with special chars in name
docs(readme): update quick start with uv instructions
refactor(scorer): extract location matching to helper
test(engine): add pipeline dry-run test
```

---

## Adding a New Collector

1. **Create** `collectors/your_source.py`
2. **Extend** `BaseCollector` (from `collectors/base.py`)
3. **Implement** `_collect_impl()` returning `List[Job]`
4. **Add** circuit breaker integration
5. **Register** in `cli.py:_init_engine()`:
   ```python
   if "yoursource" in config.ENABLED_COLLECTORS:
       collectors.append(YourSourceCollector())
   ```
6. **Add** to `config.py:ENABLED_COLLECTORS` defaults
7. **Update** `README.md` source table
8. **Add** `ARCHITECTURE.md` documentation
9. **Write** tests in `tests/`

### Collector Template

```python
"""Collector for YourSource."""
from typing import List
import httpx
from bs4 import BeautifulSoup

from collectors.base import BaseCollector
from core.models import Job
import config


class YourSourceCollector(BaseCollector):
    """Scrapes jobs from YourSource."""
    
    def __init__(self):
        super().__init__()
        self.source_name = "yoursource"
        self.base_url = "https://yoursource.com/jobs"
    
    def _collect_impl(self) -> List[Job]:
        """Fetch and parse jobs from YourSource."""
        jobs = []
        
        for keyword in config.TARGET_ROLES:
            response = self._fetch(f"{self.base_url}?q={keyword}")
            soup = BeautifulSoup(response.text, "html.parser")
            
            for listing in soup.select(".job-listing"):
                job = self._parse_listing(listing)
                if job:
                    jobs.append(job)
        
        return jobs
    
    def _parse_listing(self, element) -> Job:
        """Parse a single job listing into a Job object."""
        # ... parsing logic ...
        pass
```

---

## Reporting Issues

### Bug Reports

Include:

- **System info**: Python version, Ollama version, OS
- **Steps to reproduce**: Exact commands and input
- **Expected behavior**: What should happen
- **Actual behavior**: What happened instead
- **Logs**: Relevant lines from `logs/jobctl.log`
- **Config**: Sanitized `.env` (remove secrets)

### Feature Requests

Include:

- **Problem**: What gap does this fill?
- **Solution**: How would you like it to work?
- **Alternatives**: What else have you considered?
- **Context**: Any relevant links or references

---

## Getting Help

| Channel | Where |
|---------|-------|
| **Issues** | GitHub Issues |
| **Email** | npdimagine@gmail.com |
| **GitHub** | [@fiscalmindset](https://github.com/fiscalmindset) |

---

*For system architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).*  
*For quick start, see [README.md](README.md).*