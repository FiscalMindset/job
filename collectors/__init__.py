"""Job collectors."""
from collectors.linkedin import LinkedInCollector
from collectors.ycombinator import YCombinatorCollector
from collectors.wellfound import WellfoundCollector
from collectors.github import GitHubCollector
from collectors.naukri import NaukriCollector


__all__ = [
    "LinkedInCollector",
    "YCombinatorCollector",
    "WellfoundCollector",
    "GitHubCollector",
    "NaukriCollector",
]
