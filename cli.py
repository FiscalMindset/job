"""CLI interface using typer."""
import typer
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich import box
from datetime import datetime, timedelta
from pathlib import Path
import shutil

from core.engine import JobEngine
from core.models import Decision
from collectors.linkedin import LinkedInCollector
from collectors.ycombinator import YCombinatorCollector
from collectors.wellfound import WellfoundCollector
from collectors.github import GitHubCollector
from collectors.naukri import NaukriCollector
from intelligence.decider import JobDecider
from enrichment.email_finder import EmailFinder
from enrichment.profile_report import ProfileReportGenerator
from outreach.sender import EmailSender
from storage.csv_store import CSVStore
from storage.sqlite_store import SQLiteStore
from observability.logger import setup_logging, get_logger
from observability.metrics import Metrics
import config


app = typer.Typer(help="Job Intelligence Operating System - Autonomous job application automation")
console = Console()
logger = get_logger(__name__)


def _init_engine(dry_run: bool = False) -> JobEngine:
    """Initialize the job engine with all components."""
    # Collectors
    collectors = []
    
    if "linkedin" in config.ENABLED_COLLECTORS:
        collectors.append(LinkedInCollector())
    if "ycombinator" in config.ENABLED_COLLECTORS:
        collectors.append(YCombinatorCollector())
    if "wellfound" in config.ENABLED_COLLECTORS or "angellist" in config.ENABLED_COLLECTORS:
        collectors.append(WellfoundCollector())
    if "github" in config.ENABLED_COLLECTORS:
        collectors.append(GitHubCollector())
    if "naukri" in config.ENABLED_COLLECTORS:
        collectors.append(NaukriCollector())
    
    # Intelligence
    decider = JobDecider(use_llm=True)
    
    # Enrichment
    email_finder = EmailFinder()
    
    # Outreach
    email_sender = EmailSender()
    
    # Storage
    csv_store = CSVStore()
    sqlite_store = SQLiteStore()
    
    # Metrics
    metrics = Metrics()
    
    # Engine
    engine = JobEngine(
        collectors=collectors,
        decider=decider,
        email_finder=email_finder,
        email_sender=email_sender,
        csv_store=csv_store,
        sqlite_store=sqlite_store,
        metrics=metrics,
        dry_run=dry_run or config.DRY_RUN
    )
    
    return engine


@app.command()
def run(
    sources: Optional[str] = typer.Option(
        "all",
        "--sources",
        "-s",
        help="Comma-separated list of sources to collect from (or 'all')"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run without sending emails"
    )
):
    """Run the job collection and application pipeline."""
    setup_logging()
    
    # Validate config
    errors = config.validate_config()
    if errors and not dry_run:
        console.print("[red]Configuration errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        console.print("\n[yellow]Run with --dry-run to test without sending emails[/yellow]")
        raise typer.Exit(1)
    
    # Parse sources
    source_list = None
    if sources and sources.lower() != "all":
        source_list = [s.strip() for s in sources.split(",")]
    else:
        # Default to all enabled collectors from .env
        source_list = config.ENABLED_COLLECTORS if config.ENABLED_COLLECTORS else None
    
    # Display header
    console.print("\n" + "="*60)
    console.print("[bold cyan]🚀 Job Intelligence Operating System[/bold cyan]")
    console.print("="*60)
    console.print(f"[yellow]Mode:[/yellow] [bold]{'🔍 DRY RUN' if dry_run else '✅ LIVE'}[/bold]")
    console.print(f"[yellow]Sources:[/yellow] [bold]{sources if sources else 'all enabled'}[/bold]")
    console.print("="*60 + "\n")
    
    # Generate and display profile analysis
    profile_gen = ProfileReportGenerator()
    profile_report = profile_gen.generate_report()
    profile_gen.save_report(profile_report)
    
    # Run pipeline
    engine = _init_engine(dry_run=dry_run)
    result = engine.run(sources=source_list)
    
    # Display results in a beautiful table
    console.print("\n" + "="*60)
    console.print("[bold green]✨ Pipeline Complete![/bold green]")
    console.print("="*60 + "\n")
    
    # Create results table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")
    
    table.add_row("⏱️  Duration", f"{result.duration_seconds:.1f}s")
    table.add_row("📥 Jobs Collected", str(result.jobs_collected))
    table.add_row("🔄 After Dedup", str(result.jobs_deduplicated))
    table.add_row("✉️  Enriched", str(result.jobs_enriched))
    table.add_row("📊 Scored", str(result.jobs_scored))
    table.add_row("📧 Emails Sent", str(result.emails_sent))
    
    console.print(table)
    
    # Decisions table
    if result.decisions_made:
        console.print("\n[bold yellow]📋 Decisions:[/bold yellow]")
        dec_table = Table(show_header=False)
        dec_table.add_column("Decision", style="yellow")
        dec_table.add_column("Count", justify="right", style="white")
        
        for decision, count in result.decisions_made.items():
            emoji = {"APPLY": "✅", "APPLY_LATER": "⏰", "WATCH": "👀", "SKIP": "⏭️ "}.get(decision.value, "")
            dec_table.add_row(f"{emoji} {decision.value}", str(count))
        
        console.print(dec_table)
    
    # Sources table
    if result.source_stats:
        console.print("\n[bold cyan]📍 Sources:[/bold cyan]")
        src_table = Table(show_header=False)
        src_table.add_column("Source", style="cyan")
        src_table.add_column("Jobs", justify="right", style="white")
        
        for source, count in result.source_stats.items():
            src_table.add_row(source, str(count))
        
        console.print(src_table)
    
    console.print()
    
    # Display detailed job analysis
    if result.all_jobs:
        _display_detailed_job_report(result.all_jobs)
    
    # Backup CSV
    csv_store = CSVStore()
    backup_file = csv_store.backup()
    if backup_file:
        console.print(f"\n[dim]Backup created: {backup_file}[/dim]")


def _display_detailed_job_report(jobs: list):
    """Display comprehensive job analysis with companies, skills, locations."""
    from collections import Counter
    import re
    
    console.print("\n" + "="*80)
    console.print("[bold magenta]📊 DETAILED JOB ANALYSIS REPORT[/bold magenta]")
    console.print("="*80 + "\n")
    
    # 1. ALL JOBS LIST
    console.print("[bold cyan]📋 ALL JOBS FOUND ({} total)[/bold cyan]\n".format(len(jobs)))
    
    jobs_table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
    jobs_table.add_column("#", style="dim", width=4)
    jobs_table.add_column("Company", style="cyan", width=20)
    jobs_table.add_column("Role", style="yellow", width=30)
    jobs_table.add_column("Location", style="green", width=15)
    jobs_table.add_column("Score", justify="right", style="magenta", width=6)
    jobs_table.add_column("Decision", style="white", width=10)
    
    for idx, job in enumerate(jobs[:50], 1):  # Show first 50
        score_color = "green" if job.score >= 75 else "yellow" if job.score >= 50 else "red"
        decision_emoji = {"APPLY": "✅", "APPLY_LATER": "⏰", "WATCH": "👀", "SKIP": "⏭️"}.get(job.decision.value, "")
        
        jobs_table.add_row(
            str(idx),
            job.company[:20],
            job.role[:30],
            job.location[:15],
            f"[{score_color}]{job.score}[/{score_color}]",
            f"{decision_emoji} {job.decision.value[:4]}"
        )
    
    console.print(jobs_table)
    
    if len(jobs) > 50:
        console.print(f"\n[dim]... and {len(jobs) - 50} more jobs (see CSV for full list)[/dim]\n")
    
    # 2. COMPANY BREAKDOWN
    company_counts = Counter([job.company for job in jobs])
    console.print("\n[bold cyan]🏢 COMPANY BREAKDOWN (Top 15)[/bold cyan]\n")
    
    company_table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
    company_table.add_column("Rank", justify="right", style="dim", width=6)
    company_table.add_column("Company", style="cyan", width=30)
    company_table.add_column("Jobs", justify="right", style="green", width=10)
    company_table.add_column("% of Total", justify="right", style="yellow", width=12)
    
    for idx, (company, count) in enumerate(company_counts.most_common(15), 1):
        percentage = (count / len(jobs)) * 100
        company_table.add_row(
            str(idx),
            company[:30],
            str(count),
            f"{percentage:.1f}%"
        )
    
    console.print(company_table)
    console.print(f"\n[bold]Total Unique Companies:[/bold] {len(company_counts)}\n")
    
    # 3. LOCATION BREAKDOWN
    location_counts = Counter([job.location for job in jobs if job.location])
    console.print("\n[bold cyan]📍 LOCATION BREAKDOWN (Top 10)[/bold cyan]\n")
    
    location_table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
    location_table.add_column("Rank", justify="right", style="dim", width=6)
    location_table.add_column("Location", style="green", width=25)
    location_table.add_column("Jobs", justify="right", style="cyan", width=10)
    location_table.add_column("Bar", width=30)
    
    max_loc_count = location_counts.most_common(1)[0][1] if location_counts else 1
    
    for idx, (location, count) in enumerate(location_counts.most_common(10), 1):
        bar_length = int((count / max_loc_count) * 20)
        bar = "█" * bar_length
        location_table.add_row(
            str(idx),
            location[:25],
            str(count),
            f"[cyan]{bar}[/cyan] {count}"
        )
    
    console.print(location_table)
    
    # 4. SKILLS ANALYSIS
    console.print("\n[bold cyan]💻 SKILLS ANALYSIS[/bold cyan]\n")
    
    # Extract skills from job descriptions
    all_skills = []
    skill_keywords = [
        'python', 'javascript', 'java', 'react', 'node', 'angular', 'vue',
        'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'terraform',
        'sql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
        'fastapi', 'django', 'flask', 'express', 'spring',
        'machine learning', 'ml', 'ai', 'deep learning', 'nlp',
        'langchain', 'openai', 'llm', 'rag', 'transformers',
        'git', 'ci/cd', 'jenkins', 'github actions',
        'typescript', 'go', 'rust', 'kotlin', 'swift'
    ]
    
    skill_counts = Counter()
    for job in jobs:
        desc_lower = job.description.lower() if job.description else ""
        for skill in skill_keywords:
            if skill in desc_lower:
                skill_counts[skill] += 1
    
    if skill_counts:
        # Most in-demand skills
        console.print("[bold yellow]🔥 MOST IN-DEMAND SKILLS (Top 15)[/bold yellow]\n")
        
        skill_table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
        skill_table.add_column("Rank", justify="right", style="dim", width=6)
        skill_table.add_column("Skill", style="yellow", width=20)
        skill_table.add_column("Jobs", justify="right", style="green", width=10)
        skill_table.add_column("% of Total", justify="right", style="cyan", width=12)
        skill_table.add_column("Demand", width=25)
        
        max_skill_count = skill_counts.most_common(1)[0][1] if skill_counts else 1
        
        for idx, (skill, count) in enumerate(skill_counts.most_common(15), 1):
            percentage = (count / len(jobs)) * 100
            bar_length = int((count / max_skill_count) * 15)
            bar = "█" * bar_length
            
            skill_table.add_row(
                str(idx),
                skill.title(),
                str(count),
                f"{percentage:.1f}%",
                f"[green]{bar}[/green]"
            )
        
        console.print(skill_table)
        
        # Least common skills
        console.print("\n[bold yellow]📉 LEAST COMMON SKILLS (Bottom 10)[/bold yellow]\n")
        
        least_skill_table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
        least_skill_table.add_column("Skill", style="cyan", width=20)
        least_skill_table.add_column("Jobs", justify="right", style="yellow", width=10)
        
        for skill, count in list(skill_counts.most_common())[-10:]:
            if count > 0:
                least_skill_table.add_row(skill.title(), str(count))
        
        console.print(least_skill_table)
        console.print(f"\n[bold]Total Skills Found:[/bold] {len(skill_counts)}\n")
    else:
        console.print("[yellow]No skill data available[/yellow]\n")
    
    # 5. SCORE DISTRIBUTION
    console.print("\n[bold cyan]📊 SCORE DISTRIBUTION[/bold cyan]\n")
    
    score_ranges = {
        "🔥 Excellent (75-100)": len([j for j in jobs if j.score >= 75]),
        "👍 Good (50-74)": len([j for j in jobs if 50 <= j.score < 75]),
        "⚠️  Fair (25-49)": len([j for j in jobs if 25 <= j.score < 50]),
        "❌ Poor (0-24)": len([j for j in jobs if j.score < 25]),
    }
    
    score_table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
    score_table.add_column("Score Range", style="yellow", width=25)
    score_table.add_column("Jobs", justify="right", style="cyan", width=10)
    score_table.add_column("Percentage", justify="right", style="green", width=12)
    score_table.add_column("Visual", width=30)
    
    for range_name, count in score_ranges.items():
        percentage = (count / len(jobs)) * 100 if jobs else 0
        bar_length = int((count / len(jobs)) * 20) if jobs else 0
        bar = "█" * bar_length
        color = "green" if "Excellent" in range_name else "yellow" if "Good" in range_name else "red"
        
        score_table.add_row(
            range_name,
            str(count),
            f"{percentage:.1f}%",
            f"[{color}]{bar}[/{color}]"
        )
    
    console.print(score_table)
    
    # 6. SUMMARY STATISTICS
    console.print("\n[bold cyan]📈 SUMMARY STATISTICS[/bold cyan]\n")
    
    summary_table = Table(show_header=False, box=box.ROUNDED)
    summary_table.add_column("Metric", style="yellow", width=35)
    summary_table.add_column("Value", style="cyan", width=20)
    
    avg_score = sum(j.score for j in jobs) / len(jobs) if jobs else 0
    remote_jobs = len([j for j in jobs if 'remote' in j.location.lower()])
    with_email = len([j for j in jobs if j.email])
    
    summary_table.add_row("Average Match Score", f"{avg_score:.1f}")
    summary_table.add_row("Remote Jobs", f"{remote_jobs} ({(remote_jobs/len(jobs)*100):.1f}%)")
    summary_table.add_row("Jobs with Email Found", f"{with_email} ({(with_email/len(jobs)*100):.1f}%)")
    summary_table.add_row("Unique Companies", str(len(company_counts)))
    summary_table.add_row("Unique Locations", str(len(location_counts)))
    
    console.print(summary_table)
    console.print()


@app.command()
def status():
    """Show system status and recent activity."""
    setup_logging()
    
    sqlite_store = SQLiteStore()
    stats = sqlite_store.get_stats(days=7)
    
    console.print("\n[bold]System Status (Last 7 Days)[/bold]\n")
    
    # Summary
    console.print(f"Total jobs: {stats['total_jobs']}")
    console.print(f"Emails sent: {stats['emails']['sent']}/{stats['emails']['total']}")
    
    # Decisions
    console.print("\n[bold]Decisions:[/bold]")
    for decision, count in stats['decisions'].items():
        console.print(f"  {decision}: {count}")
    
    # Sources
    console.print("\n[bold]Sources:[/bold]")
    for source, count in stats['sources'].items():
        console.print(f"  {source}: {count}")


@app.command()
def stats(
    last: str = typer.Option(
        "30d",
        "--last",
        "-l",
        help="Time period (e.g., 7d, 30d)"
    )
):
    """Show detailed statistics."""
    setup_logging()
    
    # Parse time period
    if last.endswith('d'):
        days = int(last[:-1])
    else:
        days = 30
    
    sqlite_store = SQLiteStore()
    stats = sqlite_store.get_stats(days=days)
    
    console.print(f"\n[bold]Statistics (Last {days} Days)[/bold]\n")
    
    # Create table
    table = Table(show_header=True)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    
    table.add_row("Total Jobs", str(stats['total_jobs']))
    table.add_row("Emails Sent", f"{stats['emails']['sent']}/{stats['emails']['total']}")
    
    for decision, count in stats['decisions'].items():
        table.add_row(f"  {decision}", str(count))
    
    console.print(table)
    
    # Source breakdown
    console.print("\n[bold]Source Breakdown:[/bold]")
    source_table = Table(show_header=True)
    source_table.add_column("Source")
    source_table.add_column("Jobs", justify="right")
    
    for source, count in stats['sources'].items():
        source_table.add_column(source, str(count))
    
    console.print(source_table)


@app.command()
def audit(
    decision: Optional[str] = typer.Option(
        None,
        "--decision",
        "-d",
        help="Filter by decision (APPLY, APPLY_LATER, WATCH, SKIP)"
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Number of jobs to show"
    )
):
    """Audit job decisions."""
    setup_logging()
    
    sqlite_store = SQLiteStore()
    
    if decision:
        decision_enum = Decision(decision.upper())
        jobs = sqlite_store.get_jobs_by_decision(decision_enum, limit=limit)
    else:
        jobs = sqlite_store.search_jobs(limit=limit)
    
    if not jobs:
        console.print("[yellow]No jobs found[/yellow]")
        return
    
    console.print(f"\n[bold]Job Audit ({len(jobs)} jobs)[/bold]\n")
    
    # Create table
    table = Table(show_header=True)
    table.add_column("Company")
    table.add_column("Role")
    table.add_column("Decision")
    table.add_column("Score", justify="right")
    table.add_column("Reason")
    
    for job in jobs:
        table.add_row(
            job.company,
            job.role[:30],
            job.decision.value,
            str(job.score),
            job.reason[:50]
        )
    
    console.print(table)


@app.command()
def retry(
    failed: bool = typer.Option(
        False,
        "--failed",
        help="Retry failed jobs"
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Number of jobs to retry"
    )
):
    """Retry failed jobs."""
    setup_logging()
    
    if not failed:
        console.print("[yellow]Use --failed to retry failed jobs[/yellow]")
        return
    
    sqlite_store = SQLiteStore()
    failed_jobs = sqlite_store.get_failed_jobs(limit=limit)
    
    if not failed_jobs:
        console.print("[green]No failed jobs to retry[/green]")
        return
    
    console.print(f"\n[bold]Retrying {len(failed_jobs)} failed jobs[/bold]\n")
    
    # TODO: Implement retry logic
    # This would re-run specific jobs through the pipeline
    
    console.print("[yellow]Retry functionality not yet implemented[/yellow]")


@app.command()
def config_check():
    """Validate configuration."""
    errors = config.validate_config()
    
    if errors:
        console.print("\n[red]Configuration errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)
    else:
        console.print("\n[green]Configuration is valid![/green]")
        
        console.print(f"\nTarget roles: {', '.join(config.TARGET_ROLES)}")
        console.print(f"Skills: {', '.join(config.YOUR_SKILLS[:5])}")
        console.print(f"Enabled collectors: {', '.join(config.ENABLED_COLLECTORS)}")
        console.print(f"Email rate limits: {config.MAX_EMAILS_PER_HOUR}/hour, {config.MAX_EMAILS_PER_DAY}/day")


@app.command()
def upload_resume(
    resume_path: str = typer.Argument(..., help="Path to your resume PDF file")
):
    """Upload or update your resume PDF."""
    source_path = Path(resume_path)
    
    # Validate file
    if not source_path.exists():
        console.print(f"[red]Error: File not found: {resume_path}[/red]")
        raise typer.Exit(1)
    
    if source_path.suffix.lower() != '.pdf':
        console.print(f"[red]Error: Resume must be a PDF file[/red]")
        raise typer.Exit(1)
    
    # Copy to project directory
    target_dir = Path(__file__).parent / "data"
    target_dir.mkdir(exist_ok=True)
    target_path = target_dir / "resume.pdf"
    
    shutil.copy2(source_path, target_path)
    
    console.print(f"\n[green]✓ Resume uploaded successfully![/green]")
    console.print(f"Saved to: {target_path}")
    console.print(f"\nUpdate your .env file with:")
    console.print(f"YOUR_RESUME={target_path}")


if __name__ == "__main__":
    app()

