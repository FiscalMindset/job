"""Rule-based job scoring - fast, deterministic, explainable."""
from datetime import datetime, timedelta
from typing import Tuple

from core.models import Job
import config


class JobScorer:
    """
    Rule-based job scoring system.
    
    Philosophy:
    - Rules first, LLM second
    - Fast and deterministic
    - Every score has a reason
    - Transparent and debuggable
    
    Score breakdown (max 100):
    - Role match: 0-30 points
    - Skills match: 0-20 points
    - Company stage: 0-15 points
    - Location: 0-10 points
    - Recency: 0-15 points
    - Salary: 0-10 points
    """
    
    def __init__(self):
        self.target_roles = [r.lower() for r in config.TARGET_ROLES]
        self.skills = [s.lower().strip() for s in config.YOUR_SKILLS]
        self.preferred_stages = [s.lower() for s in config.PREFERRED_COMPANY_STAGES]
        self.preferred_locations = [l.lower() for l in config.PREFERRED_LOCATIONS]
    
    def score(self, job: Job) -> Tuple[int, str]:
        """
        Score a job and return (score, reason).
        
        Returns:
            Tuple of (score: int, reason: str)
        """
        score = 0
        reasons = []
        
        # 1. Role match (0-30 points)
        role_score, role_reason = self._score_role(job)
        score += role_score
        if role_reason:
            reasons.append(role_reason)
        
        # 2. Skills match (0-20 points)
        skills_score, skills_reason = self._score_skills(job)
        score += skills_score
        if skills_reason:
            reasons.append(skills_reason)
        
        # 3. Company stage (0-15 points)
        stage_score, stage_reason = self._score_company_stage(job)
        score += stage_score
        if stage_reason:
            reasons.append(stage_reason)
        
        # 4. Location (0-10 points)
        location_score, location_reason = self._score_location(job)
        score += location_score
        if location_reason:
            reasons.append(location_reason)
        
        # 5. Recency (0-15 points)
        recency_score, recency_reason = self._score_recency(job)
        score += recency_score
        if recency_reason:
            reasons.append(recency_reason)
        
        # 6. Salary (0-10 points)
        salary_score, salary_reason = self._score_salary(job)
        score += salary_score
        if salary_reason:
            reasons.append(salary_reason)
        
        # Combine reasons
        reason = "; ".join(reasons) if reasons else "No strong signals"
        
        return score, reason
    
    def _score_role(self, job: Job) -> Tuple[int, str]:
        """Score role match."""
        role = job.role.lower()
        
        # Exact match
        for target in self.target_roles:
            if target in role:
                return 30, f"Role matches '{target}'"
        
        # Partial match (less points)
        keywords = ["engineer", "developer", "backend", "fullstack", "platform"]
        for keyword in keywords:
            if keyword in role:
                return 15, f"Role contains '{keyword}'"
        
        return 0, ""
    
    def _score_skills(self, job: Job) -> Tuple[int, str]:
        """Score skills match from job description."""
        if not job.description:
            return 0, ""
        
        desc = job.description.lower()
        matched_skills = []
        
        for skill in self.skills:
            if skill.lower() in desc:
                matched_skills.append(skill)
        
        if not matched_skills:
            return 0, ""
        
        # More matched skills = higher score
        if len(matched_skills) >= 5:
            return 20, f"{len(matched_skills)} skills match"
        elif len(matched_skills) >= 3:
            return 15, f"{len(matched_skills)} skills match"
        elif len(matched_skills) >= 1:
            return 10, f"{len(matched_skills)} skills match"
        
        return 0, ""
    
    def _score_company_stage(self, job: Job) -> Tuple[int, str]:
        """Score company stage preference."""
        if not job.company_stage:
            return 0, ""
        
        stage = job.company_stage.lower()
        
        for preferred in self.preferred_stages:
            if preferred in stage:
                return 15, f"Company stage: {job.company_stage}"
        
        return 0, ""
    
    def _score_location(self, job: Job) -> Tuple[int, str]:
        """Score location match."""
        if not job.location:
            return 0, ""
        
        location = job.location.lower()
        
        # Remote is always good
        if "remote" in location:
            return 10, "Remote position"
        
        # Check preferred locations
        for preferred in self.preferred_locations:
            if preferred.lower() in location:
                return 10, f"Location: {job.location}"
        
        return 0, ""
    
    def _score_recency(self, job: Job) -> Tuple[int, str]:
        """Score job posting recency."""
        if not job.posted_date:
            return 5, "Unknown posting date"
        
        days_old = (datetime.utcnow() - job.posted_date).days
        
        if days_old <= 3:
            return 15, "Posted within 3 days"
        elif days_old <= 7:
            return 12, "Posted within 1 week"
        elif days_old <= 14:
            return 8, "Posted within 2 weeks"
        elif days_old <= 30:
            return 5, "Posted within 1 month"
        else:
            return 0, f"Posted {days_old} days ago"
    
    def _score_salary(self, job: Job) -> Tuple[int, str]:
        """Score salary range."""
        if not job.salary_min:
            return 0, ""
        
        if job.salary_min >= config.MIN_SALARY:
            return 10, f"Salary >= ${config.MIN_SALARY:,}"
        elif job.salary_min >= config.MIN_SALARY * 0.8:
            return 5, f"Salary close to target"
        
        return 0, ""
