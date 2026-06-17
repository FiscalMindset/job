"""Configuration management for Job Intelligence OS."""
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", DATA_DIR / "backups"))
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

CSV_FILE = Path(os.getenv("CSV_FILE", DATA_DIR / "jobs.csv"))
SQLITE_FILE = Path(os.getenv("SQLITE_FILE", DATA_DIR / "jobs.db"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USERNAME)
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Job Seeker")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))

YOUR_NAME = os.getenv("YOUR_NAME", "")
YOUR_TITLE = os.getenv("YOUR_TITLE", "")
YOUR_SKILLS = [s.strip() for s in os.getenv("YOUR_SKILLS", "").split(",") if s.strip()]
YOUR_EXPERIENCE_YEARS = int(os.getenv("YOUR_EXPERIENCE_YEARS", "0"))
YOUR_LOCATION = os.getenv("YOUR_LOCATION", "")
YOUR_LINKEDIN = os.getenv("YOUR_LINKEDIN", "")
YOUR_GITHUB = os.getenv("YOUR_GITHUB", "")
YOUR_PORTFOLIO = os.getenv("YOUR_PORTFOLIO", "")
YOUR_RESUME = os.getenv("YOUR_RESUME", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

TARGET_ROLES = [r.strip() for r in os.getenv("TARGET_ROLES", "").split(",") if r.strip()]
PREFERRED_COMPANY_STAGES = [s.strip() for s in os.getenv("PREFERRED_COMPANY_STAGES", "").split(",") if s.strip()]
PREFERRED_COMPANY_SIZES = [s.strip() for s in os.getenv("PREFERRED_COMPANY_SIZES", "").split(",") if s.strip()]
PREFERRED_LOCATIONS = [loc.strip() for loc in os.getenv("PREFERRED_LOCATIONS", "").split(",") if loc.strip()]
MIN_SALARY = int(os.getenv("MIN_SALARY", "0"))
MAX_COMMUTE_MILES = int(os.getenv("MAX_COMMUTE_MILES", "20"))
MIN_EXPERIENCE_YEARS = int(os.getenv("MIN_EXPERIENCE_YEARS", "0"))
MAX_EXPERIENCE_YEARS = int(os.getenv("MAX_EXPERIENCE_YEARS", "2"))

APPLY_THRESHOLD = int(os.getenv("APPLY_THRESHOLD", "75"))
APPLY_LATER_THRESHOLD = int(os.getenv("APPLY_LATER_THRESHOLD", "50"))
WATCH_THRESHOLD = int(os.getenv("WATCH_THRESHOLD", "30"))

SCORE_WEIGHTS = {
    "role": int(os.getenv("SCORE_WEIGHT_ROLE", "30")),
    "skills": int(os.getenv("SCORE_WEIGHT_SKILLS", "20")),
    "company_stage": int(os.getenv("SCORE_WEIGHT_STAGE", "15")),
    "location": int(os.getenv("SCORE_WEIGHT_LOCATION", "10")),
    "recency": int(os.getenv("SCORE_WEIGHT_RECENCY", "15")),
    "salary": int(os.getenv("SCORE_WEIGHT_SALARY", "10")),
}

MAX_EMAILS_PER_DAY = int(os.getenv("MAX_EMAILS_PER_DAY", "20"))
MAX_EMAILS_PER_HOUR = int(os.getenv("MAX_EMAILS_PER_HOUR", "5"))
EMAIL_DELAY_SECONDS = int(os.getenv("EMAIL_DELAY_SECONDS", "60"))

MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "30"))

ENABLED_COLLECTORS = [c.strip() for c in os.getenv("ENABLED_COLLECTORS", "linkedin,ycombinator,wellfound").split(",") if c.strip()]
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

LINKEDIN_MAX_PAGES = int(os.getenv("LINKEDIN_MAX_PAGES", "5"))
LINKEDIN_JOBS_PER_PAGE = int(os.getenv("LINKEDIN_JOBS_PER_PAGE", "25"))

CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "300"))

LINKEDIN_SESSION_COOKIE = os.getenv("LINKEDIN_SESSION_COOKIE", "")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = Path(os.getenv("LOG_FILE", LOG_DIR / "jobctl.log"))
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

SEND_COMPLETION_EMAIL = os.getenv("SEND_COMPLETION_EMAIL", "true").lower() == "true"
NOTIFY_ON_ERRORS = os.getenv("NOTIFY_ON_ERRORS", "true").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
ENABLE_PLAYWRIGHT = os.getenv("ENABLE_PLAYWRIGHT", "false").lower() == "true"
SAVE_RAW_HTML = os.getenv("SAVE_RAW_HTML", "false").lower() == "true"
CONCURRENT_COLLECTORS = int(os.getenv("CONCURRENT_COLLECTORS", "3"))


_CONFIG_FIELDS = {
    "SMTP_USERNAME": ("string", False, "Gmail address for sending emails"),
    "SMTP_PASSWORD": ("string", False, "Gmail app password"),
    "YOUR_NAME": ("string", False, "Your full name"),
    "YOUR_SKILLS": ("comma_list", False, "Your skills (comma-separated)"),
    "TARGET_ROLES": ("comma_list", False, "Target job roles (comma-separated)"),
    "ENABLED_COLLECTORS": ("comma_list", True, "Enabled job sources"),
    "OLLAMA_HOST": ("string", True, "Ollama server URL"),
    "OLLAMA_MODEL": ("string", True, "Ollama model name"),
    "MIN_SALARY": ("int", True, "Minimum annual salary"),
    "APPLY_THRESHOLD": ("int", True, "Minimum score to auto-apply (0-100)"),
}


def get_schema() -> Dict[str, tuple]:
    return dict(_CONFIG_FIELDS)


def validate_config() -> List[str]:
    errors = []
    checks = [
        (not SMTP_USERNAME, "SMTP_USERNAME is required (e.g., your.email@gmail.com)"),
        (not SMTP_PASSWORD, "SMTP_PASSWORD is required (use Gmail app password from https://myaccount.google.com/apppasswords)"),
        (not YOUR_NAME, "YOUR_NAME is required"),
        (not YOUR_SKILLS, "YOUR_SKILLS is required (comma-separated, e.g., Python, FastAPI, React)"),
        (not TARGET_ROLES, "TARGET_ROLES is required (comma-separated, e.g., AI Engineer, Backend Developer)"),
        (not ENABLED_COLLECTORS, "ENABLED_COLLECTORS is required (e.g., linkedin,ycombinator,wellfound)"),
    ]
    for condition, msg in checks:
        if condition:
            errors.append(msg)

    if SMTP_USERNAME and "@" not in SMTP_USERNAME:
        errors.append("SMTP_USERNAME must be a valid email address")
    if not (0 <= APPLY_THRESHOLD <= 100):
        errors.append("APPLY_THRESHOLD must be 0-100")
    if not (0 <= APPLY_LATER_THRESHOLD <= 100):
        errors.append("APPLY_LATER_THRESHOLD must be 0-100")
    if not (0 <= WATCH_THRESHOLD <= 100):
        errors.append("WATCH_THRESHOLD must be 0-100")
    if not (APPLY_THRESHOLD > APPLY_LATER_THRESHOLD > WATCH_THRESHOLD):
        errors.append("Thresholds must be ordered: APPLY > APPLY_LATER > WATCH")
    if MAX_EMAILS_PER_HOUR > MAX_EMAILS_PER_DAY:
        errors.append("MAX_EMAILS_PER_HOUR cannot exceed MAX_EMAILS_PER_DAY")

    return errors


def validate_with_detail() -> List[Dict[str, Any]]:
    results = []
    for field, (ftype, optional, desc) in _CONFIG_FIELDS.items():
        val = os.getenv(field, "")
        status = "ok"
        msg = ""
        if not val and not optional:
            status = "missing"
            msg = f"{desc} — not set"
        elif val and ftype == "int":
            try:
                int(val)
            except ValueError:
                status = "invalid"
                msg = f"Expected integer, got '{val}'"
        if status == "ok":
            msg = f"{desc} — {'✓' if val else '(optional, not set)'}"
        results.append({"field": field, "value": val or "(not set)", "status": status, "message": msg})
    return results


def to_env_line(key: str, value: str) -> str:
    return f"{key}={value}\n"


def write_env_example(path: Optional[Path] = None) -> Path:
    path = path or BASE_DIR / ".env.example"
    lines = [
        "# ===== GMAIL SMTP =====",
        "SMTP_HOST=smtp.gmail.com",
        "SMTP_PORT=587",
        'SMTP_USERNAME=your.email@gmail.com',
        'SMTP_PASSWORD=your-app-password-here',
        'EMAIL_FROM_NAME=Vicky Kumar',
        "",
        "# ===== OLLAMA =====",
        "OLLAMA_HOST=http://localhost:11434",
        "OLLAMA_MODEL=llama3.2:3b",
        "OLLAMA_TIMEOUT=60",
        "",
        "# ===== PROFILE =====",
        'YOUR_NAME=Vicky Kumar',
        'YOUR_TITLE=AI Engineer',
        'YOUR_SKILLS=Python,FastAPI,PyTorch,React,TypeScript,LangChain,Docker,PostgreSQL',
        'YOUR_EXPERIENCE_YEARS=2',
        'YOUR_LOCATION=San Francisco, CA',
        'YOUR_LINKEDIN=https://linkedin.com/in/your-profile',
        'YOUR_GITHUB=https://github.com/your-username',
        'YOUR_PORTFOLIO=https://your-portfolio.dev',
        'YOUR_RESUME=data/resume.pdf',
        'GITHUB_TOKEN=',
        "",
        "# ===== JOB PREFERENCES =====",
        'TARGET_ROLES=AI Engineer,Machine Learning Engineer,Backend Engineer',
        'PREFERRED_COMPANY_STAGES=seed,series-a,series-b',
        'PREFERRED_COMPANY_SIZES=1-50,51-200',
        'PREFERRED_LOCATIONS=San Francisco,Remote,New York',
        'MIN_SALARY=100000',
        'MAX_COMMUTE_MILES=20',
        'MIN_EXPERIENCE_YEARS=0',
        'MAX_EXPERIENCE_YEARS=5',
        "",
        "# ===== SCORING =====",
        'APPLY_THRESHOLD=75',
        'APPLY_LATER_THRESHOLD=50',
        'WATCH_THRESHOLD=30',
        "",
        "# ===== RATE LIMITS =====",
        'MAX_EMAILS_PER_DAY=20',
        'MAX_EMAILS_PER_HOUR=5',
        'EMAIL_DELAY_SECONDS=60',
        "",
        "# ===== STORAGE =====",
        'MAX_BACKUPS=30',
        "",
        "# ===== COLLECTORS =====",
        'ENABLED_COLLECTORS=linkedin,ycombinator,wellfound',
        'USER_AGENT=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'REQUEST_TIMEOUT=30',
        'MAX_RETRIES=3',
        'RETRY_DELAY=5',
        'CONCURRENT_COLLECTORS=3',
        'LINKEDIN_MAX_PAGES=5',
        'LINKEDIN_JOBS_PER_PAGE=25',
        'LINKEDIN_SESSION_COOKIE=',
        "",
        "# ===== CIRCUIT BREAKER =====",
        'CIRCUIT_BREAKER_THRESHOLD=5',
        'CIRCUIT_BREAKER_TIMEOUT=300',
        "",
        "# ===== LOGGING =====",
        'LOG_LEVEL=INFO',
        "",
        "# ===== NOTIFICATIONS =====",
        'SEND_COMPLETION_EMAIL=true',
        'NOTIFY_ON_ERRORS=true',
        "",
        "# ===== DEBUG =====",
        'DRY_RUN=false',
        'ENABLE_PLAYWRIGHT=false',
        'SAVE_RAW_HTML=false',
    ]
    path.write_text("\n".join(lines) + "\n")
    return path
