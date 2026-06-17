"""Decision maker - combines rules and LLM reasoning with confidence scoring."""
from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.models import Job, Decision
from intelligence.scorer import JobScorer
from intelligence.llm import OllamaClient
from observability.logger import get_logger
import config


logger = get_logger(__name__)


@dataclass
class DecisionContext:
    score: int
    rule_reason: str
    llm_used: bool = False
    llm_adjustment: int = 0
    llm_reason: str = ""
    confidence: float = 1.0


class JobDecider:
    LLM_AMBIGUITY_RANGE = (30, 70)
    LLM_BOOST = 10
    LLM_PENALTY = -10

    def __init__(self, use_llm: bool = True):
        self.scorer = JobScorer()
        self.use_llm = use_llm
        self.llm: Optional[OllamaClient] = None

        if use_llm:
            try:
                self.llm = OllamaClient()
                if not self.llm.is_available:
                    logger.warning("LLM unavailable, using rules only")
                    self.use_llm = False
            except Exception as e:
                logger.warning(f"LLM init failed, rules only: {e}")
                self.use_llm = False

    def decide(self, job: Job) -> None:
        ctx = self._score_and_reason(job)
        job.score = ctx.score
        job.reason = ctx.reason
        if ctx.llm_used and ctx.confidence > 0.3:
            job.llm_analysis = {
                "used": True,
                "adjustment": ctx.llm_adjustment,
                "reason": ctx.llm_reason,
                "confidence": ctx.confidence,
            }
        job.decision = self._score_to_decision(ctx.score)
        logger.debug(f"{job.company} - {job.role}: {job.decision.value} (score={ctx.score}, conf={ctx.confidence:.2f})")

    def decide_with_context(self, job: Job) -> DecisionContext:
        ctx = self._score_and_reason(job)
        job.score = ctx.score
        job.reason = ctx.reason
        job.decision = self._score_to_decision(ctx.score)
        return ctx

    def _score_and_reason(self, job: Job) -> DecisionContext:
        score, reason = self.scorer.score(job)
        ctx = DecisionContext(score=score, rule_reason=reason)

        if self.use_llm and self.llm and self._needs_llm_analysis(score):
            llm_result = self._analyze_with_llm(job)
            if llm_result:
                ctx.llm_used = True
                adj = llm_result.get("score_adjustment", 0)
                if llm_result.get("suitable") is False and adj >= 0:
                    adj = self.LLM_PENALTY
                elif llm_result.get("suitable") is True and adj <= 0:
                    adj = self.LLM_BOOST
                ctx.llm_adjustment = adj
                ctx.llm_reason = llm_result.get("reason", "")
                ctx.score = max(0, min(100, score + adj))
                ctx.reason = f"{reason} | LLM: {ctx.llm_reason}"

        ctx.confidence = self._calculate_confidence(ctx.score, ctx.llm_used)
        return ctx

    def _needs_llm_analysis(self, score: int) -> bool:
        ambiguous = self.LLM_AMBIGUITY_RANGE[0] <= score <= self.LLM_AMBIGUITY_RANGE[1]
        near_threshold = abs(score - config.APPLY_THRESHOLD) <= 10 or abs(score - config.WATCH_THRESHOLD) <= 10
        return ambiguous or near_threshold

    def _analyze_with_llm(self, job: Job) -> Optional[Dict[str, Any]]:
        try:
            return self.llm.analyze_job_description(job)
        except Exception as e:
            logger.error(f"LLM analysis failed for {job.job_id}: {e}")
            return None

    def _score_to_decision(self, score: int) -> Decision:
        if score >= config.APPLY_THRESHOLD:
            return Decision.APPLY
        if score >= config.APPLY_LATER_THRESHOLD:
            return Decision.APPLY_LATER
        if score >= config.WATCH_THRESHOLD:
            return Decision.WATCH
        return Decision.SKIP

    def _calculate_confidence(self, score: int, llm_used: bool) -> float:
        far_from_boundary = max(
            abs(score - config.APPLY_THRESHOLD),
            abs(score - config.APPLY_LATER_THRESHOLD),
            abs(score - config.WATCH_THRESHOLD),
        )
        if far_from_boundary >= 25:
            base = 0.95
        elif far_from_boundary >= 15:
            base = 0.85
        elif far_from_boundary >= 5:
            base = 0.70
        else:
            base = 0.55
        return min(1.0, base + (0.1 if llm_used else 0.0))
