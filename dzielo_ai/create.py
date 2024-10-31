import argparse
import datetime
import logging
import os
import pathlib
import re
import subprocess
import time
import zipfile
from typing import List, Tuple

import colorlog
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

# Load environment variables from .env file
load_dotenv()

# Configure logging
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        fmt="[%(log_color)s%(asctime)s - %(levelname)s%(reset)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )
)

logger = colorlog.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# Read the system prompt from the file
def load_system_prompt(file_path: str) -> str:
    """
    Loads the system prompt from a specified file.

    Args:
        file_path (str): Path to the system prompt file.

    Returns:
        str: Content of the system prompt.
    """
    try:
        with open(file_path, "r") as file:
            content = file.read()
            logging.info(f"Loaded system prompt from {file_path}")
            return content
    except FileNotFoundError:
        logging.error(f"System prompt file not found: {file_path}")
        raise
    except Exception as e:
        logging.error(f"Error reading system prompt file: {e}")
        raise


client = OpenAI()


def get_previous_month(date: datetime.date) -> datetime.date:
    """
    Returns the first day of the previous month relative to the given date.

    Args:
        date (datetime.date): The reference date.

    Returns:
        datetime.date: The first day of the previous month.
    """
    if date.month == 1:
        return datetime.date(date.year - 1, 12, 1)
    else:
        return datetime.date(date.year, date.month - 1, 1)


def parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Process git commits.")

    # Create a mutually exclusive group for period selection
    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--this-month",
        action="store_true",
        help="Process commits from the current month (default)",
    )
    group.add_argument(
        "--previous-month",
        action="store_true",
        help="Process commits from the previous month",
    )
    group.add_argument(
        "--custom",
        nargs=2,
        metavar=("MONTH", "YEAR"),
        type=int,
        help="Specify a custom month and year (e.g., --custom 6 2023 for June 2023)",
    )

    # Optional arguments
    parser.add_argument(
        "--author",
        type=str,
        help="Author email",
        default="yuriy.babyak@goelett.com",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="../travel-frontend/",
        help="Path to the repository (default: ../travel-frontend/)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save the output files (default: output)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use for rewriting commit messages",
    )

    return parser.parse_args()


def determine_target_date(args: argparse.Namespace) -> datetime.date:
    """
    Determines the target date based on the provided arguments.

    Args:
        args (argparse.Namespace): Parsed command-line arguments.

    Returns:
        datetime.date: The target date.
    """
    today = datetime.date.today()
    if args.previous_month:
        return get_previous_month(today)
    elif args.custom:
        month, year = args.custom
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 1 and 12.")
        return datetime.date(year, month, 1)
    else:
        # Default to this month
        return today


def validate_repo_path(repo_path: str) -> pathlib.Path:
    """
    Validates the repository path.

    Args:
        repo_path (str): The path to the repository.

    Returns:
        pathlib.Path: The validated repository path.

    Raises:
        ValueError: If the repository path is invalid.
    """
    path = pathlib.Path(repo_path)
    if not path.is_dir():
        raise ValueError(f"The repository path {repo_path} is not a valid directory.")
    logging.info(f"Validated repository path: {path.resolve()}")
    return path


def calculate_month_range(year: int, month: int) -> Tuple[datetime.date, datetime.date]:
    """
    Calculates the first and last day of the specified month.

    Args:
        year (int): The year.
        month (int): The month.

    Returns:
        Tuple[datetime.date, datetime.date]: The first and last day of the month.
    """
    first_day = datetime.date(year, month, 1)
    if month == 12:
        last_day = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    logging.debug(f"Month range: {first_day} to {last_day}")
    return first_day, last_day


def execute_git_command(command: List[str], repo_path: pathlib.Path) -> str:
    """
    Executes a git command and returns its output.

    Args:
        command (List[str]): The git command to execute.
        repo_path (pathlib.Path): The path to the repository.

    Returns:
        str: The output of the git command.

    Raises:
        subprocess.CalledProcessError: If the git command fails.
    """
    logging.debug(f"Executing git command: {' '.join(command)} in {repo_path}")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=repo_path, check=True)
    logging.debug(f"Git command output: {result.stdout[:100]}...")  # Log first 100 chars
    return result.stdout


def write_to_file(file_path: str, data: str) -> None:
    """
    Writes data to a file.

    Args:
        file_path (str): The path to the file.
        data (str): The data to write.
    """
    try:
        with open(file_path, "w") as file:
            file.write(data)
        logging.info(f"Wrote data to {file_path}")
    except Exception as e:
        logging.error(f"Error writing to file {file_path}: {e}")
        raise


def rewrite_commit_messages(commit_messages: str, system_prompt: str, model: str) -> str:
    """
    Rewrites commit messages using the OpenAI API.

    Args:
        commit_messages (str): The original commit messages.
        system_prompt (str): The system prompt for the OpenAI API.
        model (str): The OpenAI model to use.

    Returns:
        str: The rewritten commit messages.

    Raises:
        ConnectionError: If the API request fails.
    """
    try:
        logging.info("Sending commit messages to OpenAI API for rewriting.")
        completion = client.chat.completions.create(
            model=model,
            temperature=0.8,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": commit_messages},
            ],
        )
        rewritten = completion.choices[0].message.content
        logging.info("Successfully rewrote commit messages.")
        return rewritten
    except OpenAIError as e:
        logging.error(f"OpenAI API request failed: {e}")
        raise ConnectionError("API request failed.") from e


def load_commit_messages(repo_path: pathlib.Path, first_day: datetime.date, last_day: datetime.date, author: str) -> List[str]:
    """
    Retrieves commit messages from the git repository.

    Args:
        repo_path (pathlib.Path): The path to the repository.
        first_day (datetime.date): The start date for commits.
        last_day (datetime.date): The end date for commits.
        author (str): The author's email.

    Returns:
        List[str]: A list of commit messages.
    """
    commits_command = [
        "git",
        "log",
        "--pretty=format:%s",
        f"--since={first_day.isoformat()}",
        f"--until={last_day.isoformat()}",
        f"--author={author}",
    ]
    try:
        git_log_output = execute_git_command(commits_command, repo_path)
        commit_messages = git_log_output.strip().split("\n")
        merged_pr_messages = [msg for msg in commit_messages if msg.startswith("Merged PR")]
        logging.info(f"Found {len(merged_pr_messages)} merged PR messages.")
        return merged_pr_messages
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running git command: {e.stderr}")
        raise


def zip_output_files(zip_filename: pathlib.Path, files: list) -> None:
    """
    Zips the specified files into a single zip archive.

    Args:
        zip_filename (pathlib.Path): The path to the zip file to create.
        files (list): A list of file paths to include in the zip archive.
    """
    with zipfile.ZipFile(zip_filename, "w") as zipf:
        for file in files:
            zipf.write(file, arcname=file.name)
    logging.info(f"Output files zipped into: {zip_filename}")


def process_commits(
    repo_path: pathlib.Path,
    first_day: datetime.date,
    last_day: datetime.date,
    author: str,
    output_dir: pathlib.Path,
    system_prompt: str,
    model: str,
) -> None:
    """
    Processes the commits by retrieving, rewriting, and saving them.

    Args:
        repo_path (pathlib.Path): The path to the repository.
        first_day (datetime.date): The start date for commits.
        last_day (datetime.date): The end date for commits.
        author (str): The author's email.
        output_dir (pathlib.Path): The directory to save output files.
        system_prompt (str): The system prompt for the OpenAI API.
        model (str): The OpenAI model to use.
    """
    # Ensure the output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Output directory is set to: {output_dir.resolve()}")

    # Extract author name from email
    author_name = author.split("@")[0].replace(".", "_")

    # File names for output
    commit_changes_filename = output_dir / f"{first_day.year}_{first_day.month:02d}_zmiany.txt"
    rewritten_filename = output_dir / f"{first_day.year}_{first_day.month:02d}_opis_zmian.txt"
    zip_filename = output_dir / f"dzielo_{author_name}_{first_day.year}_{first_day.month:02d}.zip"

    # Command to get detailed commit changes
    commit_changes_command = [
        "git",
        "log",
        f"--since={first_day.isoformat()}",
        f"--until={last_day.isoformat()}",
        "--branches",
        "-p",
        f"--author={author}",
    ]

    try:
        commit_changes = execute_git_command(commit_changes_command, repo_path)
        write_to_file(str(commit_changes_filename), commit_changes)
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running git command for commit changes: {e.stderr}")
        raise

    # Load commit messages
    merged_pr_messages = load_commit_messages(repo_path, first_day, last_day, author)
    if not merged_pr_messages:
        logging.info("No merged PR messages found for the specified period.")
        return

    all_messages = "\n".join(merged_pr_messages)
    rewritten_messages = rewrite_commit_messages(all_messages, system_prompt, model)
    rewritten_messages = re.sub(r"\n+", "\n", rewritten_messages)  # Remove extra newlines

    # Save rewritten commit messages
    write_to_file(str(rewritten_filename), rewritten_messages + "\n")

    # Zip the output files
    zip_output_files(zip_filename, [commit_changes_filename, rewritten_filename])


def main() -> None:
    """
    The main entry point of the script.
    """
    start_time = time.time()

    # Check for OpenAI API key
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logging.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        return

    # Parse command-line arguments
    args = parse_arguments()

    # Validate repository path
    try:
        repo_path = validate_repo_path(args.repo)
    except ValueError as e:
        logging.error(e)
        return

    # Determine the target period
    try:
        target_date = determine_target_date(args)
    except ValueError as e:
        logging.error(f"Invalid custom date provided: {e}")
        return

    year = target_date.year
    month = target_date.month
    author = args.author
    model = args.model
    output_dir = pathlib.Path(args.output_dir)

    logging.info(f"Processing commits for {year}-{month:02d}")

    # Calculate the first and last day of the target month
    first_day, last_day = calculate_month_range(year, month)

    # Load system prompt
    try:
        system_prompt = load_system_prompt("prompts/tasks_rewriter.txt")
    except Exception:
        return

    # Process commits
    try:
        process_commits(
            repo_path=repo_path,
            first_day=first_day,
            last_day=last_day,
            author=author,
            output_dir=output_dir,
            system_prompt=system_prompt,
            model=model,
        )
    except Exception as e:
        logging.error(f"An error occurred during commit processing: {e}")
        return

    end_time = time.time()
    duration = end_time - start_time
    logging.info(f"Script execution time: {duration:.2f} seconds")


if __name__ == "__main__":
    main()
