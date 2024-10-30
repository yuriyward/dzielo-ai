import argparse
import datetime
import os
import subprocess

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
MODEL = "gpt-4o-mini"
system_prompt = """
You are professional comedian and you are asked to tell the funny and original jokes.
"""
client = OpenAI()


def main():
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "OpenAI API key not found. Please set the OPENAI_API_KEY "
            "environment variable."
        )
        return

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Process git commits.")
    parser.add_argument("month", type=int, help="Month (1-12)")
    parser.add_argument("year", type=int, help="Year (e.g., 2023)")
    parser.add_argument(
        "--author", type=str, help="Author email", default="yuriy.babyak@goelett.com"
    )
    parser.add_argument(
        "--repo",
        type=str,
        default="../travel-frontend/",
        help="Path to the repository (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory to save the output files (default: output)",
    )
    args = parser.parse_args()

    month = args.month
    year = args.year
    author = args.author
    repo_path = args.repo
    output_dir = args.output_dir

    # Pad the month with leading zero if necessary
    month_padded = "{:02d}".format(month)
    first_day = datetime.date(year, month, 1)

    # Calculate the last day of the month
    if month == 12:
        last_day = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # File names for output
    commit_changes_filename = os.path.join(
        output_dir, f"{year}.{month_padded}_zmiany.txt"
    )

    rewritten_filename = os.path.join(
        output_dir, f"{year}.{month_padded}_opis_zmian.txt"
    )

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

    # Rewrite commit messages using OpenAI API
    rewritten_messages = [rewrite_commit_message(msg) for msg in merged_pr_messages]

    # Save rewritten commit messages
    with open(rewritten_filename, "w") as rewritten_file:
        for rewritten_msg in rewritten_messages:
            rewritten_file.write(rewritten_msg + "\n")

    print(f"Commands executed for period: {first_day} to {last_day}")


def rewrite_commit_message(commit_message):
    completion = client.beta.chat.completions.parse(
        model=MODEL,
        temperature=0.5,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": commit_message},
        ],
    )

    return completion.choices[0].message


if __name__ == "__main__":
    main()
