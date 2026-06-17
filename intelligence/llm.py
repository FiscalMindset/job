"""LLM integration for job analysis using Ollama."""
import httpx
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.models import Job
from observability.logger import get_logger
import config


logger = get_logger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    duration_ms: int
    cached: bool = False


class OllamaClient:
    def __init__(
        self,
        host: str = config.OLLAMA_HOST,
        model: str = config.OLLAMA_MODEL,
        timeout: int = config.OLLAMA_TIMEOUT,
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        self._connected = False
        self._response_cache: Dict[str, str] = {}
        self._test_connection()

    def _test_connection(self) -> bool:
        try:
            resp = self.client.get(f"{self.host}/api/tags", timeout=5)
            resp.raise_for_status()
            self._connected = True
            logger.info(f"Ollama connected: {self.host} (model: {self.model})")
            return True
        except Exception as e:
            self._connected = False
            logger.warning(f"Ollama unavailable: {e}")
            return False

    @property
    def is_available(self) -> bool:
        return self._connected

    def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 512,
        use_cache: bool = True,
    ) -> Optional[LLMResponse]:
        if not self._connected:
            return None

        cache_key = f"{system}|{prompt}|{temperature}"
        if use_cache and cache_key in self._response_cache:
            cached = self._response_cache[cache_key]
            return LLMResponse(text=cached, model=self.model, duration_ms=0, cached=True)

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": 0.9,
                    "num_predict": max_tokens,
                },
            }
            if system:
                payload["system"] = system

            t0 = time.time()
            resp = self.client.post(f"{self.host}/api/generate", json=payload)
            resp.raise_for_status()
            elapsed = int((time.time() - t0) * 1000)

            result = resp.json()
            text = result.get("response", "").strip()
            if use_cache and text:
                self._response_cache[cache_key] = text
            return LLMResponse(text=text, model=self.model, duration_ms=elapsed)

        except httpx.TimeoutException:
            logger.warning(f"Ollama timeout ({self.timeout}s)")
            return None
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return None

    def analyze_job_description(self, job: Job) -> Dict[str, Any]:
        if not job.description:
            return {"suitable": False, "reason": "No description available"}

        system = (
            f"You are a job analysis assistant. "
            f"The user is a {config.YOUR_TITLE} with {config.YOUR_EXPERIENCE_YEARS} years experience. "
            f"Skills: {', '.join(config.YOUR_SKILLS)}. "
            f"Analyze if this job is a good fit. Be critical. "
            f"Respond in JSON with keys: suitable (bool), reason (str), concerns (list of str), score_adjustment (int, -20 to +20)."
        )

        prompt = (
            f"Job: {job.role} at {job.company}\n"
            f"Location: {job.location}\n"
            f"Description:\n{job.description[:1200]}\n\n"
            f"Is this a good fit? Provide JSON response."
        )

        response = self.generate(prompt, system, temperature=0.3)
        if not response:
            return {"suitable": False, "reason": "LLM unavailable"}

        try:
            result = json.loads(response.text)
            if "score_adjustment" not in result:
                result["score_adjustment"] = 10 if result.get("suitable") else -10
            return result
        except (json.JSONDecodeError, KeyError):
            return {
                "suitable": "yes" in response.text.lower() or "good fit" in response.text.lower(),
                "reason": response.text[:200],
                "concerns": [],
                "score_adjustment": 0,
            }

    def personalize_email(
        self,
        job: Job,
        template: str,
        hiring_manager: Optional[str] = None,
    ) -> str:
        system = (
            f"You are writing a professional job application email. "
            f"Name: {config.YOUR_NAME}. Title: {config.YOUR_TITLE}. "
            f"Experience: {config.YOUR_EXPERIENCE_YEARS} years. "
            f"Write naturally. Avoid 'excited', 'passionate', 'thrilled'. "
            f"Be direct. Keep under 150 words."
        )
        prompt = (
            f"Personalize this email for:\n"
            f"Company: {job.company}\nRole: {job.role}\n"
            f"To: {hiring_manager or 'Hiring Manager'}\n\n"
            f"Template:\n{template}\n\n"
            f"Write the complete email (no subject line or signature)."
        )
        response = self.generate(prompt, system, temperature=0.8, max_tokens=300)
        return response.text if response else template

    def extract_key_requirements(self, description: str) -> List[str]:
        system = "Extract the top 5 key requirements from this job description as a JSON array of strings."
        prompt = f"Job description:\n{description[:1000]}"
        response = self.generate(prompt, system, temperature=0.2)
        if not response:
            return []
        try:
            return json.loads(response.text)
        except (json.JSONDecodeError, TypeError):
            lines = [line.strip("- *•0123456789. ") for line in response.text.split("\n") if line.strip()]
            return lines[:5]

    def clear_cache(self) -> None:
        self._response_cache.clear()
