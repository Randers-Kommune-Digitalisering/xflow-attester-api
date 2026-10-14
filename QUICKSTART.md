# Quickstart (generated Flask application)

This repository is generated from the `rk-digi-template` (Flask) cookiecutter.
This guide assumes cookiecutter has already been run and you are now working in the generated repository.

## What you get

- Flask app scaffold with:
	- `GET /healthz` health check
	- `GET /api/example` example API route

- Environment-based config (`FLASK_ENV=dev|prod`) loaded from `.env` via `python-dotenv`

- Dockerfile (gunicorn) + `docker-compose.yml`

- GitHub Actions workflows for:
	- Linting + tests
	- Docker build + push to GHCR
	- Optional auto-deploy to an infrastructure repo on release tags
	- Optional “config sync” (sync repo-level dev configs via PR)

## Local development

### Prerequisites

- Python 3.10+
- (Optional) Docker + Docker Compose

### Step-by-step:

1) Create and activate a virtual environment:


    - *Linux/macOS*:

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

    - *Windows (PowerShell)*:

    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

2) Install dependencies:

    ```bash
    pip install -r requirements.txt -r requirements-dev.txt 
    ```

3) Create your `.env`

    Copy the example and edit values as needed.

    ```bash
    cp .env.example .env
    ```

    Notes:

    - `.env` is ignored by git.
    - If you add new environment variables, also add them to `src/utils/config.py` and (usually) to `.env.example`.

4) Run the application:

    ```bash
    python src/main.py
    ```

    The server listens on `PORT` (default `8080`).

## Docker (gunicorn)

The application uses Docker via the `Dockerfile`, which runs the application with gunicorn.

Build and run the application:

```bash
docker build -t xflow_attester_api:local .
docker run --rm -p 8080:8080 -e FLASK_ENV=prod -e PORT=8080 xflow_attester_api:local
```

Run the application with compose:

```bash
docker compose up
```

## Formatting, linting, testing

Organize imports using iSort:

```bash
isort .
```

Format code to conform to PEP 8 using Autopep8:

```bash
autopep8 .
```

Lint using Flake8:

```bash
flake8
```

Run tests using Pytest:

```bash
pytest
```

List API endpoints:

```bash
Select-String -Path .\src\*.py, .\src\**\*.py -Pattern "@api.route")
```

## Build and deploy

The `Build` workflow builds and pushes a Docker image to GHCR on:

- pushes to `main`
- tags matching `v*`

It tags images with the commit SHA, and for releases also tags `latest` and the version (e.g. `1.2.3`).

### Auto-deploy (optional)

The deploy workflow updates an infrastructure repository when a build succeeds and the commit has a release tag.

**How to enable it**:

1) Add a GitHub Actions secret named `AUTO_DEPLOY` containing an SSH deploy key with access to the infrastructure repository.

2) Ensure infrastructure repository contains a folder with this repository name (ie. `xflow_attester_api`) with a `values.yaml`-file

    Otherwise, update `.github/workflows/deploy.yml` to match your infrastructure setup if needed:
    - `INFRA_REPO` (target repo)
    - `INFRA_REF` (branch/ref)
    - `INFRA_VALUES_EXPR` (YAML path to the image tag)

3) Create a release tag and push it:

    ```bash
    git tag v1.2.3
    git push --tags
    ```

## Config sync

This repository includes a workflow that can sync shared “dev configs” (workflows, `setup.cfg`, etc.) from a central repository into this repo via a pull request.

**How it works**:

- Source/target mappings live in `.github/dev-configs-sync.yml`.

- The workflow `.github/workflows/sync-dev-configs.yml` runs on a schedule (Mondays) and can also be run manually.

- It checks out the `dev-configs` repository, copies the mapped files into this repo, and opens a PR.

**How to enable it**:

1) Create a GitHub Actions secret named `CONFIG_SYNC`.

    - The value should be a fine-grained PAT (read-only) that can read the repository configured as `dev_configs.repo` in `.github/dev-configs-sync.yml`.
    - This is needed because the built-in `GITHUB_TOKEN` cannot read other private repositories.

2) (Optional) Adjust `.github/dev-configs-sync.yml` if you want to sync different files.

**Important**:

- Destination files must already exist in this repo; the workflow intentionally fails instead of creating new destination files.

## Dependabot (dependency updates)

This template includes a Dependabot configuration at `.github/dependabot.yml`.
It can automatically open pull requests for dependency updates (Python/pip and GitHub Actions), including security updates.

**How to enable it**:

1) Go to __Settings__ → [<sub><sup>__Security & quality__</sub></sup>] __Advanced Security__ and ensure these are enabled:

    - Dependency graph
    - Dependabot alerts
    - Dependabot security updates

3) Wait for the first scheduled run, or trigger it by editing and pushing a small change to `.github/dependabot.yml`.

Notes:

- Adjust update frequency, ecosystems, and PR limits directly in `.github/dependabot.yml`.

- If auto config sync is configured, Dependabot configuration will automatically sync from the `dev-configs` repository.
