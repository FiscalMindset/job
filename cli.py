"""Interactive CLI with Rich-powered menus, live progress, and wizard."""
import typer
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import box
from pathlib import Path
import shutil
import json

from core.engine import JobEngine
from core.models import Decision, Job
from collectors.linkedin import LinkedInCollector
from collectors.ycombinator import YCombinatorCollector
from collectors.wellfound import WellfoundCollector
from collectors.github import GitHubCollector
from collectors.naukri import NaukriCollector
from intelligence.decider import JobDecider
from enrichment.email_finder import EmailFinder
from enrichment.profile_analyzer import ProfileAnalyzer
from outreach.sender import EmailSender
from storage.csv_store import CSVStore
from storage.sqlite_store import SQLiteStore
from observability.logger import setup_logging, get_logger
from observability.metrics import Metrics
import config


app = typer.Typer(
    name="jobctl",
    help="🤖 Job Intelligence Operating System — Autonomous job application automation",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
logger = get_logger(__name__)

SOURCES: Dict[str, type] = {
    "linkedin": LinkedInCollector,
    "ycombinator": YCombinatorCollector,
    "wellfound": WellfoundCollector,
    "github": GitHubCollector,
    "naukri": NaukriCollector,
}

SOURCE_LABELS = {
    "linkedin": "LinkedIn Jobs",
    "ycombinator": "Y Combinator (Work at a Startup)",
    "wellfound": "Wellfound (AngelList Talent)",
    "github": "GitHub Jobs / Hiring Repos",
    "naukri": "Naukri.com",
}


def _init_engine(dry_run: bool = False, sources: Optional[List[str]] = None) -> JobEngine:
    collectors = []
    for name, cls in SOURCES.items():
        if name in (sources or config.ENABLED_COLLECTORS):
            collectors.append(cls())
    return JobEngine(
        collectors=collectors,
        decider=JobDecider(use_llm=True),
        email_finder=EmailFinder(),
        email_sender=EmailSender(),
        csv_store=CSVStore(),
        sqlite_store=SQLiteStore(),
        metrics=Metrics(),
        dry_run=dry_run or config.DRY_RUN,
    )


# ─── RUN (fully interactive, Claude Code-style) ────────────────────

@app.command()
def run(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip all confirmations (non-interactive)"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate without sending emails"),
    sources: Optional[str] = typer.Option(None, "--sources", "-s", help="Comma-separated sources to use"),
):
    """Run the full pipeline with interactive prompts at every step (Claude Code-style)."""
    setup_logging()

    _show_welcome()

    source_list = _pick_sources_interactive(sources, yes)
    if not source_list:
        console.print("[yellow]No sources selected. Exiting.[/yellow]")
        raise typer.Exit(0)

    mode = _pick_mode(dry_run, yes)

    smtp_account = _pick_smtp_account(yes)
    if smtp_account:
        config.SMTP_USERNAME = smtp_account["username"]
        config.SMTP_PASSWORD = smtp_account["password"]

    errors = config.validate_config()
    if errors:
        console.print("[red]Configuration issues:[/red]")
        for e in errors:
            console.print(f"  • {e}")
        if not mode["dry_run"]:
            if not Confirm.ask("\n[yellow]Continue anyway?[/yellow]", default=False):
                raise typer.Exit(1)

    profile = _analyze_profile(yes)
    _show_pipeline_preview(source_list, mode, profile, smtp_account)

    if not yes and not Confirm.ask("\n[bold green]🚀 Start the pipeline?[/bold green]", default=True):
        console.print("[dim]Cancelled[/dim]")
        raise typer.Exit(0)

    engine = _init_engine(dry_run=mode["dry_run"], sources=source_list)
    engine.phase_callback = _phase_callback

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("[cyan]Pipeline running...", total=None)
        result = engine.run(sources=source_list)

    _show_results(result)
    _show_post_run_prompt(result, yes)


def _show_welcome():
    db = SQLiteStore()
    stats = db.get_stats(days=7) if config.SQLITE_FILE.exists() else None
    console.print(Panel(
        "[bold cyan]🤖 Job Intelligence Operating System[/bold cyan]\n\n"
        "[magenta]Interactive mode[/magenta] — I'll guide you through each step.\n"
        "Use [bold]--yes[/bold] or [bold]-y[/bold] to skip prompts and run headlessly.\n"
        "Press [bold]Ctrl+C[/bold] anytime to cancel.",
        border_style="cyan",
        title="🚀 Welcome",
    ))
    if stats and stats["total_jobs"] > 0:
        console.print(f"  [dim]📊 Last 7 days: {stats['total_jobs']} jobs, {stats.get('avg_score', 'N/A')} avg score[/dim]")
    console.print()


def _pick_sources_interactive(sources: Optional[str], yes: bool) -> List[str]:
    if sources:
        return [s.strip() for s in sources.split(",")]

    if yes:
        return list(config.ENABLED_COLLECTORS)

    console.print("[bold]Select job sources to scrape:[/bold]")
    console.print("  [dim]Toggle with number, or press Enter for all enabled[/dim]\n")

    enabled_defaults = config.ENABLED_COLLECTORS
    source_list = list(SOURCE_LABELS.keys())

    for i, (key, label) in enumerate(SOURCE_LABELS.items(), 1):
        status = "✅ [green]enabled[/green]" if key in enabled_defaults else "❌ [red]disabled[/red]"
        console.print(f"  [{i}] {label:40s} {status}")

    console.print(f"  [{len(source_list)+1}] [bold]All enabled sources[/bold]")
    console.print(f"  [{len(source_list)+2}] [bold]Cancel[/bold]")

    choice = Prompt.ask(
        "\n[bold yellow]Choose sources[/bold yellow]",
        default=str(len(source_list) + 1),
    )

    try:
        idx = int(choice)
        if idx == len(source_list) + 2:
            return []
        if 1 <= idx <= len(source_list):
            return [source_list[idx - 1]]
        return list(enabled_defaults)
    except ValueError:
        return list(enabled_defaults)


def _pick_mode(dry_run: bool, yes: bool) -> Dict[str, Any]:
    if dry_run:
        return {"dry_run": True, "label": "🔍 Dry Run (no emails sent)"}

    if yes:
        return {"dry_run": config.DRY_RUN, "label": "✅ Live (emails will be sent)"}

    console.print("\n[bold]Select mode:[/bold]")
    console.print("  [1] [green]✅ Live[/green] — emails will actually be sent")
    console.print("  [2] [yellow]🔍 Dry Run[/yellow] — simulate only, no emails")
    choice = Prompt.ask("[bold yellow]Mode[/bold yellow]", choices=["1", "2"], default="2")
    is_dry = choice == "2"
    if not is_dry and not Confirm.ask("[bold red]⚠️  LIVE MODE — are you sure?[/bold red]", default=False):
        is_dry = True
    return {"dry_run": is_dry, "label": "🔍 Dry Run" if is_dry else "✅ Live"}


def _pick_smtp_account(yes: bool) -> Optional[Dict[str, str]]:
    accounts_file = config.DATA_DIR / "smtp_accounts.json"
    if not accounts_file.exists():
        return None

    try:
        accounts = json.loads(accounts_file.read_text()).get("accounts", [])
    except (json.JSONDecodeError, KeyError):
        return None

    if not accounts:
        return None

    if yes or len(accounts) == 1:
        return accounts[0]

    console.print("\n[bold]📧 Select email account to send from:[/bold]")
    for i, acct in enumerate(accounts, 1):
        console.print(f"  [{i}] {acct['username']} [dim]({acct.get('label', '')})[/dim]")
    choice = Prompt.ask("[bold yellow]Account[/bold yellow]", default="1")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(accounts):
            return accounts[idx]
    except ValueError:
        pass
    return accounts[0]


def _analyze_profile(yes: bool) -> Optional[Dict[str, Any]]:
    github_username = config.YOUR_GITHUB.split("/")[-1] if config.YOUR_GITHUB else None
    if not github_username:
        return None

    analyzer = ProfileAnalyzer()
    console.print(f"\n[dim]🔍 Analyzing GitHub profile: {github_username}...[/dim]")
    data = analyzer.analyze_github(github_username, force=True)
    if data:
        summary = analyzer.get_category_summary()
        console.print(f"  [green]✓[/green] {data['public_repos']} repos, {data['total_stars']}⭐")
        if summary:
            console.print(f"  [dim]{summary}[/dim]")
    return data


def _show_pipeline_preview(sources: List[str], mode: Dict, profile: Any, smtp_account: Optional[Dict]):
    console.print()
    console.print(Panel(
        f"[bold cyan]Pipeline Preview[/bold cyan]\n\n"
        f"[yellow]Sources:[/yellow] {', '.join(SOURCE_LABELS[s] for s in sources)}\n"
        f"[yellow]Mode:[/yellow] {mode['label']}\n"
        f"[yellow]Email:[/yellow] {smtp_account['username'] if smtp_account else config.SMTP_USERNAME or 'Not configured'}\n"
        f"[yellow]Target Roles:[/yellow] {', '.join(config.TARGET_ROLES)}\n"
        f"[yellow]Profile:[/yellow] {profile.get('public_repos', 'N/A')} repos, {profile.get('total_stars', 0)}⭐" if profile else "",
        border_style="cyan",
    ))


def _show_post_run_prompt(result, yes: bool):
    if result.jobs_deduplicated == 0:
        console.print("\n[dim]No new jobs found. Try adjusting sources or waiting for new listings.[/dim]")
        return

    if yes:
        return

    if Confirm.ask("\n[bold]📊 Show detailed job analysis?[/bold]", default=True):
        _display_detailed_job_report(result.all_jobs)

    apply_jobs = [j for j in result.all_jobs if j.decision == Decision.APPLY]
    if apply_jobs:
        console.print(f"\n[bold green]🎯 {len(apply_jobs)} jobs marked as APPLY[/bold green]")
        if Confirm.ask("Preview their emails?", default=True):
            _preview_apply_emails(apply_jobs)

    if result.errors > 0:
        console.print(f"\n[bold yellow]⚠️  {result.errors} errors occurred[/bold yellow]")
        if Confirm.ask("View error details?", default=False):
            for job in result.all_jobs:
                if job.error_log:
                    console.print(f"[red]{job.company} - {job.role}:[/red] {job.error_log[:200]}")


# ─── PER-SOURCE COMMANDS (quick-launch) ────────────────────────────

@app.command()
def ycombinator(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmations"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate only"),
):
    """Run pipeline for Y Combinator (Work at a Startup) only."""
    _quick_source_run("ycombinator", yes, dry_run)


@app.command()
def linkedin(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmations"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate only"),
):
    """Run pipeline for LinkedIn Jobs only."""
    _quick_source_run("linkedin", yes, dry_run)


@app.command()
def wellfound(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmations"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate only"),
):
    """Run pipeline for Wellfound (AngelList Talent) only."""
    _quick_source_run("wellfound", yes, dry_run)


@app.command()
def github_jobs(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmations"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate only"),
):
    """Run pipeline for GitHub Jobs / Hiring Repos only."""
    _quick_source_run("github", yes, dry_run)


@app.command()
def naukri(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmations"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Simulate only"),
):
    """Run pipeline for Naukri.com only."""
    _quick_source_run("naukri", yes, dry_run)


def _quick_source_run(source: str, yes: bool, dry_run: bool):
    setup_logging()
    console.print(Panel(
        f"[bold cyan]{SOURCE_LABELS.get(source, source)}[/bold cyan]\n"
        "[dim]Quick-launch mode — running a focused single-source pipeline[/dim]",
        border_style="cyan",
    ))

    smtp_account = _pick_smtp_account(yes)
    if smtp_account:
        config.SMTP_USERNAME = smtp_account["username"]
        config.SMTP_PASSWORD = smtp_account["password"]

    errors = config.validate_config()
    if errors and not dry_run:
        console.print("[red]Configuration errors:[/red]")
        for e in errors:
            console.print(f"  • {e}")
        if not Confirm.ask("\n[yellow]Continue anyway?[/yellow]", default=False):
            raise typer.Exit(1)

    engine = _init_engine(dry_run=dry_run, sources=[source])
    if not yes:
        _analyze_profile(yes)

    if not yes and not dry_run:
        if not Confirm.ask(f"\n[bold green]Start {source} pipeline?[/bold green]", default=True):
            raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"[cyan]{source} pipeline...", total=None)
        result = engine.run(sources=[source])

    _show_results(result)


# ─── SMTP ACCOUNTS ──────────────────────────────────────────────────

@app.command()
def smtp():
    """Manage multiple email accounts for sending applications."""
    accounts_file = config.DATA_DIR / "smtp_accounts.json"
    accounts = []
    if accounts_file.exists():
        try:
            accounts = json.loads(accounts_file.read_text()).get("accounts", [])
        except (json.JSONDecodeError, KeyError):
            accounts = []

    while True:
        console.print(Panel("[bold cyan]📧 Email Accounts[/bold cyan]", border_style="cyan"))
        t = Table(box=box.ROUNDED)
        t.add_column("#", style="dim")
        t.add_column("Email", style="cyan")
        t.add_column("Label", style="white")
        t.add_column("Default", justify="center")
        for i, acct in enumerate(accounts, 1):
            is_default = "✅" if i == 1 else ""
            t.add_row(str(i), acct["username"], acct.get("label", ""), is_default)
        if not accounts:
            t.add_row("[dim]—[/dim]", "[dim]No accounts configured[/dim]", "", "")
        console.print(t)

        console.print("\n[bold]Options:[/bold]")
        console.print("  [a] Add new account")
        if accounts:
            console.print("  [d] Delete an account")
            console.print("  [r] Reorder (set default)")
        console.print("  [q] Quit")

        choice = Prompt.ask("[bold yellow]Action[/bold yellow]", choices=["a", "d", "r", "q"] if accounts else ["a", "q"], default="q")

        if choice == "a":
            username = Prompt.ask("[bold]Email address[/bold]")
            password = Prompt.ask("[bold]App password[/bold]", password=True)
            label = Prompt.ask("[bold]Label[/bold] [dim](e.g., Personal, Work)[/dim]", default="")
            accounts.append({"username": username, "password": password, "label": label})
            accounts_file.parent.mkdir(parents=True, exist_ok=True)
            accounts_file.write_text(json.dumps({"accounts": accounts}, indent=2))
            console.print(f"[green]✅ Added {username}[/green]")

        elif choice == "d" and accounts:
            idx = IntPrompt.ask("[bold]Number to delete[/bold]", min=1, max=len(accounts))
            removed = accounts.pop(idx - 1)
            accounts_file.write_text(json.dumps({"accounts": accounts}, indent=2))
            console.print(f"[red]Removed {removed['username']}[/red]")

        elif choice == "r" and accounts:
            idx = IntPrompt.ask("[bold]Set account # as default[/bold]", min=1, max=len(accounts))
            acct = accounts.pop(idx - 1)
            accounts.insert(0, acct)
            accounts_file.write_text(json.dumps({"accounts": accounts}, indent=2))
            console.print(f"[green]✅ Default: {acct['username']}[/green]")

        elif choice == "q":
            break


# ─── STATUS ─────────────────────────────────────────────────────────

@app.command()
def status():
    """Show system status with last 7 days activity dashboard."""
    setup_logging()
    db = SQLiteStore()
    stats = db.get_stats(days=7) if config.SQLITE_FILE.exists() else {"total_jobs": 0, "emails": {"sent": 0, "total": 0}, "sources": {}, "decisions": {}}

    console.print(Panel("[bold cyan]📊 System Status — Last 7 Days[/bold cyan]", border_style="cyan"))

    summary = Table.grid(padding=(1, 4))
    summary.add_column()
    summary.add_column()
    summary.add_row(
        Panel(f"[bold]{stats['total_jobs']}[/bold]\nJobs", border_style="blue"),
        Panel(f"[bold]{stats['emails'].get('sent', 0)}/{stats['emails'].get('total', 0)}[/bold]\nEmails", border_style="green"),
    )
    avg_score = stats.get("avg_score", "N/A")
    summary.add_row(
        Panel(f"[bold]{avg_score}[/bold]\nAvg Score", border_style="yellow"),
        Panel(f"[bold]{len(stats['sources'])}[/bold]\nSources", border_style="magenta"),
    )
    console.print(summary)

    if stats.get("decisions"):
        console.print("\n[bold]Decisions:[/bold]")
        d = Table(box=box.SIMPLE)
        d.add_column("Decision", style="cyan")
        d.add_column("Count", justify="right")
        for dec, count in stats["decisions"].items():
            emoji = {"APPLY": "✅", "APPLY_LATER": "⏰", "WATCH": "👀", "SKIP": "⏭️"}.get(dec, "")
            d.add_row(f"{emoji} {dec}", str(count))
        console.print(d)


# ─── STATS ──────────────────────────────────────────────────────────

@app.command()
def stats(
    days: int = typer.Option(30, "--days", "-d", help="Days of history to analyze"),
):
    """Show detailed statistics with trend data."""
    setup_logging()
    db = SQLiteStore()
    metrics = Metrics()
    db_stats = db.get_stats(days=days)
    metrics_summary = metrics.get_summary(days=days)

    console.print(Panel(f"[bold cyan]📈 Statistics — Last {days} Days[/bold cyan]", border_style="cyan"))

    t = Table(box=box.ROUNDED)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", justify="right")
    t.add_row("Total Jobs", str(db_stats["total_jobs"]))
    t.add_row("Avg Score", str(db_stats.get("avg_score", "N/A")))
    t.add_row("Emails Sent", f"{db_stats['emails'].get('sent', 0)}/{db_stats['emails'].get('total', 0)}")
    t.add_row("Errors", str(metrics_summary.get("total_errors", 0)))
    t.add_row("Avg Duration", f"{metrics_summary.get('avg_duration_seconds', 0):.1f}s")
    t.add_row("Pipeline Runs", str(metrics_summary.get("pipeline_runs", 0)))
    console.print(t)

    if db_stats.get("sources"):
        console.print("\n[bold]Source Breakdown:[/bold]")
        s = Table(box=box.SIMPLE)
        s.add_column("Source", style="cyan")
        s.add_column("Jobs", justify="right")
        for src, count in db_stats["sources"].items():
            s.add_row(src, str(count))
        console.print(s)

    drift = metrics.detect_drift(days=days)
    if drift:
        console.print("\n[bold yellow]⚠️  Drift Detected:[/bold yellow]")
        for k, v in drift.items():
            console.print(f"  {v}")

    top = db.get_top_companies(limit=10)
    if top:
        console.print("\n[bold]Top Companies:[/bold]")
        ct = Table(box=box.SIMPLE)
        ct.add_column("Company", style="cyan")
        ct.add_column("Jobs", justify="right")
        ct.add_column("Avg Score", justify="right")
        for c in top:
            ct.add_row(c["company"], str(c["count"]), f"{c['avg_score']:.0f}")
        console.print(ct)


# ─── AUDIT ──────────────────────────────────────────────────────────

@app.command()
def audit(
    decision: Optional[str] = typer.Option(None, "--decision", "-d", help="Filter: APPLY, APPLY_LATER, WATCH, SKIP"),
    company: Optional[str] = typer.Option(None, "--company", "-c", help="Filter by company name"),
    min_score: Optional[int] = typer.Option(None, "--min-score", "-m", help="Minimum match score"),
    limit: int = typer.Option(30, "--limit", "-n", help="Max jobs to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Audit and browse past job decisions with filters."""
    setup_logging()
    db = SQLiteStore()
    jobs = db.search_jobs(
        decision=decision.upper() if decision else None,
        company=company,
        min_score=min_score,
        limit=limit,
    )
    if not jobs:
        console.print("[yellow]No matching jobs found[/yellow]")
        raise typer.Exit(0)

    if json_output:
        console.print(json.dumps([j.to_dict() for j in jobs], indent=2, default=str))
        return

    t = Table(box=box.ROUNDED, show_edge=False)
    t.add_column("#", style="dim", width=3)
    t.add_column("Company", style="cyan", width=18)
    t.add_column("Role", style="white", width=28)
    t.add_column("Score", justify="right", width=5)
    t.add_column("Decision", width=12)
    t.add_column("Reason", style="dim", width=30)
    for i, job in enumerate(jobs[:limit], 1):
        sc = "green" if job.score >= 75 else "yellow" if job.score >= 50 else "red"
        emoji = {"APPLY": "✅", "APPLY_LATER": "⏰", "WATCH": "👀", "SKIP": "⏭️"}.get(job.decision.value, "")
        t.add_row(
            str(i), job.company[:18], job.role[:28],
            f"[{sc}]{job.score}[/{sc}]",
            f"{emoji} {job.decision.value[:4]}",
            job.reason[:30],
        )
    console.print(t)
    console.print(f"\n[dim]{len(jobs)} jobs found[/dim]")


# ─── RETRY ──────────────────────────────────────────────────────────

@app.command()
def retry(
    limit: int = typer.Option(10, "--limit", "-n", help="Max jobs to retry"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without sending"),
):
    """Retry failed email sends from queue."""
    setup_logging()
    sender = EmailSender()
    pending = sender.send_queue.pending
    if not pending:
        console.print("[green]No pending jobs in send queue[/green]")
        return

    console.print(f"[yellow]📤 {len(pending)} queued emails[/yellow]")
    if dry_run:
        for jid in pending[:limit]:
            console.print(f"  • {jid[:16]}")
        console.print("\n[dim]Run without --dry-run to send[/dim]")
        return

    if Confirm.ask(f"\nRetry {min(limit, len(pending))} queued emails?", default=True):
        sent = sender.retry_queue()
        console.print(f"[green]✅ Sent {sent} emails[/green]")
        remaining = sender.send_queue.pending
        if remaining:
            console.print(f"[yellow]⏳ {len(remaining)} still queued (rate limit)[/yellow]")


# ─── CONFIG ─────────────────────────────────────────────────────────

@app.command()
def config_wizard():
    """Interactive configuration wizard for .env."""
    console.print(Panel("[bold cyan]⚙️ Configuration Wizard[/bold cyan]\nSet up your Job OS in a few steps.", border_style="cyan"))
    env_path = Path(__file__).parent / ".env"

    current = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                current[k.strip()] = v.strip()

    fields = [
        ("YOUR_NAME", "Your full name", str),
        ("YOUR_TITLE", "Your job title", str),
        ("YOUR_SKILLS", "Your skills (comma-separated)", str),
        ("TARGET_ROLES", "Target roles (comma-separated)", str),
        ("SMTP_USERNAME", "Your Gmail address", str),
        ("SMTP_PASSWORD", "Gmail app password (from myaccount.google.com/apppasswords)", str),
        ("YOUR_LINKEDIN", "LinkedIn profile URL", str, True),
        ("YOUR_GITHUB", "GitHub profile URL", str, True),
        ("MIN_SALARY", "Minimum annual salary", int, True),
        ("PREFERRED_LOCATIONS", "Preferred locations (comma-separated)", str, True),
    ]

    updates = {}
    for field_data in fields:
        field = field_data[0]
        label = field_data[1]
        optional = field_data[3] if len(field_data) > 3 else False
        default = current.get(field, "")
        prompt_text = f"[bold cyan]{label}[/bold cyan]" + (" [dim](optional)[/dim]" if optional else "")
        val = Prompt.ask(prompt_text, default=default) if default else Prompt.ask(prompt_text)
        if val:
            updates[field] = val

    if Confirm.ask("\n[bold yellow]Save to .env?[/bold yellow]", default=True):
        lines = []
        if env_path.exists():
            existing = env_path.read_text()
            written_keys = set()
            for line in existing.splitlines():
                if "=" in line and not line.startswith("#"):
                    k = line.split("=", 1)[0].strip()
                    if k in updates:
                        lines.append(f"{k}={updates[k]}")
                        written_keys.add(k)
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
            for k, v in updates.items():
                if k not in written_keys:
                    lines.append(f"{k}={v}")
        else:
            lines = [f"{k}={v}" for k, v in updates.items()]
        env_path.write_text("\n".join(lines) + "\n")
        console.print(f"[green]✅ Saved to {env_path}[/green]")

    if Confirm.ask("\n[bold]Generate .env.example?[/bold]", default=False):
        example = config.write_env_example()
        console.print(f"[green]✅ Created {example}[/green]")

    if Confirm.ask("\n[bold]Validate configuration now?[/bold]", default=True):
        errors = config.validate_config()
        if errors:
            console.print("[red]Issues found:[/red]")
            for e in errors:
                console.print(f"  • {e}")
        else:
            console.print("[green]✅ All good![/green]")


@app.command()
def config_check():
    """Validate .env configuration with detailed report."""
    details = config.validate_with_detail()
    t = Table(box=box.ROUNDED)
    t.add_column("Field", style="bold", width=22)
    t.add_column("Status", width=10)
    t.add_column("Detail", style="dim")
    for d in details:
        status_style = {"ok": "green", "missing": "red", "invalid": "yellow"}.get(d["status"], "white")
        t.add_row(
            d["field"],
            f"[{status_style}]● {d['status']}[/{status_style}]",
            d["message"],
        )
    console.print(t)
    errors = [d for d in details if d["status"] != "ok"]
    if errors:
        console.print(f"\n[yellow]⚠️  {len(errors)} issues found — run 'jobctl config-wizard' to fix[/yellow]")
        raise typer.Exit(1)
    console.print("\n[green]✅ All checks passed![/green]")


# ─── UPLOAD RESUME ──────────────────────────────────────────────────

@app.command()
def upload_resume(path: str = typer.Argument(..., help="Path to your resume PDF")):
    """Upload your resume PDF to the project."""
    src = Path(path)
    if not src.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(1)
    if src.suffix.lower() != ".pdf":
        console.print("[red]Resume must be a PDF[/red]")
        raise typer.Exit(1)
    dst = Path(__file__).parent / "data" / "resume.pdf"
    dst.parent.mkdir(exist_ok=True)
    shutil.copy2(src, dst)
    console.print(f"[green]✅ Resume saved to {dst}[/green]")
    console.print(f"Add to .env: [bold]YOUR_RESUME={dst}[/bold]")


# ─── SOURCES ────────────────────────────────────────────────────────

@app.command()
def sources():
    """List available job sources and their status."""
    db = SQLiteStore()
    stats = db.get_stats(days=7) if config.SQLITE_FILE.exists() else None
    t = Table(box=box.ROUNDED)
    t.add_column("Source", style="bold cyan")
    t.add_column("Status", style="bold")
    t.add_column("Collector", style="dim")
    t.add_column("Enabled", justify="center")
    t.add_column("Jobs (7d)", justify="right")
    for name, label in SOURCE_LABELS.items():
        enabled = "✅" if name in config.ENABLED_COLLECTORS else "❌"
        jobs_7d = stats["sources"].get(name, 0) if stats else "?"
        cls = SOURCES.get(name)
        est = cls().estimate_total_jobs() if cls else 0
        t.add_row(label, f"~{est} jobs/run", cls.__name__ if cls else "N/A", enabled, str(jobs_7d))
    console.print(t)


# ─── CIRCUIT ────────────────────────────────────────────────────────

@app.command()
def circuit():
    """Show circuit breaker status for all collectors."""
    t = Table(box=box.ROUNDED)
    t.add_column("Collector", style="cyan")
    t.add_column("State", style="bold")
    t.add_column("Failures")
    t.add_column("Total Calls")
    t.add_column("Failure Rate")
    for name, cls in SOURCES.items():
        cb = cls().circuit_breaker
        s = cb.get_status()
        state_color = {"CLOSED": "green", "OPEN": "red", "HALF_OPEN": "yellow"}.get(s["state"], "white")
        t.add_row(
            name,
            f"[{state_color}]● {s['state']}[/{state_color}]",
            str(s["failure_count"]),
            str(s["total_calls"]),
            f"{s['failure_rate']}%",
        )
    console.print(t)


# ─── PROFILE ────────────────────────────────────────────────────────

@app.command()
def profile(
    force: bool = typer.Option(False, "--force", "-f", help="Force refresh GitHub cache"),
):
    """Analyze and display your GitHub profile with repo categories."""
    setup_logging()
    github_username = config.YOUR_GITHUB.split("/")[-1] if config.YOUR_GITHUB else None
    if not github_username:
        console.print("[red]YOUR_GITHUB not set in .env[/red]")
        raise typer.Exit(1)

    analyzer = ProfileAnalyzer()
    console.print(f"[bold]Analyzing GitHub:[/bold] {github_username}")
    data = analyzer.analyze_github(github_username, force=force)
    if not data:
        console.print("[red]❌ GitHub analysis failed[/red]")
        raise typer.Exit(1)

    console.print()
    t = Table(box=box.ROUNDED)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", style="bold")
    t.add_row("Repos", str(data["public_repos"]))
    t.add_row("Total Stars", str(data["total_stars"]))
    t.add_row("Languages", ", ".join(data.get("languages", [])[:8]))
    console.print(t)

    if data.get("category_counts"):
        console.print("\n[bold]Repo Categories:[/bold]")
        ct = Table(box=box.SIMPLE)
        ct.add_column("Category", style="cyan")
        ct.add_column("Count", justify="right")
        ct.add_column("Top Repos", style="dim")
        for cat_id, info in sorted(data["category_counts"].items(), key=lambda x: -x[1]["count"]):
            repos = data.get("top_by_category", {}).get(cat_id, [])
            names = ", ".join(r["name"] for r in repos[:2])
            ct.add_row(f"{info['label']} ({cat_id})", str(info["count"]), names)
        console.print(ct)

    if data.get("top_repos"):
        console.print("\n[bold]Top Starred Repos:[/bold]")
        rt = Table(box=box.SIMPLE)
        rt.add_column("Repo", style="cyan")
        rt.add_column("Stars", justify="right")
        rt.add_column("Language")
        for r in data["top_repos"][:10]:
            rt.add_row(r["name"], str(r["stars"]), r.get("language", ""))
        console.print(rt)


# ─── HELPERS ────────────────────────────────────────────────────────

def _phase_callback(phase: str, current: int, total: int) -> None:
    phase_names = {
        "collect": "📥 Collecting jobs",
        "deduplicate": "🔄 Deduplicating",
        "enrich": "✉️ Enriching with emails",
        "score": "📊 Scoring & deciding",
        "outreach": "📧 Sending emails",
        "store": "💾 Storing results",
    }
    label = phase_names.get(phase, phase)
    console.log(f"[bold cyan]{label}[/bold cyan] ({current + 1}/{total})")


def _show_results(result) -> None:
    t = Table(box=box.ROUNDED, title="[bold green]✨ Pipeline Complete[/bold green]")
    t.add_column("Metric", style="cyan")
    t.add_column("Value", justify="right", style="bold")
    t.add_row("⏱️ Duration", f"{result.duration_seconds:.1f}s")
    t.add_row("📥 Jobs Collected", str(result.jobs_collected))
    t.add_row("🔄 New (after dedup)", str(result.jobs_deduplicated))
    t.add_row("✉️ Enriched", str(result.jobs_enriched))
    t.add_row("📊 Scored", str(result.jobs_scored))
    t.add_row("📧 Emails Sent", str(result.emails_sent))
    t.add_row("❌ Errors", str(result.errors))
    console.print(t)

    if result.decisions_made:
        dt = Table(box=box.SIMPLE, show_header=False)
        dt.add_column("Decision", style="yellow")
        dt.add_column("Count", justify="right")
        for dec, count in result.decisions_made.items():
            emoji = {"APPLY": "✅", "APPLY_LATER": "⏰", "WATCH": "👀", "SKIP": "⏭️"}.get(dec.value, "")
            dt.add_row(f"{emoji} {dec.value}", str(count))
        console.print(Panel(dt, title="📋 Decisions"))

    if result.source_stats:
        st = Table(box=box.SIMPLE, show_header=False)
        st.add_column("Source", style="cyan")
        st.add_column("Jobs", justify="right")
        for src, count in result.source_stats.items():
            st.add_row(src, str(count))
        console.print(Panel(st, title="📍 Sources"))

    if result.phase_timings:
        pt = Table(box=box.SIMPLE, show_header=False)
        pt.add_column("Phase", style="magenta")
        pt.add_column("Time", justify="right")
        for phase, secs in sorted(result.phase_timings.items(), key=lambda x: -x[1]):
            pt.add_row(phase, f"{secs:.1f}s")
        console.print(Panel(pt, title="⏱️ Phase Timings"))


def _preview_apply_emails(apply_jobs: List[Job]) -> None:
    sender = EmailSender()
    for i, job in enumerate(apply_jobs[:5], 1):
        email_data = sender.composer.compose_initial_email(job)
        console.print(Panel(
            f"[bold cyan]{i}. {job.company} — {job.role}[/bold cyan]\n"
            f"[yellow]To:[/yellow] {email_data['to']}\n"
            f"[yellow]Subject:[/yellow] {email_data['subject']}\n"
            f"[yellow]Score:[/yellow] {job.score}/100\n\n"
            f"[dim]{email_data['body'][:500]}[/dim]",
            border_style="blue",
        ))
        if i < len(apply_jobs[:5]):
            if not Confirm.ask("[dim]Show next?[/dim]", default=True):
                break


def _display_detailed_job_report(jobs: list) -> None:
    from collections import Counter

    console.print(Panel(f"[bold magenta]📊 Detailed Report — {len(jobs)} Jobs[/bold magenta]", border_style="magenta"))

    t = Table(box=box.ROUNDED)
    t.add_column("#", style="dim", width=3)
    t.add_column("Company", style="cyan", width=18)
    t.add_column("Role", style="yellow", width=28)
    t.add_column("Location", style="green", width=14)
    t.add_column("Score", justify="right", width=5)
    t.add_column("Decision", width=8)
    for i, job in enumerate(jobs[:50], 1):
        sc = "green" if job.score >= 75 else "yellow" if job.score >= 50 else "red"
        emoji = {"APPLY": "✅", "APPLY_LATER": "⏰", "WATCH": "👀", "SKIP": "⏭️"}.get(job.decision.value, "")
        t.add_row(
            str(i), job.company[:18], job.role[:28],
            job.location[:14],
            f"[{sc}]{job.score}[/{sc}]",
            f"{emoji} {job.decision.value[:4]}",
        )
    console.print(t)

    companies = Counter(j.company for j in jobs)
    ct = Table(title="🏢 Top Companies", box=box.SIMPLE)
    ct.add_column("Company", style="cyan")
    ct.add_column("Jobs", justify="right")
    ct.add_column("%", justify="right")
    for co, count in companies.most_common(10):
        ct.add_row(co[:25], str(count), f"{count/len(jobs)*100:.1f}")
    console.print(ct)

    locations = Counter(j.location for j in jobs if j.location)
    if locations:
        lt = Table(title="📍 Top Locations", box=box.SIMPLE)
        lt.add_column("Location", style="green")
        lt.add_column("Jobs", justify="right")
        for loc, count in locations.most_common(8):
            lt.add_row(loc[:20], str(count))
        console.print(lt)

    scores = {
        "🔥 Excellent (75-100)": len([j for j in jobs if j.score >= 75]),
        "👍 Good (50-74)": len([j for j in jobs if 50 <= j.score < 75]),
        "⚠️ Fair (25-49)": len([j for j in jobs if 25 <= j.score < 50]),
        "❌ Poor (0-24)": len([j for j in jobs if j.score < 25]),
    }
    st = Table(title="📊 Score Distribution", box=box.SIMPLE)
    st.add_column("Range", style="yellow")
    st.add_column("Count", justify="right")
    st.add_column("%", justify="right")
    for rng, count in scores.items():
        pct = count / len(jobs) * 100 if jobs else 0
        st.add_row(rng, str(count), f"{pct:.1f}")
    console.print(st)

    skills_found = Counter()
    skill_keywords = [
        "python", "javascript", "typescript", "react", "node", "docker", "kubernetes",
        "aws", "azure", "gcp", "sql", "postgresql", "mongodb", "redis",
        "fastapi", "django", "flask", "langchain", "rag", "llm", "openai",
        "machine learning", "deep learning", "nlp", "pytorch", "tensorflow",
        "git", "ci/cd", "terraform", "graphql", "rest",
    ]
    for job in jobs:
        desc = (job.description or "").lower()
        for sk in skill_keywords:
            if sk in desc:
                skills_found[sk] += 1
    if skills_found:
        skt = Table(title="🔥 Most Requested Skills", box=box.SIMPLE)
        skt.add_column("Skill", style="yellow")
        skt.add_column("Jobs", justify="right")
        skt.add_column("%", justify="right")
        for sk, count in skills_found.most_common(15):
            skt.add_row(sk.title(), str(count), f"{count/len(jobs)*100:.1f}")
        console.print(skt)

    avg = sum(j.score for j in jobs) / len(jobs) if jobs else 0
    remote = len([j for j in jobs if j.is_remote()])
    with_email = len([j for j in jobs if j.has_email()])
    summary = Table(box=box.SIMPLE)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="bold")
    summary.add_row("Avg Match Score", f"{avg:.1f}")
    summary.add_row("Remote Jobs", f"{remote} ({remote/len(jobs)*100:.1f}%)")
    summary.add_row("With Email Found", f"{with_email} ({with_email/len(jobs)*100:.1f}%)")
    summary.add_row("Unique Companies", str(len(companies)))
    summary.add_row("Unique Locations", str(len(locations)))
    console.print(Panel(summary, title="📈 Summary"))


if __name__ == "__main__":
    app()
