# lazytools

A collection of handy scripts and CLI tools designed to simplify and speed up your command-line workflow. Whether you're a developer, sysadmin, or DevSecOps engineer, these tools aim to automate repetitive tasks and make your terminal experience more efficient.

Make your CLI life easier with lazytools!

## Tools & Scripts

### Unified CLI: `gitctl`

`gitctl` is a modular Python CLI that unifies local workspace Git repository auditing with remote GitHub organization/repository management.

| Scope | Subcommand | Description |
| :--- | :--- | :--- |
| **Local** | `gitctl status` | Quick audit of all Git repositories in workspace (`~/projects`). |
| **Local** | `gitctl local status [-f]` | Audit local repositories with optional parallel remote fetch (`-f`). |
| **Local** | `gitctl local dirty` | Filter and show only repositories with uncommitted/untracked changes. |
| **Local** | `gitctl local unpushed` | Filter and show repositories with unpushed commits (ahead of upstream). |
| **GitHub** | `gitctl github features audit` | Audit features (Issues, Wiki, Projects, Pages, etc.) across all repos. |
| **GitHub** | `gitctl github features config` | Interactively or declaratively configure repository features. |
| **GitHub** | `gitctl github topics audit` | Audit topics assigned across all GitHub repositories. |
| **GitHub** | `gitctl github webhooks audit` | Scan webhooks, check delivery failure statuses, and cleanup broken hooks. |
| **GitHub** | `gitctl github webhooks add` | Add a new webhook to a repository. |
| **GitHub** | `gitctl github webhooks delete` | Delete a webhook interactively or by ID. |

### Standalone DevOps & Automation Scripts

| Script | Description | Category | Prerequisites |
| :--- | :--- | :--- | :--- |
| `ansible-playbook.sh` | Runs `ansible-playbook` via Docker, mounting current directory and SSH keys. | DevOps | `docker` |
| `aws.sh` | Runs `aws` CLI via Docker using a specialized DevOps image. | DevOps | `docker` |
| `az.sh` | Runs `az` CLI via Docker using a specialized DevOps image. | DevOps | `docker` |
| `eksctl.sh` | Runs `eksctl` CLI via Docker using a specialized DevOps image. | DevOps | `docker` |
| `gcloud.sh` | Runs `gcloud` CLI via Docker using a specialized DevOps image. | DevOps | `docker` |
| `infracost.sh` | Runs `infracost` via Docker to estimate cloud costs. Requires `.env` config. | DevOps | `docker` |
| `terraform.sh` | Runs `terraform` commands using a specialized DevOps Docker image. | DevOps | `docker` |
| `n8n.sh` | Runs `n8n-cli` via Docker to manage workflows. Requires `.env` configuration. | Automation | `docker` |

## Prerequisites

- **Python 3 & rich**: Required for `gitctl` CLI tool.
- **GitHub CLI (`gh`)**: Required for remote GitHub features in `gitctl`.
- **Docker**: Required for DevOps and Automation containerized wrapper scripts.

## Installation

Use the provided `install-script.sh` to install any script or CLI tool as a symlink in `~/.local/bin`:

```bash
# List available tools and scripts
./install-script.sh

# Install the unified gitctl CLI tool
./install-script.sh gitctl

# Install any individual bash script
./install-script.sh terraform
```

Ensure `~/.local/bin` is in your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```
