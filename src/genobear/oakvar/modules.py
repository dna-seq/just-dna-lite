"""
GenoBear Modules CLI - Manage OakVar modules from GitHub repositories.

This module provides a CLI interface for cloning and downloading data from OakVar modules.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, FileSizeColumn, TimeRemainingColumn
from rich.table import Table
from eliot import start_action

from dotenv import load_dotenv

logs = Path("logs") if Path("logs").exists() else Path.cwd().parent / "logs"

load_dotenv()

from pycomfort.logging import to_nice_file, to_nice_stdout

# Create the main CLI app
app = typer.Typer(
    name="modules",
    help="Manage OakVar modules from GitHub repositories",
    rich_markup_mode="rich",
    no_args_is_help=True
)

console = Console()


def normalize_repo_url(repo: str) -> str:
    """
    Normalize repository identifier to a full GitHub URL.
    
    Args:
        repo: Repository identifier (e.g., "dna-seq/just_longevitymap" or full URL)
        
    Returns:
        Full GitHub URL
    """
    if repo.startswith("http://") or repo.startswith("https://"):
        return repo
    elif repo.startswith("git@"):
        return repo
    elif "/" in repo:
        # Assume GitHub format: owner/repo
        return f"https://github.com/{repo}.git"
    else:
        raise ValueError(f"Invalid repository format: {repo}. Use 'owner/repo' or full URL")


def get_repo_name_from_url(repo_url: str) -> str:
    """
    Extract repository name from URL.
    
    Args:
        repo_url: Repository URL
        
    Returns:
        Repository name (owner/repo)
    """
    if repo_url.startswith("https://github.com/"):
        repo_path = repo_url.replace("https://github.com/", "").replace(".git", "")
        return repo_path
    elif repo_url.startswith("git@github.com:"):
        repo_path = repo_url.replace("git@github.com:", "").replace(".git", "")
        return repo_path
    else:
        # Fallback: use last part of URL
        return repo_url.split("/")[-1].replace(".git", "")


def clone_or_update_repo(repo_url: str, cache_dir: Optional[Path] = None) -> Path:
    """
    Clone or update a git repository.
    
    Args:
        repo_url: Repository URL
        cache_dir: Cache directory for repositories. If None, uses platformdirs cache.
        
    Returns:
        Path to the cloned repository
        
    Raises:
        typer.Exit: If git operations fail
    """
    repo_name = get_repo_name_from_url(repo_url)
    
    if cache_dir is None:
        from pooch import os_cache
        cache_base = Path(os_cache("genobear"))
    else:
        cache_base = Path(cache_dir)
    
    repos_dir = cache_base / "repositories"
    repos_dir.mkdir(parents=True, exist_ok=True)
    
    repo_path = repos_dir / repo_name.replace("/", "_")
    
    if repo_path.exists() and (repo_path / ".git").exists():
        # Repository exists, try to update
        with start_action(action_type="update_repo", repo=repo_url, path=str(repo_path)):
            try:
                subprocess.run(
                    ["git", "pull"],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                # If pull fails, continue with existing version
                console.print(f"[yellow]Warning: Could not update repository: {e.stderr}[/yellow]")
    else:
        # Clone repository
        with start_action(action_type="clone_repo", repo=repo_url, path=str(repo_path)):
            try:
                subprocess.run(
                    ["git", "clone", repo_url, str(repo_path)],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error: Failed to clone repository: {e.stderr}[/red]")
                raise typer.Exit(code=1)
            except FileNotFoundError:
                console.print("[red]Error: git is not installed or not in PATH[/red]")
                raise typer.Exit(code=1)
    
    if not repo_path.exists():
        console.print(f"[red]Error: Repository path does not exist: {repo_path}[/red]")
        raise typer.Exit(code=1)
    
    return repo_path


def find_sqlite_files(directory: Path, recursive: bool = True) -> list[Path]:
    """
    Find all SQLite files in the given directory.
    
    Args:
        directory: Directory to search in
        recursive: Whether to search recursively
        
    Returns:
        List of paths to SQLite files
    """
    sqlite_extensions = {".sqlite", ".sqlite3", ".db"}
    sqlite_files: list[Path] = []
    
    if not directory.exists():
        return sqlite_files
    
    if recursive:
        for ext in sqlite_extensions:
            sqlite_files.extend(directory.rglob(f"*{ext}"))
    else:
        for ext in sqlite_extensions:
            sqlite_files.extend(directory.glob(f"*{ext}"))
    
    # Remove duplicates and sort
    return sorted(set(sqlite_files))


@app.command()
def data(
    repo: Optional[str] = typer.Option(
        "dna-seq/just_longevitymap",
        "--repo",
        "-r",
        help="GitHub repository (owner/repo format or full URL). Default: dna-seq/just_longevitymap"
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory for downloaded SQLite files. Default: data/modules/reponame/"
    ),
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory for cloned repositories. Default: platform-specific cache"
    ),
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        help="Search recursively in subdirectories"
    ),
    log: bool = typer.Option(
        False,
        "--log/--no-log",
        help="Enable detailed logging to files"
    ),
):
    """
    Download SQLite data files from an OakVar module repository.
    
    Downloads files with extensions: .sqlite, .sqlite3, .db from the repository's data folder.
    
    Examples:
    
        # Download SQLite files from default repository (dna-seq/just_longevitymap)
        modules data
        
        # Download SQLite files from a specific repository
        modules data --repo owner/repo-name
        
        # Download to a specific directory
        modules data --output-dir /path/to/output
        
        # Download non-recursively (only top-level files)
        modules data --no-recursive
    """
    if log:
        logs.mkdir(exist_ok=True, parents=True)
        to_nice_file(logs / "modules_data.json", logs / "modules_data.log")
        to_nice_stdout()
    
    with start_action(action_type="modules_data_command", repo=repo, output_dir=output_dir, recursive=recursive) as action:
        # Clone or update repository and use its data folder
        repo_url = normalize_repo_url(repo)
        repo_name = get_repo_name_from_url(repo_url)
        console.print(f"[bold cyan]Cloning/updating repository: {repo}[/bold cyan]")
        
        cache_path = Path(cache_dir).expanduser().resolve() if cache_dir else None
        repo_path = clone_or_update_repo(repo_url, cache_path)
        search_dir = repo_path / "data"
        
        if not search_dir.exists():
            console.print(f"[yellow]Warning: data folder does not exist in repository: {search_dir}[/yellow]")
            console.print(f"[yellow]Searching in repository root instead: {repo_path}[/yellow]")
            search_dir = repo_path
        
        console.print(f"[bold cyan]Searching for SQLite files in: {search_dir}[/bold cyan]")
        
        sqlite_files = find_sqlite_files(search_dir, recursive=recursive)
        
        if not sqlite_files:
            console.print("[yellow]No SQLite files found.[/yellow]")
            action.log(message_type="info", files_found=0)
            return
        
        # Determine output directory
        if output_dir:
            dest_dir = Path(output_dir).expanduser().resolve()
        else:
            # Default: data/modules/reponame/
            repo_basename = repo_name.split("/")[-1]  # Get just the repo name, not owner/repo
            dest_dir = (Path("data") / "modules" / repo_basename).resolve()
        
        dest_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[bold cyan]Downloading to: {dest_dir}[/bold cyan]")
        
        # Download files with progress
        downloaded_files: list[Path] = []
        total_size = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            FileSizeColumn(),
            TextColumn("/"),
            FileSizeColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Downloading SQLite files...", total=sum(f.stat().st_size for f in sqlite_files if f.exists()))
            
            for file_path in sqlite_files:
                try:
                    file_size = file_path.stat().st_size
                    
                    # Preserve relative path structure from search directory
                    relative_path = file_path.relative_to(search_dir)
                    dest_file = dest_dir / relative_path
                    
                    # Skip if file already exists (same path)
                    if dest_file.exists():
                        # Check if it's the same file (same filesystem) or just skip if exists
                        try:
                            if dest_file.samefile(file_path):
                                console.print(f"[yellow]Skipping (already exists): {relative_path}[/yellow]")
                                continue
                        except OSError:
                            # Different filesystem, check if sizes match
                            if dest_file.stat().st_size == file_size:
                                console.print(f"[yellow]Skipping (already exists): {relative_path}[/yellow]")
                                continue
                    
                    # Create parent directories if needed
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    shutil.copy2(file_path, dest_file)
                    downloaded_files.append(dest_file)
                    total_size += file_size
                    progress.update(task, advance=file_size)
                    
                except OSError as e:
                    console.print(f"[red]Error copying {file_path.name}: {e}[/red]")
                    action.log(message_type="error", file=str(file_path), error=str(e))
        
        # Display results
        table = Table(title="Downloaded SQLite Files", show_header=True, header_style="bold magenta")
        table.add_column("File Name", style="cyan", no_wrap=False)
        table.add_column("Size", justify="right", style="green")
        table.add_column("Location", style="yellow")
        
        for file_path in downloaded_files:
            try:
                size = file_path.stat().st_size
                size_str = f"{size / (1024*1024):.2f} MB" if size > 1024*1024 else f"{size / 1024:.2f} KB"
                # Get relative path if possible, otherwise use absolute
                try:
                    resolved_path = file_path.resolve()
                    location = str(resolved_path.relative_to(Path.cwd().resolve()))
                except ValueError:
                    # If not in subpath, use the path as-is
                    location = str(file_path)
                table.add_row(
                    file_path.name,
                    size_str,
                    location
                )
            except OSError:
                table.add_row(file_path.name, "N/A", str(file_path))
        
        console.print(table)
        console.print(f"\n[bold green]Downloaded {len(downloaded_files)} SQLite file(s)[/bold green]")
        console.print(f"[bold green]Total size: {total_size / (1024*1024):.2f} MB[/bold green]")
        console.print(f"[bold green]Saved to: {dest_dir}[/bold green]")
        
        action.log(
            message_type="success",
            files_downloaded=len(downloaded_files),
            total_size_bytes=total_size,
            output_directory=str(dest_dir)
        )


@app.command()
def clone(
    repo: Optional[str] = typer.Option(
        "dna-seq/just_longevitymap",
        "--repo",
        "-r",
        help="GitHub repository (owner/repo format or full URL). Default: dna-seq/just_longevitymap"
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory for cloned repository. Default: data/modules/reponame/"
    ),
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory for cloned repositories. Default: platform-specific cache"
    ),
    log: bool = typer.Option(
        False,
        "--log/--no-log",
        help="Enable detailed logging to files"
    ),
):
    """
    Clone a full OakVar module repository.
    
    Clones the entire repository to the specified directory.
    
    Examples:
    
        # Clone default repository (dna-seq/just_longevitymap)
        modules clone
        
        # Clone a specific repository
        modules clone --repo owner/repo-name
        
        # Clone to a specific directory
        modules clone --output-dir /path/to/output
    """
    if log:
        logs.mkdir(exist_ok=True, parents=True)
        to_nice_file(logs / "modules_clone.json", logs / "modules_clone.log")
        to_nice_stdout()
    
    with start_action(action_type="modules_clone_command", repo=repo, output_dir=output_dir) as action:
        repo_url = normalize_repo_url(repo)
        repo_name = get_repo_name_from_url(repo_url)
        console.print(f"[bold cyan]Cloning repository: {repo}[/bold cyan]")
        
        # Determine output directory
        if output_dir:
            dest_dir = Path(output_dir).expanduser().resolve()
        else:
            # Default: data/modules/reponame/
            repo_basename = repo_name.split("/")[-1]  # Get just the repo name, not owner/repo
            dest_dir = (Path("data") / "modules" / repo_basename).resolve()
        
        # Check if destination already exists
        if dest_dir.exists() and (dest_dir / ".git").exists():
            console.print(f"[yellow]Repository already exists at: {dest_dir}[/yellow]")
            console.print("[yellow]Use 'git pull' to update, or remove the directory to re-clone[/yellow]")
            action.log(message_type="info", already_exists=True, path=str(dest_dir))
            return
        
        # Clone repository directly to destination
        with start_action(action_type="clone_repo", repo=repo_url, path=str(dest_dir)):
            try:
                subprocess.run(
                    ["git", "clone", repo_url, str(dest_dir)],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error: Failed to clone repository: {e.stderr}[/red]")
                action.log(message_type="error", error=str(e))
                raise typer.Exit(code=1)
            except FileNotFoundError:
                console.print("[red]Error: git is not installed or not in PATH[/red]")
                raise typer.Exit(code=1)
        
        console.print(f"[bold green]Repository cloned successfully to: {dest_dir}[/bold green]")
        action.log(
            message_type="success",
            output_directory=str(dest_dir),
            repo=repo
        )



