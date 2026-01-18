# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a homelab Kubernetes cluster running on Talos Linux, managed via GitOps using Flux. The cluster is deployed on bare-metal hardware and uses Infrastructure as Code (IaC) practices with automated dependency updates via Renovate.

## Reference Repositories

When in doubt about patterns, structure, or best practices, reference these repos:
- https://github.com/buroa/k8s-gitops
- https://github.com/onedr0p/home-ops

This repo's structure is modeled after theirs, and they frequently stay up-to-date on patterns that get adopted here.

## Development Environment

All development tools and environment variables are managed via `mise`. The project uses `task` (Taskfile) for task automation.

### Setup

```bash
# Install tools via mise
mise install

# List available tasks
task --list

# Generate kubeconfig
task talos:kubeconfig
```

This project uses **bd (beads)** for issue tracking.
Run `bd prime` for workflow context, or install hooks (`bd hooks install`) for auto-injection.

**Quick reference:**
- `bd ready` - Find unblocked work
- `bd create "Title" --type task --priority 2` - Create issue
- `bd close <id>` - Complete work
- `bd sync` - Sync with git (run at session end)

For full workflow details: `bd prime`

### Environment Variables

The following environment variables are automatically set via mise:
- `KUBECONFIG`: Points to kubernetes/kubeconfig
- `TALOSCONFIG`: Points to talos/talosconfig
- `MINIJINJA_CONFIG_FILE`: Points to .minijinja.toml

Version information is loaded from `kubernetes/apps/system-upgrade/versions.env`

## Common Development Tasks

### Bootstrap & Setup

```bash
# Bootstrap Talos cluster (first time setup)
task bootstrap:talos

# Bootstrap Kubernetes apps (requires ROOK_DISK variable)
task bootstrap:apps ROOK_DISK="<disk-model>"
```

### Talos Operations

```bash
# Apply config to a node
task talos:apply-node NODE=<node-name>

# Upgrade Talos on a node
task talos:upgrade-node NODE=<node-name>

# Upgrade Kubernetes across cluster
task talos:upgrade-k8s

# Reboot a node
task talos:reboot-node NODE=<node-name>
```

### Kubernetes Operations

```bash
# Mount a PVC for inspection
task kubernetes:browse-pvc NS=<namespace> CLAIM=<pvc-name>

# Open shell to a node
task kubernetes:node-shell NODE=<node-name>

# Sync all ExternalSecrets
task kubernetes:sync-secrets

# Clean up failed/pending/succeeded pods
task kubernetes:cleanse-pods
```

### Volsync (Backup/Restore)

```bash
# Snapshot an app
task volsync:snapshot NS=<namespace> APP=<app-name>

# Restore an app from previous snapshot
task volsync:restore NS=<namespace> APP=<app-name> PREVIOUS=<snapshot-name>

# Suspend/resume Volsync
task volsync:state-suspend
task volsync:state-resume

# Unlock restic repos
task volsync:unlock
```

## Architecture

### Directory Structure

```
kubernetes/
├── apps/           # Application deployments organized by namespace
├── bootstrap/      # Initial cluster bootstrap (helmfile + secrets)
├── components/     # Reusable kustomize components (volsync, gatus, keda, common)
└── flux/           # Core Flux GitOps configuration
```

### Talos Configuration

Talos machine configs are templated using Jinja2 (minijinja-cli) with 1Password secret injection:
- Template: `talos/machineconfig.yaml.j2`
- Node-specific patches: `talos/controlplane/<node>.yaml` and `talos/worker/<node>.yaml`
- Secrets referenced via `op://` format (1Password)

The template uses `ENV.MACHINE_TYPE` to differentiate between controlplane and worker configs.

### GitOps with Flux

Flux monitors the `kubernetes/` directory and applies changes automatically:

1. **Entry point**: `kubernetes/flux/cluster/ks.yaml` defines two root Kustomizations:
   - `cluster-meta`: Flux repositories and meta configuration
   - `cluster-apps`: All application deployments

2. **Application structure**: Each app under `kubernetes/apps/<namespace>/<app>/` typically contains:
   - `ks.yaml`: Flux Kustomization defining dependencies
   - `app/`: HelmRelease or raw manifests
   - `config/`: Additional configuration

3. **Dependencies**: Apps declare dependencies via `spec.dependsOn` in their Kustomizations

### Bootstrap Process

Initial cluster setup installs core components via helmfile in this order:
1. Cilium (CNI)
2. CoreDNS
3. Spegel (OCI registry mirror)
4. cert-manager
5. external-secrets
6. flux-operator
7. flux-instance

After bootstrap, Flux takes over and manages all subsequent deployments.

### Networking & Ingress

Three ingress methods are used:
- **internal**: Local network only, uses BGP-advertised VIPs with ExternalDNS for UniFi
- **tailscale**: Private access via Tailscale, automatic MagicDNS
- **external**: Public access via Cloudflare Tunnel (cloudflared), with ExternalDNS managing CNAME records

### Storage

- **Rook/Ceph**: Hyper-converged block, file, and object storage
- **Synology NAS**: NFS storage via custom Synology CSI fork for Talos
- **Volsync**: PVC backup and restore to Backblaze B2

### Secrets Management

Secrets are managed via external-secrets using 1Password Connect. Never commit secrets directly.

## Tool Stack

Key tools installed via mise:
- `kubectl`, `k9s`, `kubecolor`: Kubernetes CLI
- `talosctl`: Talos Linux management
- `flux`: Flux CLI for GitOps
- `helm`, `helmfile`: Helm package management
- `cilium-cli`: Cilium networking debug
- `op` (1Password CLI): Secret injection
- `minijinja-cli`: Template rendering
- `task`: Task automation

Useful kubectl plugins (via krew/aqua):
- `kubectl-cnpg`: CloudNativePG management
- `kubectl-node-shell`: Node access
- `kubectl-view-secret`: Secret inspection
- `kubectl-browse-pvc`: PVC mounting
- `kubectl-rook-ceph`: Rook management

## Cloud Dependencies

External services used:
- **1Password**: Secret storage (via external-secrets)
- **Cloudflare**: DNS and Cloudflare Tunnel
- **Backblaze B2**: S3-compatible backup storage
- **Pushover**: Alerting notifications
- **GitHub**: Repository and CI/CD
