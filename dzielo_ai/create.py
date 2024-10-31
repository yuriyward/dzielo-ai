import argparse
import datetime
import os
import re
import subprocess
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
system_prompt = """
YOU ARE AN EXPERT TECHNICAL CONTENT TRANSLATOR WITH SPECIALIZATION IN POLISH LANGUAGE LOCALIZATION.
 YOUR TASK IS TO TRANSLATE A LIST OF TECHNICAL TASKS INTO POLISH, REMOVING ANY TECHNICAL IDENTIFIERS SUCH AS TASK IDS, PR NUMBERS,
 AND FUNCTION NAMES (E.G., 'FEAT(SCROLLBAR)', 'BUGFIX(TRAVELLERS)'). REPHRASE EACH TASK IN A NON-TECHNICAL, USER-FRIENDLY WAY,
 HIGHLIGHTING THE BENEFITS OF THE IMPROVEMENTS IN A CREATIVE AND PRAISEWORTHY MANNER.

###INSTRUCTIONS###

- REMOVE any task identifiers or specific technical references (e.g., 'Merged PR', '#1233', 'feat(something)', 'bugfix(something)').
- TRANSLATE the task descriptions into POLISH.
- REPHRASE each task description to be MORE USER-FRIENDLY, providing additional context on how the change benefits the
 user or enhances the application experience.
- FRAME the translation to present the work as a CREATIVE and IMPACTFUL ACHIEVEMENT, making it sound like a significant
 improvement that enhances usability or aesthetics.
- ADD details to make each description feel complete and meaningful, explaining the effect of the change in a positive, engaging way.

###CHAIN OF THOUGHTS###

FOLLOW these steps in strict order to TRANSLATE and REPHRASE each task:

1. **IDENTIFY** technical terms, identifiers, or numbers and **REMOVE** them from the task description.
2. **TRANSLATE** the remaining description into Polish, adapting the language for a broader, non-technical audience.
3. **REPHRASE** each task description in a more user-centric way:
    - Highlight how the task **improves** user experience or application aesthetics.
    - Emphasize **benefits** to the end-user (e.g., easier to use, more intuitive, visually appealing).
4. **POLISH** the language to make each description **sound impressive and valuable**.

###WHAT NOT TO DO###

- **DO NOT** INCLUDE any technical identifiers or task numbers (e.g., 'PR #12522', 'feat(something)').
- **DO NOT** TRANSLATE the task in a literal or overly technical way.
- **DO NOT** OMIT user-centric details that explain how the task benefits users.
- **DO NOT** USE complex language or jargon that may confuse non-technical readers.
- **DO NOT** ADD extra new line after each item.

###FEW-SHOT EXAMPLE###

Input:
1. Merged PR 12522: #124635 feat(scrollbar): Made scrollbar pretty again
2. Merged PR 12644: #124102 bugfix(travellers): Fixed mobile view issues for travellers list

Response:
1. Estetyczne ulepszenie przewijania listy - stworzony nowy wygląd suwaka przewijania, dodając mu bardziej estetyczny wygląd.
 Dzięki temu interakcja z listami stała się przyjemniejsza i bardziej nowoczesna.
2. Ulepszenie widoku listy podróżnych na urządzeniach mobilnych - poprawiono widok listy podróżnych, aby lepiej wyglądał
 i działał na urządzeniach mobilnych. Dzięki temu korzystanie z aplikacji stało się bardziej intuicyjne i komfortowe
   dla użytkowników mobilnych.

"""
client = OpenAI()


def main():
    start_time = time.time()  # Record the start time

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("OpenAI API key not found. Please set the OPENAI_API_KEY " "environment variable.")
        return

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Process git commits.")
    parser.add_argument("month", type=int, help="Month (1-12)")
    parser.add_argument("year", type=int, help="Year (e.g., 2023)")
    parser.add_argument("--author", type=str, help="Author email", default="yuriy.babyak@goelett.com")
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

    print(f"Processing commits for {year}-{month:02d}")

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
    commit_changes_filename = os.path.join(output_dir, f"{year}.{month_padded}_zmiany.txt")
    rewritten_filename = os.path.join(output_dir, f"{year}.{month_padded}_opis_zmian.txt")

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
