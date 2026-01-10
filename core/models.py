"""Core data models for Job Intelligence OS."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import hashlib
import json


class Decision(str, Enum):
    """Job application decision."""
    APPLY = "APPLY"
    APPLY_LATER = "APPLY_LATER"
    WATCH = "WATCH"
    SKIP = "SKIP"


class JobStatus(str, Enum):
    """Job processing status."""
    NEW = "NEW"
    ENRICHED = "ENRICHED"
    SCORED = "SCORED"
    DECIDED = "DECIDED"
    EMAIL_SENT = "EMAIL_SENT"
    FOLLOW_UP_SENT = "FOLLOW_UP_SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class EmailStatus(str, Enum):
    """Email sending status."""
    NOT_SENT = "NOT_SENT"
    SENT = "SENT"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"


@dataclass
class Job:
    """Core job data model."""
    
    # Identity
    company: str
    role: str
    source: str
    job_url: str
    
    # Optional scraped data
    description: str = ""
    location: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    company_size: str = ""
    company_stage: str = ""
    posted_date: Optional[datetime] = None
    
    # Contact info (populated by enrichment)
    email: str = ""
    email_confidence: float = 0.0
    hiring_manager: str = ""
    
    # Intelligence
    score: int = 0
    decision: Decision = Decision.SKIP
    reason: str = ""
    
    # Tracking
    job_id: str = field(default="", init=False)
    status: JobStatus = JobStatus.NEW
    applied_on: Optional[datetime] = None
    followup_on: Optional[datetime] = None
    email_status: EmailStatus = EmailStatus.NOT_SENT
    attempt_count: int = 0
    
    # Metadata
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_log: str = ""
    
    # LLM response cache
    llm_analysis: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Generate job_id after initialization."""
        if not self.job_id:
            self.job_id = self.generate_id()
    
    def generate_id(self) -> str:
        """Generate deterministic job ID from core fields."""
        # Normalize inputs
        company = self.company.lower().strip()
        role = self.role.lower().strip()
        url = self.job_url.lower().strip()
        
        # Create hash
        content = f"{company}|{role}|{url}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "job_id": self.job_id,
            "company": self.company,
            "role": self.role,
            "source": self.source,
            "job_url": self.job_url,
            "description": self.description,
            "location": self.location,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "company_size": self.company_size,
            "company_stage": self.company_stage,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "email": self.email,
            "email_confidence": self.email_confidence,
            "hiring_manager": self.hiring_manager,
            "score": self.score,
            "decision": self.decision.value,
            "reason": self.reason,
            "status": self.status.value,
            "applied_on": self.applied_on.isoformat() if self.applied_on else None,
            "followup_on": self.followup_on.isoformat() if self.followup_on else None,
            "email_status": self.email_status.value,
            "attempt_count": self.attempt_count,
            "scraped_at": self.scraped_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_log": self.error_log,
            "llm_analysis": json.dumps(self.llm_analysis) if self.llm_analysis else "",
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create Job from dictionary."""
        # Parse datetime fields
        posted_date = None
        if data.get("posted_date"):
            posted_date = datetime.fromisoformat(data["posted_date"])
        
        applied_on = None
        if data.get("applied_on"):
            applied_on = datetime.fromisoformat(data["applied_on"])
        
        followup_on = None
        if data.get("followup_on"):
            followup_on = datetime.fromisoformat(data["followup_on"])
        
        scraped_at = datetime.fromisoformat(data["scraped_at"])
        updated_at = datetime.fromisoformat(data["updated_at"])
        
        # Parse JSON fields
        llm_analysis = {}
        if data.get("llm_analysis"):
            try:
                llm_analysis = json.loads(data["llm_analysis"])
            except json.JSONDecodeError:
                pass
        
        return cls(
            company=data["company"],
            role=data["role"],
            source=data["source"],
            job_url=data["job_url"],
            description=data.get("description", ""),
            location=data.get("location", ""),
            salary_min=data.get("salary_min"),
            salary_max=data.get("salary_max"),
            company_size=data.get("company_size", ""),
            company_stage=data.get("company_stage", ""),
            posted_date=posted_date,
            email=data.get("email", ""),
            email_confidence=float(data.get("email_confidence", 0.0)),
            hiring_manager=data.get("hiring_manager", ""),
            score=int(data.get("score", 0)),
            decision=Decision(data.get("decision", "SKIP")),
            reason=data.get("reason", ""),
            status=JobStatus(data.get("status", "NEW")),
            applied_on=applied_on,
            followup_on=followup_on,
            email_status=EmailStatus(data.get("email_status", "NOT_SENT")),
            attempt_count=int(data.get("attempt_count", 0)),
            scraped_at=scraped_at,
            updated_at=updated_at,
            error_log=data.get("error_log", ""),
            llm_analysis=llm_analysis,
        )


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""
    jobs_collected: int = 0
    jobs_deduplicated: int = 0
    jobs_enriched: int = 0
    jobs_scored: int = 0
    decisions_made: Dict[Decision, int] = field(default_factory=dict)
    emails_sent: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    source_stats: Dict[str, int] = field(default_factory=dict)
    all_jobs: list = field(default_factory=list)  # Store all collected jobs for email details
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Pipeline completed in {self.duration_seconds:.1f}s",
            f"Collected: {self.jobs_collected} jobs",
            f"New after dedup: {self.jobs_deduplicated} jobs",
            f"Enriched: {self.jobs_enriched} jobs",
            f"Scored: {self.jobs_scored} jobs",
            "",
            "Decisions:",
        ]
        
        for decision, count in self.decisions_made.items():
            lines.append(f"  {decision.value}: {count}")
        
        lines.append(f"\nEmails sent: {self.emails_sent}")
        
        if self.errors > 0:
            lines.append(f"Errors: {self.errors}")
        
        if self.source_stats:
            lines.append("\nSources:")
            for source, count in self.source_stats.items():
                lines.append(f"  {source}: {count}")
        
        return "\n".join(lines)
