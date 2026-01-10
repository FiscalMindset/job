"""Profile analyzer - fetch and analyze GitHub/LinkedIn profiles."""
import httpx
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from observability.logger import get_logger
import config


logger = get_logger(__name__)


class ProfileAnalyzer:
    """
    Analyze user's GitHub and LinkedIn profiles to enhance email personalization.
    
    Features:
    - Fetch GitHub repos, stars, languages
    - Load project portfolio from JSON
    - Generate relevant project highlights based on job requirements
    """
    
    def __init__(self):
        self.client = httpx.Client(timeout=30)
        self.projects = self._load_projects()
        self.github_data = None
    
    def _load_projects(self) -> List[Dict[str, Any]]:
        """Load projects from JSON file."""
        try:
            projects_file = Path(__file__).parent.parent / "data" / "projects.json"
            if projects_file.exists():
                with open(projects_file, 'r') as f:
                    data = json.load(f)
                    return data.get("projects", [])
        except Exception as e:
            logger.warning(f"Could not load projects.json: {e}")
        return []
    
    def analyze_github(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Fetch GitHub profile data.
        
        Returns:
            Dict with repos, stars, languages, etc.
        """
        try:
            # Fetch user profile
            user_response = self.client.get(f"https://api.github.com/users/{username}")
            if user_response.status_code != 200:
                logger.warning(f"GitHub API error: {user_response.status_code}")
                return None
            
            user_data = user_response.json()
            
            # Fetch repositories
            repos_response = self.client.get(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10")
            repos = repos_response.json() if repos_response.status_code == 200 else []
            
            # Extract languages
            languages = set()
            total_stars = 0
            for repo in repos:
                if repo.get('language'):
                    languages.add(repo['language'])
                total_stars += repo.get('stargazers_count', 0)
            
            self.github_data = {
                "username": username,
                "profile_url": f"https://github.com/{username}",
                "public_repos": user_data.get('public_repos', 0),
                "total_stars": total_stars,
                "languages": list(languages),
                "top_repos": [
                    {
                        "name": repo['name'],
                        "description": repo.get('description', ''),
                        "url": repo['html_url'],
                        "stars": repo.get('stargazers_count', 0),
                        "language": repo.get('language', '')
                    }
                    for repo in sorted(repos, key=lambda r: r.get('stargazers_count', 0), reverse=True)[:5]
                ]
            }
            
            logger.info(f"GitHub analysis complete: {len(repos)} repos, {total_stars} stars")
            return self.github_data
            
        except Exception as e:
            logger.error(f"Failed to analyze GitHub profile: {e}")
            return None
    
    def get_relevant_projects(self, job_role: str, job_description: str = "", max_projects: int = 3) -> List[Dict[str, Any]]:
        """
        Get most relevant projects based on job requirements.
        
        Args:
            job_role: The job title
            job_description: Job description text
            max_projects: Maximum number of projects to return
            
        Returns:
            List of relevant projects
        """
        if not self.projects:
            return []
        
        # Keywords mapping for different roles
        role_keywords = {
            "backend": ["backend", "api", "fastapi", "rest", "database", "postgresql"],
            "frontend": ["frontend", "react", "ui", "ux", "css", "javascript"],
            "fullstack": ["fullstack", "full stack", "react", "fastapi", "api"],
            "ml": ["machine learning", "deep learning", "pytorch", "tensorflow", "cnn"],
            "ai": ["ai", "llm", "langchain", "agent", "rag", "chatbot"],
            "data": ["analytics", "data", "dashboard", "visualization"]
        }
        
        # Score projects based on relevance
        scored_projects = []
        role_lower = job_role.lower()
        desc_lower = job_description.lower()
        
        for project in self.projects:
            score = 0
            
            # Check role keywords
            for role_type, keywords in role_keywords.items():
                if role_type in role_lower:
                    for keyword in keywords:
                        if keyword in project['category'].lower() or keyword in project['description'].lower():
                            score += 2
                        if 'tech_stack' in project:
                            if any(keyword in tech.lower() for tech in project['tech_stack']):
                                score += 1
            
            # Check description keywords
            if desc_lower:
                desc_keywords = ['python', 'react', 'api', 'ai', 'ml', 'backend', 'frontend']
                for keyword in desc_keywords:
                    if keyword in desc_lower and keyword in project['description'].lower():
                        score += 1
            
            scored_projects.append((score, project))
        
        # Sort by score and return top N
        scored_projects.sort(key=lambda x: x[0], reverse=True)
        return [project for score, project in scored_projects[:max_projects] if score > 0]
    
    def generate_project_highlights(self, relevant_projects: List[Dict[str, Any]]) -> str:
        """Generate a formatted string of project highlights for email."""
        if not relevant_projects:
            return ""
        
        highlights = []
        for project in relevant_projects:
            tech = ", ".join(project.get('tech_stack', [])[:3]) if 'tech_stack' in project else ""
            highlights.append(
                f"• {project['name']}: {project['description'][:100]}... "
                f"[{project['github_repo']}]"
            )
        
        return "\n".join(highlights)
    
    def get_profile_summary(self) -> str:
        """Get a brief profile summary for emails."""
        summary_parts = []
        
        if self.github_data:
            summary_parts.append(
                f"{self.github_data['public_repos']} public repositories with "
                f"{self.github_data['total_stars']} total stars"
            )
            if self.github_data['languages']:
                langs = ", ".join(self.github_data['languages'][:5])
                summary_parts.append(f"Primary languages: {langs}")
        
        if self.projects:
            categories = set(p['category'] for p in self.projects)
            summary_parts.append(f"Portfolio includes: {', '.join(list(categories)[:3])}")
        
        return " | ".join(summary_parts) if summary_parts else ""
