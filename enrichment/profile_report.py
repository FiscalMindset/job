"""Generate comprehensive profile analysis report."""
import json
from pathlib import Path
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ollama
from playwright.sync_api import sync_playwright
import time

from enrichment.profile_analyzer import ProfileAnalyzer
from observability.logger import get_logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.text import Text
from rich import box
import config


logger = get_logger(__name__)
console = Console()


class ProfileReportGenerator:
    """Generate detailed profile analysis reports."""
    
    def __init__(self):
        self.analyzer = ProfileAnalyzer()
        self.github_username = config.YOUR_GITHUB.split('/')[-1] if config.YOUR_GITHUB else None
        self.linkedin_username = config.YOUR_LINKEDIN.split('/')[-2] if config.YOUR_LINKEDIN and '/in/' in config.YOUR_LINKEDIN else None
        self.hiring_keywords = [
            'hiring', 'job opening', 'we are looking for', "we're hiring", 
            'join our team', 'career opportunity', 'now hiring', 'seeking', 
            'job opportunity', 'positions available', 'apply now', 'recruitment'
        ]
    
    def generate_report(self) -> dict:
        """Generate comprehensive profile analysis."""
        # Beautiful header
        header_text = Text()
        header_text.append("━" * 80 + "\n", style="bold cyan")
        header_text.append("     🚀 DEEP PROFILE INTELLIGENCE SYSTEM     \n", style="bold white on blue")
        header_text.append("━" * 80, style="bold cyan")
        console.print(header_text)
        console.print()
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "profile": {
                "name": config.YOUR_NAME,
                "title": config.YOUR_TITLE,
                "experience_years": config.YOUR_EXPERIENCE_YEARS,
                "location": config.YOUR_LOCATION,
                "github": config.YOUR_GITHUB,
                "linkedin": config.YOUR_LINKEDIN,
            },
            "github_analysis": {
                "all_repos": [],
                "languages_breakdown": {},
                "contribution_stats": {},
                "repo_insights": []
            },
            "linkedin_analysis": {
                "posts": [],
                "hiring_opportunities": []
            },
            "projects": [],
            "skills": config.YOUR_SKILLS,
            "target_roles": config.TARGET_ROLES,
        }
        
        # Deep GitHub Analysis
        if self.github_username:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]🔍 Deep diving into GitHub profile...", total=100)
                github_data = self._deep_github_analysis(progress, task)
                report["github_analysis"] = github_data
        
        # Deep LinkedIn Analysis
        if self.linkedin_username:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[yellow]🔍 Analyzing LinkedIn posts and activity...", total=100)
                linkedin_data = self._deep_linkedin_analysis(progress, task)
                report["linkedin_analysis"] = linkedin_data
                
                # Auto-send hiring opportunities
                if linkedin_data.get("hiring_opportunities"):
                    self._auto_send_hiring_alerts(linkedin_data["hiring_opportunities"])
        
        # Load projects
        if self.analyzer.projects:
            report["projects"] = self.analyzer.projects
            self._display_projects_enhanced(self.analyzer.projects)
        
        # Display skills with categories
        self._display_skills_enhanced(config.YOUR_SKILLS)
        
        # Display target roles
        self._display_targets_enhanced()
        
        # Final summary
        console.print()
        summary_panel = Panel(
            "[bold green]✅ PROFILE ANALYSIS COMPLETE[/bold green]\n\n"
            f"📊 GitHub Repos Analyzed: {len(report['github_analysis'].get('all_repos', []))}\n"
            f"💬 LinkedIn Posts Analyzed: {len(report['linkedin_analysis'].get('posts', []))}\n"
            f"🎯 Hiring Opportunities Found: {len(report['linkedin_analysis'].get('hiring_opportunities', []))}\n"
            f"📁 Portfolio Projects: {len(report['projects'])}",
            border_style="bold green",
            box=box.DOUBLE
        )
        console.print(summary_panel)
        console.print()
        
        return report
    
    def _deep_github_analysis(self, progress, task) -> dict:
        """Deep analysis of ALL GitHub repositories."""
        github_data = {
            "all_repos": [],
            "languages_breakdown": {},
            "contribution_stats": {},
            "repo_insights": []
        }
        
        try:
            # Fetch all repos
            progress.update(task, advance=20, description="[cyan]Fetching all repositories...")
            
            console.print(f"[dim]Calling GitHub API for user: {self.github_username}[/dim]")
            
            # Prepare headers with authentication if available
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            
            if config.GITHUB_TOKEN:
                headers["Authorization"] = f"token {config.GITHUB_TOKEN}"
                console.print("[green]✓ Using GitHub authentication token[/green]")
            else:
                console.print("[yellow]⚠️  No GitHub token - rate limited to 60 requests/hour[/yellow]")
                console.print("[dim]Add GITHUB_TOKEN to .env for 5000 requests/hour[/dim]")
            
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(
                    f"https://api.github.com/users/{self.github_username}/repos",
                    params={"per_page": 100, "sort": "updated"},
                    headers=headers
                )
                
                console.print(f"[dim]GitHub API Response Status: {response.status_code}[/dim]")
                
                if response.status_code == 200:
                    all_repos = response.json()
                    console.print(f"[green]✓ Found {len(all_repos)} repositories[/green]")
                    
                    progress.update(task, advance=30, description=f"[cyan]Analyzing {len(all_repos)} repositories...")
                    
                    for idx, repo in enumerate(all_repos):
                        repo_info = {
                            "name": repo["name"],
                            "description": repo.get("description", ""),
                            "url": repo["html_url"],
                            "stars": repo["stargazers_count"],
                            "forks": repo["forks_count"],
                            "language": repo.get("language", "Unknown"),
                            "topics": repo.get("topics", []),
                            "created_at": repo["created_at"],
                            "updated_at": repo["updated_at"],
                            "size": repo["size"]
                        }
                        
                        # Skip README fetching for now (too slow for 92 repos)
                        repo_info["readme_preview"] = None
                        
                        github_data["all_repos"].append(repo_info)
                        
                        # Language breakdown
                        lang = repo.get("language") or "Unknown"
                        github_data["languages_breakdown"][lang] = github_data["languages_breakdown"].get(lang, 0) + 1
                    
                    progress.update(task, advance=30, description="[cyan]Generating AI insights...")
                    
                    # Generate insights with LLM
                    if len(all_repos) > 0:
                        github_data["repo_insights"] = self._generate_repo_insights(all_repos[:10])
                    
                    progress.update(task, advance=20, description="[green]✅ GitHub analysis complete!")
                    
                    # Display results
                    self._display_github_enhanced(github_data)
                else:
                    error_msg = f"GitHub API returned {response.status_code}"
                    console.print(f"[red]✗ {error_msg}[/red]")
                    console.print(f"[dim]Response: {response.text[:200]}[/dim]")
                    logger.error(error_msg)
                    progress.update(task, description=f"[red]❌ {error_msg}")
                    
        except Exception as e:
            logger.error(f"GitHub analysis failed: {e}")
            console.print(f"[red]✗ GitHub analysis error: {e}[/red]")
            progress.update(task, description=f"[red]❌ GitHub analysis failed: {e}")
        
        return github_data
    
    def _deep_linkedin_analysis(self, progress, task) -> dict:
        """Deep analysis of LinkedIn posts and activity using Playwright."""
        linkedin_data = {
            "posts": [],
            "hiring_opportunities": []
        }
        
        try:
            progress.update(task, advance=20, description="[yellow]🌐 Launching browser for LinkedIn...")
            
            console.print(f"[dim]LinkedIn profile: {self.linkedin_username}[/dim]")
            console.print("[yellow]🤖 Using browser automation (Playwright)[/yellow]")
            
            with sync_playwright() as p:
                # Launch browser in headless mode
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                progress.update(task, advance=20, description="[yellow]📄 Loading LinkedIn profile...")
                
                try:
                    # Go to public profile (no login required for basic info)
                    profile_url = f"https://www.linkedin.com/in/{self.linkedin_username}"
                    page.goto(profile_url, wait_until="networkidle", timeout=30000)
                    
                    # Wait a bit for content to load
                    time.sleep(2)
                    
                    progress.update(task, advance=20, description="[yellow]🔍 Extracting profile data...")
                    
                    # Get page content
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    name_elem = soup.find('h1', class_=lambda x: x and 'text-heading' in x)
                    
                    if name_elem:
                        console.print(f"[green]✓ Found profile: {name_elem.get_text(strip=True)}[/green]")
                    
                    # Try to find activity/posts section
                    # Note: LinkedIn's public view is very limited without login
                    activity_section = soup.find('section', class_=lambda x: x and 'activity' in str(x).lower())
                    
                    if activity_section:
                        posts = activity_section.find_all('div', class_=lambda x: x and 'feed' in str(x).lower())
                        console.print(f"[green]✓ Found {len(posts)} activity items[/green]")
                        
                        for idx, post in enumerate(posts[:10]):  # Limit to 10 posts
                            post_text = post.get_text(strip=True)
                            if len(post_text) > 50:  # Filter out empty/short content
                                linkedin_data["posts"].append({
                                    "text": post_text[:500],
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                                
                                # Check for hiring keywords
                                if self._contains_hiring_keywords(post_text):
                                    hiring_post = {
                                        "text": post_text,
                                        "detected_at": datetime.utcnow().isoformat(),
                                        "keywords_found": [kw for kw in self.hiring_keywords if kw.lower() in post_text.lower()]
                                    }
                                    linkedin_data["hiring_opportunities"].append(hiring_post)
                                    console.print("[red]🚨 Hiring opportunity detected![/red]")
                    else:
                        console.print("[yellow]⚠️  No public activity found (may require login)[/yellow]")
                        linkedin_data["posts"].append({
                            "text": "LinkedIn public profiles have limited visibility. For full post analysis:\n1. Posts are only visible when logged in\n2. Consider using LinkedIn API with OAuth\n3. Or export your posts manually from LinkedIn settings\n\nProfile verified but posts require authentication.",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    
                    # Try to get experience section for work history
                    experience_section = soup.find('section', {'id': 'experience'})
                    if experience_section:
                        jobs = experience_section.find_all('li')
                        console.print(f"[green]✓ Found {len(jobs)} work experiences[/green]")
                    
                    progress.update(task, advance=40, description="[green]✅ LinkedIn scraping complete!")
                    
                except Exception as e:
                    logger.error(f"Failed to scrape LinkedIn: {e}")
                    console.print(f"[yellow]⚠️  Limited LinkedIn data: {e}[/yellow]")
                    linkedin_data["posts"].append({
                        "text": f"LinkedIn scraping encountered an issue: {str(e)}\n\nPublic profiles have very limited data. For full access, LinkedIn login or API is required.",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
                finally:
                    browser.close()
            
            # Display results
            self._display_linkedin_enhanced(linkedin_data)
                    
        except Exception as e:
            logger.error(f"LinkedIn analysis failed: {e}")
            console.print(f"[red]❌ LinkedIn analysis error: {e}[/red]")
            progress.update(task, description="[yellow]⚠️  LinkedIn analysis limited")
            linkedin_data["posts"].append({
                "text": f"Browser automation failed: {str(e)}\n\nTo fix:\n1. Ensure Playwright is installed: playwright install chromium\n2. Check browser permissions\n3. Try manual LinkedIn export",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return linkedin_data
    
    def _generate_repo_insights(self, repos: list) -> list:
        """Generate AI insights about repositories."""
        insights = []
        
        try:
            repo_summaries = []
            for repo in repos[:5]:
                repo_summaries.append(
                    f"- {repo['name']}: {repo.get('description', 'No description')} "
                    f"(★{repo['stargazers_count']}, {repo.get('language', 'Unknown')})"
                )
            
            prompt = f"""Analyze these GitHub repositories and provide 3 key insights:

{chr(10).join(repo_summaries)}

Provide insights about:
1. Technical strengths shown
2. Project themes/patterns
3. Areas of expertise

Keep each insight to 1-2 sentences."""
            
            response = ollama.chat(
                model=config.OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            
            insights_text = response["message"]["content"]
            insights = [line.strip() for line in insights_text.split('\n') if line.strip()]
            
        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            insights = ["AI insights unavailable"]
        
        return insights
    
    def _contains_hiring_keywords(self, text: str) -> bool:
        """Check if text contains hiring-related keywords."""
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in self.hiring_keywords)
    
    def _auto_send_hiring_alerts(self, opportunities: list):
        """Auto-send hiring opportunities to user email without approval."""
        if not opportunities:
            return
        
        console.print()
        alert_panel = Panel(
            f"[bold yellow]🚨 HIRING ALERTS DETECTED: {len(opportunities)}[/bold yellow]\n"
            "[bold green]Auto-sending to your email (no approval required)...[/bold green]",
            border_style="bold yellow",
            box=box.DOUBLE
        )
        console.print(alert_panel)
        console.print()
        
        try:
            # Compose email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🚨 {len(opportunities)} Hiring Opportunities Detected from Your Network"
            msg['From'] = config.EMAIL_FROM
            msg['To'] = config.SMTP_USERNAME  # Send to yourself
            
            # HTML email body
            html_body = self._create_hiring_alert_email(opportunities)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
                server.send_message(msg)
            
            console.print("[bold green]✅ Hiring alerts sent to your email![/bold green]\n")
            logger.info(f"Sent {len(opportunities)} hiring alerts to {config.SMTP_USERNAME}")
            
        except Exception as e:
            logger.error(f"Failed to send hiring alerts: {e}")
            console.print(f"[red]❌ Failed to send alerts: {e}[/red]\n")
    
    def _create_hiring_alert_email(self, opportunities: list) -> str:
        """Create HTML email for hiring alerts."""
        opportunities_html = ""
        for idx, opp in enumerate(opportunities, 1):
            keywords = ", ".join(opp["keywords_found"])
            opportunities_html += f"""
            <div style="background: #f8f9fa; border-left: 4px solid #28a745; padding: 15px; margin: 15px 0; border-radius: 5px;">
                <h3 style="color: #28a745; margin-top: 0;">Opportunity #{idx}</h3>
                <p style="color: #333; line-height: 1.6;">{opp['text'][:500]}</p>
                <p style="color: #666; font-size: 0.9em;">
                    <strong>Keywords Detected:</strong> {keywords}<br>
                    <strong>Detected At:</strong> {opp['detected_at']}
                </p>
            </div>
            """
        
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 30px; text-align: center; border-radius: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">🚨 Hiring Opportunities Detected!</h1>
                    <p style="margin: 10px 0 0 0;">From Your LinkedIn Network</p>
                </div>
                
                <div style="padding: 20px 0;">
                    <p style="color: #333; font-size: 16px;">
                        Hi {config.YOUR_NAME},
                    </p>
                    <p style="color: #333; font-size: 16px;">
                        Our AI detected <strong>{len(opportunities)} hiring opportunities</strong> from your LinkedIn posts and network activity!
                    </p>
                    
                    {opportunities_html}
                    
                    <p style="color: #666; margin-top: 30px; font-size: 14px;">
                        🤖 Auto-generated by Job Intelligence Operating System<br>
                        📅 {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _display_github_enhanced(self, github_data: dict):
        """Display enhanced GitHub statistics."""
        console.print()
        console.print(Panel(
            "[bold cyan]📊 GITHUB DEEP ANALYSIS RESULTS[/bold cyan]",
            border_style="bold cyan",
            box=box.DOUBLE
        ))
        console.print()
        
        # Summary table
        summary_table = Table(
            title="📈 Repository Statistics",
            show_header=True,
            header_style="bold magenta",
            border_style="cyan",
            box=box.ROUNDED
        )
        summary_table.add_column("Metric", style="cyan", width=30)
        summary_table.add_column("Value", style="bold green", justify="right")
        
        total_repos = len(github_data["all_repos"])
        total_stars = sum(r["stars"] for r in github_data["all_repos"])
        total_forks = sum(r["forks"] for r in github_data["all_repos"])
        
        summary_table.add_row("Total Repositories", f"🗂️  {total_repos}")
        summary_table.add_row("Total Stars Received", f"⭐ {total_stars}")
        summary_table.add_row("Total Forks", f"🍴 {total_forks}")
        summary_table.add_row("Primary Languages", str(len(github_data["languages_breakdown"])))
        
        console.print(summary_table)
        console.print()
        
        # Language breakdown
        if github_data["languages_breakdown"]:
            lang_table = Table(
                title="💻 Languages Breakdown",
                show_header=True,
                header_style="bold yellow",
                border_style="yellow",
                box=box.ROUNDED
            )
            lang_table.add_column("Language", style="yellow")
            lang_table.add_column("Repos", style="bold green", justify="right")
            lang_table.add_column("Percentage", style="cyan", justify="right")
            
            sorted_langs = sorted(
                github_data["languages_breakdown"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for lang, count in sorted_langs[:10]:
                percentage = (count / total_repos) * 100
                bar = "█" * int(percentage / 5)
                lang_table.add_row(lang, str(count), f"{percentage:.1f}% {bar}")
            
            console.print(lang_table)
            console.print()
        
        # Top repositories
        if github_data["all_repos"]:
            repos_table = Table(
                title="🌟 Top Repositories (by stars)",
                show_header=True,
                header_style="bold blue",
                border_style="blue",
                box=box.ROUNDED,
                expand=True
            )
            repos_table.add_column("Repository", style="bold blue", width=25)
            repos_table.add_column("Description", style="white", width=40)
            repos_table.add_column("⭐", style="yellow", justify="right", width=5)
            repos_table.add_column("Language", style="cyan", width=12)
            
            sorted_repos = sorted(
                github_data["all_repos"],
                key=lambda x: x["stars"],
                reverse=True
            )
            
            for repo in sorted_repos[:10]:
                desc = repo["description"][:37] + "..." if repo["description"] and len(repo["description"]) > 40 else (repo["description"] or "No description")
                repos_table.add_row(
                    f"[link={repo['url']}]{repo['name']}[/link]",
                    desc,
                    str(repo["stars"]),
                    repo["language"]
                )
            
            console.print(repos_table)
            console.print()
        
        # AI Insights
        if github_data["repo_insights"]:
            insights_text = "\n".join([f"  {idx}. {insight}" for idx, insight in enumerate(github_data["repo_insights"], 1)])
            insights_panel = Panel(
                f"[bold white]{insights_text}[/bold white]",
                title="[bold magenta]🤖 AI-Generated Insights[/bold magenta]",
                border_style="magenta",
                box=box.ROUNDED
            )
            console.print(insights_panel)
            console.print()
    
    def _display_linkedin_enhanced(self, linkedin_data: dict):
        """Display enhanced LinkedIn analysis."""
        console.print()
        console.print(Panel(
            "[bold yellow]💼 LINKEDIN DEEP ANALYSIS RESULTS[/bold yellow]",
            border_style="bold yellow",
            box=box.DOUBLE
        ))
        console.print()
        
        # Posts summary
        posts_count = len(linkedin_data["posts"])
        hiring_count = len(linkedin_data["hiring_opportunities"])
        
        summary_table = Table(
            title="📊 Activity Summary",
            show_header=True,
            header_style="bold magenta",
            border_style="yellow",
            box=box.ROUNDED
        )
        summary_table.add_column("Metric", style="yellow", width=30)
        summary_table.add_column("Value", style="bold green", justify="right")
        
        summary_table.add_row("Posts Analyzed", f"💬 {posts_count}")
        summary_table.add_row("Hiring Opportunities Found", f"🎯 {hiring_count}")
        
        console.print(summary_table)
        console.print()
        
        # Hiring opportunities
        if linkedin_data["hiring_opportunities"]:
            console.print("[bold red]🚨 HIRING OPPORTUNITIES DETECTED:[/bold red]")
            console.print()
            
            for idx, opp in enumerate(linkedin_data["hiring_opportunities"], 1):
                keywords_str = ", ".join([f"[yellow]{kw}[/yellow]" for kw in opp["keywords_found"]])
                
                opp_panel = Panel(
                    f"[white]{opp['text'][:400]}...[/white]\n\n"
                    f"[bold]Keywords:[/bold] {keywords_str}",
                    title=f"[bold green]Opportunity #{idx}[/bold green]",
                    border_style="green",
                    box=box.ROUNDED
                )
                console.print(opp_panel)
                console.print()
        
        # Recent posts preview
        if linkedin_data["posts"] and not linkedin_data["hiring_opportunities"]:
            console.print("[bold]📝 Recent Posts Preview:[/bold]")
            for idx, post in enumerate(linkedin_data["posts"][:3], 1):
                console.print(f"\n  [cyan]Post {idx}:[/cyan]")
                console.print(f"  {post['text'][:150]}...")
            console.print()
    
    def _display_projects_enhanced(self, projects: list):
        """Display projects with enhanced styling."""
        console.print()
        console.print(Panel(
            f"[bold blue]📁 PORTFOLIO PROJECTS: {len(projects)}[/bold blue]",
            border_style="bold blue",
            box=box.DOUBLE
        ))
        console.print()
        
        projects_table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
            box=box.ROUNDED,
            expand=True
        )
        projects_table.add_column("Project", style="bold blue", width=25)
        projects_table.add_column("Category", style="cyan", width=15)
        projects_table.add_column("Description", style="white", width=45)
        projects_table.add_column("Tech Stack", style="yellow", width=30)
        
        for project in projects:
            tech = ", ".join(project.get('tech_stack', [])[:3])
            desc = project['description'][:42] + "..." if len(project['description']) > 45 else project['description']
            
            projects_table.add_row(
                f"[link={project['github_repo']}]{project['name']}[/link]",
                project['category'],
                desc,
                tech
            )
        
        console.print(projects_table)
        console.print()
    
    def _display_skills_enhanced(self, skills: list):
        """Display skills with enhanced categorization."""
        console.print()
        console.print(Panel(
            "[bold green]💼 TECHNICAL SKILLS MATRIX[/bold green]",
            border_style="bold green",
            box=box.DOUBLE
        ))
        console.print()
        
        # Categorize skills
        categories = {
            "Backend": ['Python', 'FastAPI', 'Django', 'Flask', 'PostgreSQL', 'MongoDB', 'REST API', 'WebSockets', 'JWT'],
            "Frontend": ['React', 'JavaScript', 'TypeScript', 'HTML', 'CSS', 'Next.js'],
            "AI/ML": ['PyTorch', 'TensorFlow', 'CNN', 'Transformers', 'LangChain', 'LangGraph', 'CrewAI', 'RAG', 'Ollama', 'OpenAI', 'Claude'],
            "DevOps": ['Docker', 'Git', 'CI/CD', 'Azure', 'Vercel']
        }
        
        skills_table = Table(
            show_header=True,
            header_style="bold magenta",
            border_style="green",
            box=box.ROUNDED
        )
        skills_table.add_column("Category", style="bold cyan", width=15)
        skills_table.add_column("Skills", style="white", width=70)
        skills_table.add_column("Count", style="bold green", justify="right")
        
        for category, category_skills in categories.items():
            matched = [s for s in skills if s in category_skills]
            if matched:
                skills_str = ", ".join([f"[yellow]{s}[/yellow]" for s in matched])
                skills_table.add_row(f"{category} 🔧", skills_str, str(len(matched)))
        
        console.print(skills_table)
        console.print()
    
    def _display_targets_enhanced(self):
        """Display target roles with enhanced styling."""
        console.print()
        console.print(Panel(
            "[bold yellow]🎯 TARGET JOB ROLES[/bold yellow]",
            border_style="bold yellow",
            box=box.DOUBLE
        ))
        console.print()
        
        # Create a tree structure
        tree = Tree("💼 [bold]Target Positions[/bold]", guide_style="cyan")
        
        for idx, role in enumerate(config.TARGET_ROLES, 1):
            tree.add(f"[green]{idx}. {role}[/green]")
        
        console.print(tree)
        console.print()
    
    def _display_github_stats(self, github_data: dict):
        """Display GitHub statistics."""
        table = Table(title="GitHub Statistics", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")
        
        table.add_row("Username", github_data["username"])
        table.add_row("Public Repos", str(github_data["public_repos"]))
        table.add_row("Total Stars", str(github_data["total_stars"]))
        table.add_row("Languages", ", ".join(github_data["languages"][:5]))
        
        console.print(table)
        console.print()
        
        # Top repos
        if github_data["top_repos"]:
            console.print("[bold yellow]🌟 Top Repositories:[/bold yellow]")
            for repo in github_data["top_repos"][:3]:
                console.print(f"  • [link={repo['url']}]{repo['name']}[/link] - ⭐ {repo['stars']} stars")
                if repo['description']:
                    console.print(f"    {repo['description'][:80]}...")
            console.print()
    
    def _display_projects(self, projects: list):
        """Display projects."""
        console.print(Panel(
            f"[bold cyan]📁 Portfolio Projects: {len(projects)}[/bold cyan]",
            border_style="cyan"
        ))
        
        for project in projects[:5]:
            tech = ", ".join(project.get('tech_stack', [])[:3]) if 'tech_stack' in project else ""
            console.print(
                f"  • [bold]{project['name']}[/bold] ({project['category']})\n"
                f"    {project['description'][:80]}...\n"
                f"    Tech: {tech}\n"
                f"    [link={project['github_repo']}]{project['github_repo']}[/link]\n"
            )
    
    def _display_skills(self, skills: list):
        """Display skills breakdown."""
        console.print("[bold yellow]💼 Skills:[/bold yellow]")
        
        # Categorize skills
        backend = [s for s in skills if s in ['Python', 'FastAPI', 'PostgreSQL', 'MongoDB', 'Django', 'Flask']]
        frontend = [s for s in skills if s in ['React', 'JavaScript', 'TypeScript', 'HTML', 'CSS', 'Next.js']]
        ai_ml = [s for s in skills if s in ['PyTorch', 'TensorFlow', 'LangChain', 'OpenAI', 'Claude', 'Ollama', 'RAG']]
        
        if backend:
            console.print(f"  Backend: {', '.join(backend)}")
        if frontend:
            console.print(f"  Frontend: {', '.join(frontend)}")
        if ai_ml:
            console.print(f"  AI/ML: {', '.join(ai_ml)}")
        console.print()
    
    def _display_targets(self):
        """Display target job roles."""
        console.print("[bold yellow]🎯 Target Roles:[/bold yellow]")
        for role in config.TARGET_ROLES:
            console.print(f"  • {role}")
        console.print()
    
    def save_report(self, report: dict):
        """Save report to JSON and CSV files."""
        report_dir = Path(__file__).parent.parent / "data"
        enrichment_dir = Path(__file__).parent
        report_dir.mkdir(exist_ok=True)
        
        # Save JSON report
        report_file = report_dir / f"profile_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Profile report saved to {report_file}")
        
        # Save GitHub analysis to CSV
        if report.get("github_analysis") and report["github_analysis"].get("all_repos"):
            import csv
            github_csv = enrichment_dir / f"github_analysis_{datetime.now().strftime('%Y%m%d')}.csv"
            with open(github_csv, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    'name', 'description', 'url', 'stars', 'forks', 'language', 
                    'topics', 'created_at', 'updated_at', 'size'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for repo in report["github_analysis"]["all_repos"]:
                    row = {k: repo.get(k, '') for k in fieldnames}  # Only include fieldnames
                    row['topics'] = ', '.join(repo.get('topics', []))
                    writer.writerow(row)
            console.print(f"[green]✅ GitHub analysis saved to {github_csv}[/green]")
        
        # Save LinkedIn analysis to CSV
        if report.get("linkedin_analysis") and report["linkedin_analysis"].get("posts"):
            import csv
            linkedin_csv = enrichment_dir / f"linkedin_analysis_{datetime.now().strftime('%Y%m%d')}.csv"
            with open(linkedin_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['text', 'timestamp', 'is_hiring', 'keywords'])
                writer.writeheader()
                for post in report["linkedin_analysis"]["posts"]:
                    writer.writerow({
                        'text': post['text'],
                        'timestamp': post['timestamp'],
                        'is_hiring': 'No',
                        'keywords': ''
                    })
                # Add hiring opportunities
                for opp in report["linkedin_analysis"].get("hiring_opportunities", []):
                    writer.writerow({
                        'text': opp['text'],
                        'timestamp': opp['detected_at'],
                        'is_hiring': 'Yes',
                        'keywords': ', '.join(opp['keywords_found'])
                    })
            console.print(f"[green]✅ LinkedIn analysis saved to {linkedin_csv}[/green]")
        
        return report_file
