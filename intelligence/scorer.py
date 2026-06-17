"""Rule-based job scoring with configurable weights and fuzzy matching."""
from datetime import datetime
from typing import Tuple, List
import difflib

from core.models import Job
import config


class JobScorer:
    def __init__(self):
        self.target_roles = [r.lower() for r in config.TARGET_ROLES]
        self.skills = [s.lower().strip() for s in config.YOUR_SKILLS]
        self.preferred_stages = [s.lower() for s in config.PREFERRED_COMPANY_STAGES]
        self.preferred_locations = [loc.lower() for loc in config.PREFERRED_LOCATIONS]
        self.w = config.SCORE_WEIGHTS

        self.role_synonyms = {
            "ai engineer": ["ai engineer", "machine learning engineer", "ml engineer", "ai/ml engineer", "artificial intelligence engineer", "deep learning engineer"],
            "backend engineer": ["backend engineer", "back end engineer", "backend developer", "back-end developer", "server-side engineer", "api engineer"],
            "full stack": ["full stack", "fullstack", "full-stack", "full stack developer", "fullstack engineer"],
            "frontend": ["frontend", "front-end", "front end", "frontend engineer", "ui engineer"],
            "data scientist": ["data scientist", "data engineer", "data analyst", "ml engineer"],
            "devops": ["devops", "devops engineer", "site reliability", "sre", "platform engineer", "infrastructure engineer"],
            "software engineer": ["software engineer", "software developer", "swe", "generalist engineer"],
        }

    def score(self, job: Job) -> Tuple[int, str]:
        score = 0
        reasons: List[str] = []

        role_score, role_reason = self._score_role(job)
        score += role_score
        if role_reason:
            reasons.append(role_reason)

        skills_score, skills_reason = self._score_skills(job)
        score += skills_score
        if skills_reason:
            reasons.append(skills_reason)

        stage_score, stage_reason = self._score_company_stage(job)
        score += stage_score
        if stage_reason:
            reasons.append(stage_reason)

        loc_score, loc_reason = self._score_location(job)
        score += loc_score
        if loc_reason:
            reasons.append(loc_reason)

        recency_score, recency_reason = self._score_recency(job)
        score += recency_score
        if recency_reason:
            reasons.append(recency_reason)

        salary_score, salary_reason = self._score_salary(job)
        score += salary_score
        if salary_reason:
            reasons.append(salary_reason)

        score = max(0, min(100, score))
        reason = "; ".join(reasons) if reasons else "No strong signals"
        return score, reason

    def _score_role(self, job: Job) -> Tuple[int, str]:
        role = job.role.lower()

        for target in self.target_roles:
            if target in role:
                return self.w["role"], f"Role matches target '{target}'"
            for syn_list in self.role_synonyms.values():
                if target in syn_list:
                    for syn in syn_list:
                        if syn in role:
                            ratio = difflib.SequenceMatcher(None, target, syn).ratio()
                            points = int(self.w["role"] * max(0.6, ratio))
                            return points, f"Role similar to '{target}' (matched '{syn}')"

        keywords = ["engineer", "developer", "backend", "fullstack", "frontend", "platform", "infrastructure", "data", "ml", "ai"]
        for kw in keywords:
            if kw in role:
                return int(self.w["role"] * 0.5), f"Role contains '{kw}'"

        return 0, ""

    def _score_skills(self, job: Job) -> Tuple[int, str]:
        if not job.description:
            return 0, ""

        desc = job.description.lower()
        matched_skills: List[str] = []

        for skill in self.skills:
            if skill.lower() in desc:
                matched_skills.append(skill)

        if not matched_skills:
            tech_keywords = ["python", "javascript", "java", "react", "node", "docker", "kubernetes", "aws", "sql", "postgresql", "mongodb", "redis"]
            found = [kw for kw in tech_keywords if kw in desc]
            if len(found) >= 3:
                return int(self.w["skills"] * 0.5), f"{len(found)} tech keywords found (no explicit skill match)"

        ratio = min(len(matched_skills) / max(len(self.skills), 1), 1.0)
        points = int(self.w["skills"] * ratio)
        if points > 0:
            return points, f"{len(matched_skills)}/{len(self.skills)} skills match"
        return 0, ""

    def _score_company_stage(self, job: Job) -> Tuple[int, str]:
        if not job.company_stage:
            return 0, ""
        stage = job.company_stage.lower()
        for preferred in self.preferred_stages:
            if preferred in stage or stage in preferred:
                return self.w["company_stage"], f"Stage: {job.company_stage}"
        return 0, ""

    def _score_location(self, job: Job) -> Tuple[int, str]:
        if not job.location:
            return 0, ""
        location = job.location.lower()
        if "remote" in location or "hybrid" in location:
            return self.w["location"], f"{'Remote' if 'remote' in location else 'Hybrid'} position"
        for preferred in self.preferred_locations:
            if preferred.lower() in location or location in preferred.lower():
                return self.w["location"], f"Location: {job.location}"
        return 0, ""

    def _score_recency(self, job: Job) -> Tuple[int, str]:
        if not job.posted_date:
            return int(self.w["recency"] * 0.3), "Unknown posting date"
        days_old = (datetime.utcnow() - job.posted_date).days
        if days_old <= 3:
            return self.w["recency"], "Posted within 3 days"
        elif days_old <= 7:
            return self.w["recency"] - 3, "Posted within 1 week"
        elif days_old <= 14:
            return int(self.w["recency"] * 0.5), "Posted within 2 weeks"
        elif days_old <= 30:
            return int(self.w["recency"] * 0.3), "Posted within 1 month"
        return 0, f"Posted {days_old} days ago"

    def _score_salary(self, job: Job) -> Tuple[int, str]:
        if job.salary_min is None and job.salary_max is None:
            return int(self.w["salary"] * 0.3), "Salary not specified"
        salary = job.salary_min or job.salary_max or 0
        if salary >= config.MIN_SALARY * 1.5:
            return self.w["salary"], f"Salary ${salary:,} >= 1.5x target"
        elif salary >= config.MIN_SALARY:
            return self.w["salary"], f"Salary ${salary:,} >= ${config.MIN_SALARY:,}"
        elif salary >= config.MIN_SALARY * 0.8:
            return int(self.w["salary"] * 0.5), "Salary close to target"
        return 0, ""

    def score_component_breakdown(self, job: Job) -> dict:
        return {
            "role": self._score_role(job),
            "skills": self._score_skills(job),
            "company_stage": self._score_company_stage(job),
            "location": self._score_location(job),
            "recency": self._score_recency(job),
            "salary": self._score_salary(job),
        }
