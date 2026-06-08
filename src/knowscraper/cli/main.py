"""
KnowScraper CLI
Usage:
    knowscraper create <project-name>               # scaffold new project
    knowscraper create <project-name> --type playwright
    knowscraper run <file>                          # run a scraper file
    knowscraper info                                # show version + environment
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def print_banner():
    print(f"""
{CYAN}{BOLD}
  _  __                    _____
 | |/ /_ __   _____      _/ ____|  ___ _ __ __ _ _ __   ___ _ __
 | ' /| '_ \\ / _ \\ \\ /\\ / /\\___ \\ / __| '__/ _` | '_ \\ / _ \\ '__|
 | . \\| | | | (_) \\ V  V /  ___) | (__| | | (_| | |_) |  __/ |
 |_|\\_\\_| |_|\\___/ \\_/\\_/  |____/ \\___|_|  \\__,_| .__/ \\___|_|
                                                  |_|
{RESET}
{YELLOW}Knowledge Scraper Framework v0.1.0{RESET}
Python + Node.js | Crawlee-inspired | Anti-detection built-in
""")


def cmd_create(args):
    project_name = args.project_name
    crawler_type = args.type  # "cheerio" or "playwright"

    target = Path.cwd() / project_name
    if target.exists():
        print(f"{RED}Error: Directory '{project_name}' already exists.{RESET}")
        sys.exit(1)

    template = "playwright_project" if crawler_type == "playwright" else "cheerio_project"
    template_dir = TEMPLATES_DIR / template

    if not template_dir.exists():
        print(f"{RED}Error: Template '{template}' not found.{RESET}")
        sys.exit(1)

    # Copy template
    shutil.copytree(template_dir, target)

    # Replace {{project_name}} placeholder in main.py
    main_py = target / "main.py"
    content = main_py.read_text()
    content = content.replace("{{project_name}}", project_name)
    main_py.write_text(content)

    # Create .knowscraper dir for storage
    (target / ".knowscraper").mkdir(exist_ok=True)

    print(f"\n{GREEN}{BOLD}✓ Created project: {project_name}{RESET}")
    print(f"\n{YELLOW}Project structure:{RESET}")
    print(f"  {project_name}/")
    print(f"  ├── main.py          ← your scraper (edit this)")
    print(f"  ├── requirements.txt")
    print(f"  └── .knowscraper/    ← output data goes here")

    print(f"\n{YELLOW}Next steps:{RESET}")
    print(f"  cd {project_name}")
    print(f"  pip install -r requirements.txt")
    if crawler_type == "playwright":
        print(f"  playwright install chromium")
    print(f"  python main.py")

    print(f"\n{CYAN}Happy scraping! 🚀{RESET}\n")


def cmd_run(args):
    script = Path(args.file)
    if not script.exists():
        print(f"{RED}Error: File '{args.file}' not found.{RESET}")
        sys.exit(1)

    print(f"{CYAN}Running {script}...{RESET}\n")
    result = subprocess.run([sys.executable, str(script)], check=False)
    sys.exit(result.returncode)


def cmd_info(args):
    import platform
    try:
        import knowscraper
        ks_version = knowscraper.__version__
    except Exception:
        ks_version = "unknown"

    node_version = "not found"
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        node_version = result.stdout.strip()
    except Exception:
        pass

    print_banner()
    print(f"{BOLD}Environment:{RESET}")
    print(f"  KnowScraper : {ks_version}")
    print(f"  Python      : {sys.version.split()[0]}")
    print(f"  Platform    : {platform.system()} {platform.machine()}")
    print(f"  Node.js     : {node_version}")
    print()


def main():
    parser = argparse.ArgumentParser(
        prog="knowscraper",
        description="KnowScraper — Knowledge Scraper Framework CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # create
    p_create = sub.add_parser("create", help="Scaffold a new scraper project")
    p_create.add_argument("project_name", help="Name of the new project directory")
    p_create.add_argument(
        "--type",
        choices=["cheerio", "playwright"],
        default="cheerio",
        help="Crawler type (default: cheerio)",
    )

    # run
    p_run = sub.add_parser("run", help="Run a scraper file")
    p_run.add_argument("file", help="Path to the scraper Python file")

    # info
    sub.add_parser("info", help="Show version and environment info")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "info":
        cmd_info(args)
    else:
        print_banner()
        parser.print_help()


if __name__ == "__main__":
    main()
