# lazytools

A collection of handy scripts designed to simplify and speed up your command-line workflow. Whether you're a developer, sysadmin, or CLI enthusiast, these tools aim to automate repetitive tasks and make your terminal experience more efficient.

Make your CLI life easier with lazytools!

## Scripts

| Script | Description | Category | Prerequisites |
| :--- | :--- | :--- | :--- |
| `github-add-webhook.sh` | Interactively add a new webhook with custom events and secrets. | GitHub | `gh`, `jq` |
| `github-audit-features.sh` | Audits features (Issues, Wiki, etc.) across all repos. Supports `--csv`. | GitHub | `gh`, `jq`, `awk` |
| `github-audit-topics.sh` | Lists all topics assigned to each of your repositories for better organization. | GitHub | `gh`, `jq` |
| `github-audit-webhooks.sh` | Scans for webhooks, checks for failures, and offers to remove broken ones. | GitHub | `gh`, `jq` |
| `github-config-features.sh` | Interactively toggle repo features. Handles unarchiving/re-archiving automatically. | GitHub | `gh`, `jq` |
| `github-delete-webhook.sh` | Interactively select and remove a specific webhook from a repository. | GitHub | `gh`, `jq` |
| `ansible-playbook.sh` | Runs `ansible-playbook` via Docker, mounting current directory and SSH keys. | DevOps | `docker` |
| `infracost.sh` | Runs `infracost` via Docker to estimate cloud costs. Requires `.env` config. | DevOps | `docker` |
| `terraform.sh` | Runs `terraform` commands using a specialized DevOps Docker image. | DevOps | `docker` |
| `n8n.sh` | Runs `n8n-cli` via Docker to manage workflows. Requires `.env` configuration. | Automation | `docker` |

## Prerequisites

- **Docker**: Required for DevOps and Automation scripts.
- **GitHub CLI (`gh`)**: Required for all GitHub management scripts.
- **jq**: Required for JSON parsing across most scripts.

## Installation

You can use the provided `install-script.sh` to set up the environment or simply clone the repository and add the `bash/` directory to your `PATH`.
