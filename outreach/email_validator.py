"""Email validator with regex, DNS MX, and disposable domain detection."""
import re
import dns.resolver
from typing import Tuple, Set

from observability.logger import get_logger


logger = get_logger(__name__)


class EmailValidator:
    INVALID_PATTERNS = [r'noreply@', r'no-reply@', r'donotreply@']

    DISPOSABLE_DOMAINS: Set[str] = set()

    valid_domains_cache: Set[str] = set()
    invalid_domains_cache: Set[str] = set()

    @classmethod
    def _load_disposable(cls) -> None:
        if cls.DISPOSABLE_DOMAINS:
            return
        try:
            resp = __import__("httpx").get(
                "https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/master/disposable_email_blocklist.conf",
                timeout=10,
            )
            if resp.status_code == 200:
                cls.DISPOSABLE_DOMAINS = {d.strip().lower() for d in resp.text.splitlines() if d.strip() and not d.startswith("#")}
                logger.info(f"Loaded {len(cls.DISPOSABLE_DOMAINS)} disposable domains")
        except Exception:
            cls.DISPOSABLE_DOMAINS = {"mailinator.com", "guerrillamail.com", "tempmail.com", "10minutemail.com"}

    @classmethod
    def is_valid(cls, email: str) -> Tuple[bool, str]:
        if not email:
            return False, "Empty email"
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False, "Invalid format"
        for pat in cls.INVALID_PATTERNS:
            if re.match(pat, email, re.IGNORECASE):
                return False, f"Known inactive pattern: {email}"
        domain = email.split("@")[1].lower()
        if domain in cls.invalid_domains_cache:
            return False, "Domain previously failed"
        if domain in cls.valid_domains_cache:
            return True, "Valid (cached)"
        cls._load_disposable()
        if domain in cls.DISPOSABLE_DOMAINS:
            cls.invalid_domains_cache.add(domain)
            return False, f"Disposable domain: {domain}"
        try:
            dns.resolver.resolve(domain, "MX")
            cls.valid_domains_cache.add(domain)
            return True, "MX records found"
        except dns.resolver.NXDOMAIN:
            cls.invalid_domains_cache.add(domain)
            return False, "Domain does not exist"
        except dns.resolver.NoAnswer:
            cls.invalid_domains_cache.add(domain)
            return False, "No MX records"
        except Exception as e:
            logger.warning(f"DNS check failed for {domain}: {e}")
            return True, "Could not verify (allowing)"

    @classmethod
    def add_invalid_pattern(cls, pattern: str) -> None:
        cls.INVALID_PATTERNS.append(pattern)

    @classmethod
    def mark_domain_invalid(cls, domain: str) -> None:
        cls.invalid_domains_cache.add(domain)
        cls.valid_domains_cache.discard(domain)
