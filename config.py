"""Configuration management for Job Intelligence OS."""
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ===== PATHS =====
BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", DATA_DIR / "backups"))
LOG_DIR = BASE_DIR / "logs"

# Create directories
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

CSV_FILE = Path(os.getenv("CSV_FILE", DATA_DIR / "jobs.csv"))
SQLITE_FILE = Path(os.getenv("SQLITE_FILE", DATA_DIR / "jobs.db"))

# ===== GMAIL SMTP =====
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USERNAME)
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Job Seeker")

# ===== OLLAMA =====
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))

# ===== PERSONAL PROFILE =====
YOUR_NAME = os.getenv("YOUR_NAME", "")
YOUR_TITLE = os.getenv("YOUR_TITLE", "")
YOUR_SKILLS = os.getenv("YOUR_SKILLS", "").split(",")
YOUR_EXPERIENCE_YEARS = int(os.getenv("YOUR_EXPERIENCE_YEARS", "0"))
YOUR_LOCATION = os.getenv("YOUR_LOCATION", "")
YOUR_LINKEDIN = os.getenv("YOUR_LINKEDIN", "")
YOUR_GITHUB = os.getenv("YOUR_GITHUB", "")
YOUR_PORTFOLIO = os.getenv("YOUR_PORTFOLIO", "")
YOUR_RESUME = os.getenv("YOUR_RESUME", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # For higher API rate limits

# ===== JOB PREFERENCES =====
TARGET_ROLES = [r.strip() for r in os.getenv("TARGET_ROLES", "").split(",")]
PREFERRED_COMPANY_STAGES = [s.strip() for s in os.getenv("PREFERRED_COMPANY_STAGES", "").split(",")]
PREFERRED_COMPANY_SIZES = [s.strip() for s in os.getenv("PREFERRED_COMPANY_SIZES", "").split(",")]
PREFERRED_LOCATIONS = [l.strip() for l in os.getenv("PREFERRED_LOCATIONS", "").split(",")]
MIN_SALARY = int(os.getenv("MIN_SALARY", "0"))
MAX_COMMUTE_MILES = int(os.getenv("MAX_COMMUTE_MILES", "20"))
MIN_EXPERIENCE_YEARS = int(os.getenv("MIN_EXPERIENCE_YEARS", "0"))
MAX_EXPERIENCE_YEARS = int(os.getenv("MAX_EXPERIENCE_YEARS", "2"))

# ===== DECISION THRESHOLDS =====
APPLY_THRESHOLD = int(os.getenv("APPLY_THRESHOLD", "75"))
APPLY_LATER_THRESHOLD = int(os.getenv("APPLY_LATER_THRESHOLD", "50"))
WATCH_THRESHOLD = int(os.getenv("WATCH_THRESHOLD", "30"))

# ===== RATE LIMITS =====
MAX_EMAILS_PER_DAY = int(os.getenv("MAX_EMAILS_PER_DAY", "20"))
MAX_EMAILS_PER_HOUR = int(os.getenv("MAX_EMAILS_PER_HOUR", "5"))
EMAIL_DELAY_SECONDS = int(os.getenv("EMAIL_DELAY_SECONDS", "60"))

# ===== STORAGE =====
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "30"))

# ===== COLLECTORS =====
ENABLED_COLLECTORS = [c.strip() for c in os.getenv("ENABLED_COLLECTORS", "").split(",") if c.strip()]
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

# LinkedIn specific
LINKEDIN_MAX_PAGES = int(os.getenv("LINKEDIN_MAX_PAGES", "5"))
LINKEDIN_JOBS_PER_PAGE = int(os.getenv("LINKEDIN_JOBS_PER_PAGE", "25"))

# ===== CIRCUIT BREAKER =====
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "300"))

# ===== LINKEDIN =====
LINKEDIN_SESSION_COOKIE = os.getenv("LINKEDIN_SESSION_COOKIE", "")

# ===== LOGGING =====
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = Path(os.getenv("LOG_FILE", LOG_DIR / "jobctl.log"))
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))


# ===== NOTIFICATIONS =====
SEND_COMPLETION_EMAIL = os.getenv("SEND_COMPLETION_EMAIL", "true").lower() == "true"
NOTIFY_ON_ERRORS = os.getenv("NOTIFY_ON_ERRORS", "true").lower() == "true"
# ===== DEBUGGING =====
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
ENABLE_PLAYWRIGHT = os.getenv("ENABLE_PLAYWRIGHT", "false").lower() == "true"
SAVE_RAW_HTML = os.getenv("SAVE_RAW_HTML", "false").lower() == "true"


def validate_config() -> List[str]:
    """Validate configuration and return list of errors."""
    errors = []
    
    if not SMTP_USERNAME:
        errors.append("SMTP_USERNAME is required")
    if not SMTP_PASSWORD:
        errors.append("SMTP_PASSWORD is required (use Gmail app password)")
    if not YOUR_NAME:
        errors.append("YOUR_NAME is required")
    if not YOUR_SKILLS:
        errors.append("YOUR_SKILLS is required")
    if not TARGET_ROLES:
        errors.append("TARGET_ROLES is required")
    
    return errors
