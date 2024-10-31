# Dzielo AI

Dzielo AI is a tool designed to collect all changes made by a specified author from a GIT repository during a selected month. It then rewrites and translates commit messages using the OpenAI API, making them more comprehensible for non-technical audience. The tool is specifically designed to optimize the process of creating Prawa Autorskie.

## Features

- **Commit Message Rewriting**: Uses OpenAI API to rewrite commit messages.
- **Commit Message Processing**: Processes commit messages within a specified date range.
- **Code changes overview**: Creates file with all code changes made during specified period.
- **Output Management**: Saves rewritten commit messages to specified output directories.

## Installation

1. Clone the repository:

    ```sh
    git clone <repository-url>
    ```

2. Navigate to the project directory:

    ```sh
    cd dzielo-ai
    ```

3. Install dependencies using Poetry:

    ```sh
    poetry install
    ```

## Usage

1. Set up your environment variables by creating a `.env` file:

    ```sh
    cp .env-example .env
    ```

   Then, add your OpenAI API key to the [.env](http://_vscodecontentref_/1) file:

    ```env
    OPENAI_API_KEY=your_openai_api_key_here
    ```

2. Run the script:

    ```sh
    poetry run python dzielo_ai/create.py --repo <repository-path> --output-dir <output-directory> --model <openai-model>
    ```

## Configuration

- **Period Selection**:
  - `--this-month`: Process commits from the current month (default).
  - `--previous-month`: Process commits from the previous month.
  - `--custom MONTH YEAR`: Specify a custom month and year (e.g., `--custom 6 2023` for June 2023).

- **Author**:
  - `--author`: Author email (default: `yuriy.babyak@goelett.com`).

- **Repository Path**:
  - `--repo`: Path to the repository containing commit messages (default: `../travel-frontend/`).

- **Output Directory**:
  - `--output-dir`: Directory where the rewritten commit messages will be saved (default: `output`).

- **OpenAI Model**:
  - `--model`: The OpenAI model to use for rewriting commit messages (default: `gpt-4o-mini`).

## Example

```sh
python dzielo_ai/create.py
```

or

```sh
poetry run python dzielo_ai/create.py --repo ../travel-frontend/ --output-dir output --model gpt-4o-mini
```
