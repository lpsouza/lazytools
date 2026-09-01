# lazytools

A collection of handy scripts and CLI tools designed to simplify and speed up your command-line workflow. Whether you're a developer, sysadmin, or DevSecOps engineer, these tools aim to automate repetitive tasks and make your terminal experience more efficient.

Make your CLI life easier with lazytools!

## Tools & Scripts

### Unified CLI: `gitctl`

`gitctl` is a modular Python CLI that unifies local workspace Git repository auditing with remote GitHub organization/repository management.

| Scope | Subcommand | Description |
| :--- | :--- | :--- |
| **AI Commit** | `gitctl commit` (alias: `ci`, `ai-commit`) | Generate AI commit message from staged changes and commit interactively. |
| **Local** | `gitctl status` | Quick audit of all Git repositories in workspace (`~/projects`). |
| **Local** | `gitctl local status [-f]` | Audit local repositories with optional parallel remote fetch (`-f`). |
| **Local** | `gitctl local dirty` | Filter and show only repositories with uncommitted/untracked changes. |
| **Local** | `gitctl local unpushed` | Filter and show repositories with unpushed commits (ahead of upstream). |
| **Local** | `gitctl local commit` | Local workspace AI commit generator (alias of `gitctl commit`). |
| **GitHub** | `gitctl github features audit` | Audit features (Issues, Wiki, Projects, Pages, etc.) across all repos. |
| **GitHub** | `gitctl github features config` | Interactively or declaratively configure repository features. |
| **GitHub** | `gitctl github topics audit` | Audit topics assigned across all GitHub repositories. |
| **GitHub** | `gitctl github webhooks audit` | Scan webhooks, check delivery failure statuses, and cleanup broken hooks. |
| **GitHub** | `gitctl github webhooks add` | Add a new webhook to a repository. |
| **GitHub** | `gitctl github webhooks delete` | Delete a webhook interactively or by ID. |

### Terminal Monitor: `nodetop`

`nodetop` is a `btop`-inspired interactive terminal monitoring dashboard powered directly by Prometheus `node_exporter` endpoints (e.g. `http://ukitake:9100`).

```bash
# Launch interactive dashboard (defaults to http://localhost:9100 or NODETOP_URL)
nodetop

# Connect to a specific remote node_exporter
nodetop ukitake
nodetop http://ukitake:9100 -i 0.5

# Print a single metrics snapshot and exit
nodetop ukitake --once
```

**Interactive Hotkeys:**

* `q` / `Ctrl+C`: Quit
* `r`: Force immediate metrics refresh
* `+` / `-`: Increase / decrease scrape interval (0.5s - 10s)
* `1` - `5`: Toggle individual panels (CPU, Mem, Disks, Network, System)
* `h` / `?`: Show help overlay modal

### Standalone CLI Launchers & Git Aliases

| Command | Description | Prerequisites |
| :--- | :--- | :--- |
| `gcommit` | Quick interactive AI commit generator shortcut for `gitctl commit`. | `agy` or `gh copilot` |
| `git-ai` | Git custom subcommand launcher allowing `git ai` or `git-ai`. | `agy` or `gh copilot` |

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
