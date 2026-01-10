"""Email validator - check if email addresses are valid and reachable."""
import re
import dns.resolver
from typing import Tuple

from observability.logger import get_logger


logger = get_logger(__name__)


class EmailValidator:
    """Validate email addresses before sending."""
    
    # Known invalid patterns
    INVALID_PATTERNS = [
        r'noreply@',
        r'no-reply@',
        r'donotreply@',
    ]
    
    # Company-specific email patterns (use career pages instead)
    CAREER_PAGE_COMPANIES = {
        'stripe.com': 'https://stripe.com/jobs',
        'notion.com': 'https://notion.com/careers',
    }
    
    # Known valid domains (cache)
    valid_domains_cache = set()
    invalid_domains_cache = set()
    
    @classmethod
    def is_valid(cls, email: str) -> Tuple[bool, str]:
        """
        Check if email is valid and deliverable.
        
        Returns:
            (is_valid, reason)
        """
        if not email:
            return False, "Empty email"
        
        # Basic format check
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False, "Invalid email format"
        
        # Check against known invalid patterns
        for pattern in cls.INVALID_PATTERNS:
            if re.match(pattern, email, re.IGNORECASE):
                return False, f"Known inactive email pattern: {email}"
        
        # Extract domain
        domain = email.split('@')[1]
        
        # Check cache
        if domain in cls.invalid_domains_cache:
            return False, f"Domain {domain} previously failed"
        
        if domain in cls.valid_domains_cache:
            return True, "Valid"
        
        # Check MX records
        try:
            dns.resolver.resolve(domain, 'MX')
            cls.valid_domains_cache.add(domain)
            return True, "Valid (MX records found)"
        except dns.resolver.NXDOMAIN:
            cls.invalid_domains_cache.add(domain)
            return False, f"Domain {domain} does not exist"
        except dns.resolver.NoAnswer:
            cls.invalid_domains_cache.add(domain)
            return False, f"No MX records for {domain}"
        except Exception as e:
            logger.warning(f"DNS check failed for {domain}: {e}")
            # Don't cache on error, allow retry
            return True, "Could not verify (allowing)"
    
    @classmethod
    def add_invalid_pattern(cls, pattern: str):
        """Add a pattern to the invalid list."""
        cls.INVALID_PATTERNS.append(pattern)
    
    @classmethod
    def mark_domain_invalid(cls, domain: str):
        """Mark a domain as invalid."""
        cls.invalid_domains_cache.add(domain)
        if domain in cls.valid_domains_cache:
            cls.valid_domains_cache.remove(domain)
