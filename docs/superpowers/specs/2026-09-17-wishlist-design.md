# Wishlist deployment design

## Goal

Deploy [Wishlist](https://github.com/cmintey/wishlist) as a public, self-hosted
application at `https://wishlist.zebernst.dev`, using Pocket ID for OpenID
Connect (OIDC) login and Rook/Ceph for persistent data.

## Architecture

Wishlist will be deployed to the `self-hosted` namespace using the repository's
`app-template` Helm chart. The deployment will use
`ghcr.io/cmintey/wishlist` and set
`ORIGIN=https://wishlist.zebernst.dev`.

A single Ceph ReadWriteOnce PVC will persist both application directories:

- `/usr/src/app/data` — the SQLite database and app configuration
- `/usr/src/app/uploads` — user-uploaded images

The workload will use the established non-root, read-only-root-filesystem
security settings, an `emptyDir` for writable temporary files, readiness and
liveness HTTP probes, conservative resource requests and limits, and the
internal-only priority class.

## Exposure and monitoring

An app-template HTTPRoute will expose `wishlist.zebernst.dev` through the
`external` Cilium Gateway. Its Gatus annotation will create an availability
probe in the `self-hosted` group, inherited from the public Gateway's DNS and
probe configuration.

Public registry/list links are intentionally reachable without authenticating:
Wishlist uses them to let recipients view and claim gifts. Normal account
access remains protected by Wishlist's native login flow.

## Identity and onboarding

Pocket ID will have an OIDC client registered with:

- Redirect URI: `https://wishlist.zebernst.dev/login`
- Issuer URL: the existing public Pocket ID issuer at `https://id.zebernst.dev`

Wishlist does not support receiving OIDC configuration through environment
variables. After Flux deploys the app, an operator must:

1. Complete Wishlist's setup wizard by creating the initial local administrator.
2. In Wishlist Administration Settings, disable Public Signup, making account
   creation invite-only.
3. Enter Pocket ID's issuer URL, client ID, and client secret in the OIDC
   settings.

The Pocket ID client secret must be stored in 1Password and must not be
committed. Because Wishlist only accepts this secret through its administration
UI, it will be entered directly there rather than rendered in GitOps
manifests.

## Validation

Before relying on the deployment:

1. Validate the rendered Flux/Helm manifests with the repository's standard
   YAML and Kubernetes validation tasks.
2. Confirm Flux reconciles the Kustomization, HelmRelease, PVC, Service, and
   external HTTPRoute successfully.
3. Confirm `https://wishlist.zebernst.dev` is reachable and Gatus reports it
   healthy.
4. Verify a Pocket ID user can sign in through Wishlist's OIDC flow.
5. Verify public signup is disabled while an administrator can still issue
   invitations and a public registry link remains claimable.
