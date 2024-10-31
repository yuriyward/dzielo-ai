import argparse
import datetime
import os
import re
import subprocess
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Read the system prompt from the file
with open("prompts/tasks_rewriter.txt", "r") as file:
    system_prompt = file.read()

client = OpenAI()


def get_previous_month(date):
    """
    Returns the first day of the previous month relative to the given date.
    """
    if date.month == 1:
        return datetime.date(date.year - 1, 12, 1)
    else:
        return datetime.date(date.year, date.month - 1, 1)


def main():
    start_time = time.time()  # Record the start time

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        return

    # Parse command-line arguments
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
    args = parser.parse_args()

    # Determine the target period
    today = datetime.date.today()
    if args.previous_month:
        target_date = get_previous_month(today)
    elif args.custom:
        try:
            month, year = args.custom
            if not (1 <= month <= 12):
                raise ValueError("Month must be between 1 and 12.")
            target_date = datetime.date(year, month, 1)
        except ValueError as e:
            print(f"Invalid custom date provided: {e}")
            return
    else:
        # Default to this month
        target_date = today

    year = target_date.year
    month = target_date.month
    author = args.author
    repo_path = args.repo
    output_dir = args.output_dir

    print(f"Processing commits for {year}-{month:02d}")

    # Calculate the first and last day of the target month
    first_day = datetime.date(year, month, 1)
    if month == 12:
        last_day = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # File names for output
    commit_changes_filename = os.path.join(output_dir, f"{year}.{month:02d}_zmiany.txt")
    rewritten_filename = os.path.join(output_dir, f"{year}.{month:02d}_opis_zmian.txt")

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
        with open(commit_changes_filename, "w") as commit_changes_file:
            subprocess.run(
                commit_changes_command,
                stdout=commit_changes_file,
                check=True,
                cwd=repo_path,  # Specify the repository path
            )
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e}")
        return

    # Command to get commit messages
    commits_command = [
        "git",
        "log",
        "--pretty=format:%s",
        f"--since={first_day.isoformat()}",
        f"--until={last_day.isoformat()}",
        f"--author={author}",
    ]
    try:
        git_log_output = subprocess.check_output(
            commits_command,
            text=True,
            cwd=repo_path,  # Specify the repository path
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e}")
        return

    # Process commit messages
    commit_messages = git_log_output.strip().split("\n")
    merged_pr_messages = [msg for msg in commit_messages if msg.startswith("Merged PR")]
    print(f"Commands executed for period: {first_day} to {last_day}")

    if not merged_pr_messages:
        print("No merged PR messages found for the specified period.")
        return

    # Rewrite commit messages using OpenAI API
    all_messages = "\n".join(merged_pr_messages)
    rewritten_messages = rewrite_commit_message(all_messages)
    rewritten_messages = re.sub(r"\n+", "\n", rewritten_messages)  # Remove extra newlines

    # Save rewritten commit messages
    with open(rewritten_filename, "w") as rewritten_file:
        rewritten_file.write(rewritten_messages + "\n")

    end_time = time.time()  # Record the end time
    duration = end_time - start_time  # Calculate the duration
    print(f"Script execution time: {duration:.2f} seconds")


def rewrite_commit_message(commit_message):
    rewrite_start_time = time.time()  # Record the start time

    print("Starting rewriting commit message")
    completion = client.chat.completions.create(
        model=os.getenv("MODEL"),
        temperature=0.8,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": commit_message},
        ],
    )

    rewrite_end_time = time.time()  # Record the end time
    duration = rewrite_end_time - rewrite_start_time  # Calculate the duration
    print(f"Rewriting commit message took: {duration:.2f} seconds")
    return completion.choices[0].message.content


if __name__ == "__main__":
    main()
