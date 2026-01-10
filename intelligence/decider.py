"""Decision maker - combines rules and LLM reasoning."""
from core.models import Job, Decision
from intelligence.scorer import JobScorer
from intelligence.llm import OllamaClient
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class JobDecider:
    """
    Makes final application decisions.
    
    Decision hierarchy:
    1. Rule-based scoring (fast, deterministic)
    2. LLM analysis (only when needed)
    3. Final decision based on thresholds
    
    Philosophy:
    - Rules handle 80% of cases
    - LLM handles edge cases and ambiguity
    - Every decision must have a clear reason
    """
    
    def __init__(self, use_llm: bool = True):
        self.scorer = JobScorer()
        self.use_llm = use_llm
        
        if use_llm:
            try:
                self.llm = OllamaClient()
            except Exception as e:
                logger.warning(f"LLM unavailable, using rules only: {e}")
                self.use_llm = False
    
    def decide(self, job: Job) -> None:
        """
        Make application decision and update job in-place.
        
        Modifies job.score, job.decision, job.reason
        """
        # Step 1: Rule-based scoring
        score, reason = self.scorer.score(job)
        job.score = score
        job.reason = reason
        
        # Step 2: LLM analysis for edge cases
        if self.use_llm and self._needs_llm_analysis(score):
            llm_analysis = self._analyze_with_llm(job)
            
            if llm_analysis:
                # Adjust score based on LLM feedback
                job.llm_analysis = llm_analysis
                
                if llm_analysis.get("suitable") is False:
                    # LLM says no - reduce score
                    score = min(score, config.WATCH_THRESHOLD - 1)
                    job.score = score
                    job.reason += f" | LLM: {llm_analysis.get('reason', 'Not suitable')}"
                
                elif llm_analysis.get("suitable") is True:
                    # LLM says yes - boost score slightly
                    score = min(score + 10, 100)
                    job.score = score
                    job.reason += f" | LLM: {llm_analysis.get('reason', 'Good fit')}"
        
        # Step 3: Final decision based on thresholds
        job.decision = self._score_to_decision(score)
        
        logger.debug(
            f"{job.company} - {job.role}: "
            f"{job.decision.value} (score={score}) - {job.reason}"
        )
    
    def _needs_llm_analysis(self, score: int) -> bool:
        """
        Determine if LLM analysis is needed.
        
        Use LLM for:
        - Scores in the ambiguous range (40-60)
        - Jobs on the edge of thresholds
        """
        # In the "maybe" zone
        if config.WATCH_THRESHOLD <= score < config.APPLY_THRESHOLD:
            return True
        
        # Close to APPLY threshold
        if abs(score - config.APPLY_THRESHOLD) <= 5:
            return True
        
        return False
    
    def _analyze_with_llm(self, job: Job) -> dict:
        """Run LLM analysis on job."""
        try:
            return self.llm.analyze_job_description(job)
        except Exception as e:
            logger.error(f"LLM analysis failed for {job.job_id}: {e}")
            return {}
    
    def _score_to_decision(self, score: int) -> Decision:
        """Convert score to decision."""
        if score >= config.APPLY_THRESHOLD:
            return Decision.APPLY
        elif score >= config.APPLY_LATER_THRESHOLD:
            return Decision.APPLY_LATER
        elif score >= config.WATCH_THRESHOLD:
            return Decision.WATCH
        else:
            return Decision.SKIP
