"""LLM integration for job analysis using Ollama."""
import httpx
import json
from typing import Dict, Any, Optional

from core.models import Job
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class OllamaClient:
    """
    Client for Ollama LLM inference.
    
    Usage philosophy:
    - Use LLMs for understanding, not for filtering
    - Use LLMs for personalization, not for decisions
    - Always have a fallback if LLM fails
    - Cache LLM responses to avoid redundant calls
    """
    
    def __init__(
        self,
        host: str = config.OLLAMA_HOST,
        model: str = config.OLLAMA_MODEL,
        timeout: int = config.OLLAMA_TIMEOUT
    ):
        self.host = host
        self.model = model
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self) -> None:
        """Test if Ollama is available."""
        try:
            response = self.client.get(f"{self.host}/api/tags")
            response.raise_for_status()
            logger.info(f"Ollama connected: {self.host}")
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            logger.error("Make sure Ollama is running: ollama serve")
    
    def generate(self, prompt: str, system: str = "") -> Optional[str]:
        """
        Generate text using Ollama.
        
        Args:
            prompt: User prompt
            system: System prompt (optional)
        
        Returns:
            Generated text or None if failed
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
            }
            
            if system:
                payload["system"] = system
            
            response = self.client.post(
                f"{self.host}/api/generate",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
            
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return None
    
    def analyze_job_description(self, job: Job) -> Dict[str, Any]:
        """
        Analyze job description for ambiguous requirements.
        
        Use case: When rule-based scoring is inconclusive
        """
        if not job.description:
            return {"suitable": False, "reason": "No description"}
        
        system = f"""You are a job analysis assistant. 
Your user is a {config.YOUR_TITLE} with {config.YOUR_EXPERIENCE_YEARS} years experience.
Skills: {', '.join(config.YOUR_SKILLS)}

Analyze if this job is a good fit. Be critical but fair.
Respond in JSON format with keys: suitable (bool), reason (str), concerns (list of str)."""
        
        prompt = f"""Job: {job.role} at {job.company}
Location: {job.location}

Description:
{job.description[:1000]}

Is this a good fit? Be specific about why or why not."""
        
        response = self.generate(prompt, system)
        
        if not response:
            return {"suitable": False, "reason": "LLM failed"}
        
        # Try to parse JSON response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback: extract from text
            return {
                "suitable": "yes" in response.lower() or "good fit" in response.lower(),
                "reason": response[:200],
                "concerns": []
            }
    
    def personalize_email(
        self,
        job: Job,
        template: str,
        hiring_manager: Optional[str] = None
    ) -> str:
        """
        Personalize email template for specific company/role.
        
        Use case: Make emails human and specific, not generic
        """
        system = f"""You are writing a professional job application email.
Your name: {config.YOUR_NAME}
Your title: {config.YOUR_TITLE}
Your background: {config.YOUR_EXPERIENCE_YEARS} years in software engineering

Write a natural, confident email. Reference the specific company and role.
Avoid buzzwords like "excited", "passionate", "thrilled".
Be direct and professional. Keep it under 150 words."""
        
        prompt = f"""Personalize this email template for:

Company: {job.company}
Role: {job.role}
To: {hiring_manager or "Hiring Manager"}

Template:
{template}

Write the complete email. Do not add subject line or signature."""
        
        response = self.generate(prompt, system)
        return response if response else template
    
    def extract_key_requirements(self, description: str) -> list:
        """
        Extract key requirements from job description.
        
        Use case: Understanding what really matters in the role
        """
        system = "Extract the top 5 key requirements from this job description. Return as a bullet list."
        
        prompt = f"Job description:\n{description[:800]}"
        
        response = self.generate(prompt, system)
        
        if not response:
            return []
        
        # Parse bullet points
        lines = [line.strip("- *•") for line in response.split("\n") if line.strip()]
        return lines[:5]
