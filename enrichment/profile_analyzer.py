"""Profile analyzer - fetch and analyze GitHub/LinkedIn profiles with caching."""
import httpx
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from datetime import datetime

from observability.logger import get_logger
import config


logger = get_logger(__name__)


REPO_CATEGORIES: Dict[str, List[str]] = {
    "ai-ml": ["ai", "machine-learning", "deep-learning", "llm", "langchain", "rag", "pytorch",
              "tensorflow", "nlp", "computer-vision", "transformer", "neural-network",
              "openai", "gpt", "chatbot", "agent", "fine-tuning", "embedding",
              "retrieval-augmented", "vector-database", "ai-agent", "mlops"],
    "backend": ["backend", "api", "fastapi", "flask", "django", "rest", "graphql",
                "microservice", "database", "postgresql", "redis", "mongodb", "kafka",
                "grpc", "websocket", "server", "celery", "rabbitmq", "sql"],
    "frontend": ["frontend", "react", "vue", "angular", "svelte", "ui", "ux", "css",
                 "tailwind", "typescript", "javascript", "nextjs", "web"],
    "fullstack": ["fullstack", "full-stack", "full stack", "nextjs", "remix", "t3"],
    "data": ["data", "analytics", "dashboard", "visualization", "etl", "data-pipeline",
             "data-engineering", "data-science", "jupyter", "pandas", "numpy", "spark"],
    "devops": ["docker", "kubernetes", "k8s", "ci/cd", "github-actions", "terraform",
               "ansible", "infrastructure", "devops", "deployment", "helm", "monitoring"],
    "mobile": ["mobile", "ios", "android", "flutter", "react-native", "swift", "kotlin"],
    "security": ["security", "authentication", "authorization", "oauth", "jwt", "encryption",
                 "cybersecurity", "penetration-testing"],
    "blockchain": ["blockchain", "web3", "ethereum", "solidity", "smart-contract", "nft",
                   "cryptocurrency", "defi"],
    "cli-tool": ["cli", "command-line", "terminal", "shell", "tool"],
    "game": ["game", "gaming", "unity", "unreal", "pygame", "godot"],
    "documentation": ["docs", "documentation", "wiki", "knowledge-base"],
}

CATEGORY_LABELS: Dict[str, str] = {
    "ai-ml": "AI/ML",
    "backend": "Backend",
    "frontend": "Frontend",
    "fullstack": "Full-Stack",
    "data": "Data Engineering",
    "devops": "DevOps/Infrastructure",
    "mobile": "Mobile",
    "security": "Security",
    "blockchain": "Blockchain/Web3",
    "cli-tool": "CLI/Tooling",
    "game": "Game Development",
    "documentation": "Documentation",
}


class ProfileAnalyzer:
    def __init__(self):
        self.client = httpx.Client(timeout=30, follow_redirects=True)
        self.projects = self._load_projects()
        self.github_data: Optional[Dict[str, Any]] = None
        self._github_cache_file = config.DATA_DIR / "github_cache.json"
        self._cache_ttl = 3600

    def _load_projects(self) -> List[Dict[str, Any]]:
        try:
            pf = Path(__file__).parent.parent / "data" / "projects.json"
            if pf.exists():
                data = json.loads(pf.read_text())
                return data.get("projects", [])
        except Exception as e:
            logger.warning(f"Could not load projects.json: {e}")
        return []

    def _fetch_all_repos(self, username: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        repos = []
        page = 1
        per_page = 100
        while True:
            resp = self.client.get(
                f"https://api.github.com/users/{username}/repos",
                params={"sort": "updated", "per_page": per_page, "page": page},
                headers=headers,
            )
            if resp.status_code != 200:
                break
            page_repos = resp.json()
            if not page_repos:
                break
            repos.extend(page_repos)
            if len(page_repos) < per_page:
                break
            page += 1
        return repos

    def _categorize_repo(self, repo: Dict[str, Any]) -> List[str]:
        desc = (repo.get("description") or "").lower()
        name = repo.get("name", "").lower()
        topics = [t.lower() for t in repo.get("topics", [])]
        lang = (repo.get("language") or "").lower()
        search_text = f"{name} {desc} {' '.join(topics)} {lang}"

        matched_categories: List[str] = []
        for cat, keywords in REPO_CATEGORIES.items():
            for kw in keywords:
                if kw in search_text:
                    matched_categories.append(cat)
                    break
        return matched_categories if matched_categories else ["other"]

    def _fetch_repo_topics(self, repo_full_name: str, headers: Dict[str, str]) -> List[str]:
        try:
            resp = self.client.get(
                f"https://api.github.com/repos/{repo_full_name}/topics",
                headers={**headers, "Accept": "application/vnd.github.mercy-preview+json"},
            )
            if resp.status_code == 200:
                return resp.json().get("names", [])
        except Exception:
            pass
        return []

    def analyze_github(self, username: str, force: bool = False) -> Optional[Dict[str, Any]]:
        cached = self._load_github_cache(username)
        if cached and not force:
            self.github_data = cached
            return cached
        try:
            headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": config.USER_AGENT}
            if config.GITHUB_TOKEN:
                headers["Authorization"] = f"token {config.GITHUB_TOKEN}"

            user_resp = self.client.get(f"https://api.github.com/users/{username}", headers=headers)
            if user_resp.status_code != 200:
                logger.warning(f"GitHub API: {user_resp.status_code}")
                return None

            user_data = user_resp.json()
            repos = self._fetch_all_repos(username, headers)

            languages: Set[str] = set()
            total_stars = 0
            total_forks = 0
            category_counts: Dict[str, int] = {}
            categorized_repos: List[Dict[str, Any]] = []

            for repo in repos:
                if repo.get("language"):
                    languages.add(repo["language"])
                total_stars += repo.get("stargazers_count", 0)
                total_forks += repo.get("forks_count", 0)

                repo_full_name = repo.get("full_name", "")
                topics = self._fetch_repo_topics(repo_full_name, headers) if repo_full_name else []
                repo["topics"] = topics

                cats = self._categorize_repo(repo)
                for c in cats:
                    category_counts[c] = category_counts.get(c, 0) + 1

                categorized_repos.append({
                    "name": repo["name"],
                    "description": repo.get("description", ""),
                    "url": repo["html_url"],
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language", ""),
                    "topics": topics,
                    "categories": cats,
                    "fork": repo.get("fork", False),
                })

            category_summary = {}
            for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
                label = CATEGORY_LABELS.get(cat, cat)
                category_summary[cat] = {"label": label, "count": count}

            top_by_category: Dict[str, List[Dict[str, Any]]] = {}
            for cat in category_counts:
                top_by_category[cat] = [
                    r for r in sorted(categorized_repos, key=lambda x: x["stars"], reverse=True)
                    if cat in r["categories"]
                ][:3]

            self.github_data = {
                "username": username,
                "profile_url": f"https://github.com/{username}",
                "public_repos": user_data.get("public_repos", len(repos)),
                "total_stars": total_stars,
                "total_forks": total_forks,
                "languages": sorted(languages),
                "top_repos": [
                    {
                        "name": r["name"],
                        "description": r.get("description", ""),
                        "url": r["html_url"],
                        "stars": r.get("stargazers_count", 0),
                        "language": r.get("language", ""),
                    }
                    for r in sorted(repos, key=lambda x: x.get("stargazers_count", 0), reverse=True)[:5]
                ],
                "category_counts": category_summary,
                "categorized_repos": categorized_repos,
                "top_by_category": top_by_category,
                "analyzed_at": datetime.utcnow().isoformat(),
            }
            self._save_github_cache(self.github_data)
            logger.info(f"GitHub: {len(repos)} repos across {len(category_counts)} categories, {total_stars} stars")
            return self.github_data
        except Exception as e:
            logger.error(f"GitHub analysis failed: {e}")
            return None

    def _load_github_cache(self, username: str) -> Optional[Dict[str, Any]]:
        if not self._github_cache_file.exists():
            return None
        try:
            data = json.loads(self._github_cache_file.read_text())
            if data.get("username") == username:
                cached_at = datetime.fromisoformat(data.get("analyzed_at", ""))
                if (datetime.utcnow() - cached_at).total_seconds() < self._cache_ttl:
                    return data
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None

    def _save_github_cache(self, data: Dict[str, Any]) -> None:
        self._github_cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._github_cache_file.write_text(json.dumps(data, indent=2))

    def get_category_summary(self, max_categories: int = 5) -> str:
        if not self.github_data or "category_counts" not in self.github_data:
            return ""
        cats = self.github_data["category_counts"]
        sorted_cats = sorted(cats.items(), key=lambda x: -x[1]["count"])[:max_categories]
        parts = []
        for cat_id, info in sorted_cats:
            label = info["label"]
            count = info["count"]
            repo_word = "repo" if count == 1 else "repos"
            parts.append(f"{count} {repo_word} in {label}")
        return " | ".join(parts)

    def get_repos_for_category(self, category: str, max_count: int = 3) -> List[Dict[str, Any]]:
        if not self.github_data or "top_by_category" not in self.github_data:
            return []
        return self.github_data["top_by_category"].get(category, [])[:max_count]

    def get_category_relevance_score(self, job_role: str, job_description: str = "") -> Dict[str, float]:
        if not self.github_data or "category_counts" not in self.github_data:
            return {}
        role_lower = job_role.lower()
        desc_lower = job_description.lower()
        search_text = f"{role_lower} {desc_lower}"

        relevance: Dict[str, float] = {}
        for cat_id, info in self.github_data["category_counts"].items():
            label = info["label"].lower()
            keywords = REPO_CATEGORIES.get(cat_id, [])
            score = 0.0
            for kw in keywords:
                if kw in search_text:
                    score += 1.0
            if label in search_text:
                score += 2.0
            relevance[cat_id] = min(score, 10.0)
        return relevance

    def generate_skill_section(self, job_role: str = "", job_description: str = "", max_examples: int = 2) -> str:
        if not self.github_data or "category_counts" not in self.github_data:
            return ""

        relevance = self.get_category_relevance_score(job_role, job_description)
        top_cats = sorted(relevance.items(), key=lambda x: -x[1])[:3]

        lines = []
        for cat_id, _ in top_cats:
            if cat_id not in self.github_data["category_counts"]:
                continue
            info = self.github_data["category_counts"][cat_id]
            label = info["label"]
            count = info["count"]
            repos = self.get_repos_for_category(cat_id, max_count=max_examples)
            if repos:
                repo_names = ", ".join(r["name"] for r in repos)
                lines.append(f"• {label} ({count} repos): {repo_names}")
            else:
                lines.append(f"• {label} ({count} repos)")
        return "\n".join(lines) if lines else ""

    def get_relevant_projects(self, job_role: str, job_description: str = "", max_projects: int = 3) -> List[Dict[str, Any]]:
        if not self.projects:
            return []
        role_keywords = {
            "backend": ["backend", "api", "fastapi", "rest", "database", "postgresql"],
            "frontend": ["frontend", "react", "ui", "ux", "css", "javascript"],
            "fullstack": ["fullstack", "full stack", "react", "fastapi", "api"],
            "ml": ["machine learning", "deep learning", "pytorch", "tensorflow", "cnn"],
            "ai": ["ai", "llm", "langchain", "agent", "rag", "chatbot"],
            "data": ["analytics", "data", "dashboard", "visualization"],
        }
        scored = []
        role_lower = job_role.lower()
        desc_lower = job_description.lower()
        for project in self.projects:
            score = 0
            for rtype, kws in role_keywords.items():
                if rtype in role_lower:
                    for kw in kws:
                        if kw in project.get("category", "").lower() or kw in project.get("description", "").lower():
                            score += 2
                        if any(kw in tech.lower() for tech in project.get("tech_stack", [])):
                            score += 1
            if desc_lower:
                for kw in ["python", "react", "api", "ai", "ml", "backend", "frontend"]:
                    if kw in desc_lower and kw in project.get("description", "").lower():
                        score += 1
            scored.append((score, project))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for s, p in scored[:max_projects] if s > 0]

    def generate_project_highlights(self, relevant_projects: List[Dict[str, Any]]) -> str:
        if not relevant_projects:
            return ""
        lines = []
        for p in relevant_projects:
            lines.append(f"• {p['name']}: {p['description'][:100]}... [{p.get('github_repo', '')}]")
        return "\n".join(lines)

    def get_profile_summary(self) -> str:
        parts = []
        if self.github_data:
            gd = self.github_data
            parts.append(f"{gd['public_repos']} repos with {gd['total_stars']}⭐ and {gd['total_forks']}🍴")
            if gd.get("languages"):
                parts.append(f"Languages: {', '.join(gd['languages'][:5])}")
            if gd.get("category_counts"):
                summary = self.get_category_summary(max_categories=4)
                if summary:
                    parts.append(summary)
        if self.projects:
            cats = set(p.get("category", "") for p in self.projects)
            parts.append(f"Portfolio: {', '.join(list(cats)[:3])}")
        return " | ".join(parts) if parts else ""
