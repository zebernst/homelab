# Wishlist Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Wishlist at `https://wishlist.zebernst.dev` with a Ceph-backed
SQLite/uploads volume, public Cilium Gateway exposure, and Pocket ID OIDC
onboarding instructions.

**Architecture:** A Flux Kustomization in `self-hosted` will reconcile an
app-template HelmRelease. The HelmRelease creates the workload, Ceph RWO PVC,
Service, public HTTPRoute, and Gatus endpoint. Wishlist's native OIDC and
invite-only registration are persisted in its SQLite database and therefore
require documented post-deployment administrator configuration rather than
GitOps credentials.

**Tech Stack:** Flux CD, HelmRelease v2, bjw-s app-template, Cilium Gateway
API, Rook/Ceph block storage, Gatus, Pocket ID OIDC.

## Global Constraints

- Image: `ghcr.io/cmintey/wishlist:v0.66.0@sha256:073ab4de0f27a93a79410172bedfa3947bed4718f050396547516def790f1f49`.
- Public application origin and hostname: `https://wishlist.zebernst.dev`.
- Persistent paths: `/usr/src/app/data` and `/usr/src/app/uploads` on one
  `ceph-block` ReadWriteOnce PVC.
- Do not commit Pocket ID client credentials; Wishlist accepts OIDC settings
  only from its Administration Settings UI.
- Disable Wishlist Public Signup in its Administration Settings after the
  initial administrator is created.
- Preserve unauthenticated public registry/list links; they are a Wishlist
  feature, not a route-level authorization bypass.

---

## File structure

- `kubernetes/apps/self-hosted/kustomization.yaml` — registers the new Flux
  Kustomization with the namespace app aggregate.
- `kubernetes/apps/self-hosted/wishlist/ks.yaml` — Flux reconciliation,
  namespace, labels, timing, and source configuration.
- `kubernetes/apps/self-hosted/wishlist/app/kustomization.yaml` — groups the
  application HelmRelease.
- `kubernetes/apps/self-hosted/wishlist/app/helmrelease.yaml` — describes the
  container, storage, Service, external HTTPRoute, monitoring annotation, and
  workload hardening.
- `docs/superpowers/specs/2026-09-17-wishlist-design.md` — deployment
  requirements and the operator-only OIDC/signup configuration procedure.

### Task 1: Register the Flux application

**Files:**
- Create: `kubernetes/apps/self-hosted/wishlist/ks.yaml`
- Create: `kubernetes/apps/self-hosted/wishlist/app/kustomization.yaml`
- Modify: `kubernetes/apps/self-hosted/kustomization.yaml`
- Test: rendered Flux Kustomization manifest

**Interfaces:**
- Consumes: the existing `self-hosted` namespace aggregate and `flux-system`
  GitRepository.
- Produces: a Flux Kustomization named `wishlist` in `self-hosted`, reconciling
  `kubernetes/apps/self-hosted/wishlist/app`.

- [ ] **Step 1: Add the failing aggregate reference**

  Add this resource to the alphabetized `resources` list in
  `kubernetes/apps/self-hosted/kustomization.yaml`:

  ```yaml
    - wishlist/ks.yaml
  ```

- [ ] **Step 2: Validate the incomplete change fails**

  Run:

  ```bash
  kustomize build kubernetes/apps/self-hosted
  ```

  Expected: FAIL because `wishlist/ks.yaml` does not exist.

- [ ] **Step 3: Create the Flux Kustomization and app Kustomization**

  Create `kubernetes/apps/self-hosted/wishlist/ks.yaml`:

  ```yaml
  # yaml-language-server: $schema=https://kubernetes-schemas.pages.dev/kustomize.toolkit.fluxcd.io/kustomization_v1.json
  ---
  apiVersion: kustomize.toolkit.fluxcd.io/v1
  kind: Kustomization
  metadata:
    name: &app wishlist
    namespace: &ns self-hosted
  spec:
    targetNamespace: *ns
    commonMetadata:
      labels:
        app.kubernetes.io/name: *app
    interval: 30m
    retryInterval: 1m
    timeout: 5m
    path: kubernetes/apps/self-hosted/wishlist/app
    prune: true
    sourceRef:
      kind: GitRepository
      name: flux-system
      namespace: flux-system
    wait: false
  ```

  Create `kubernetes/apps/self-hosted/wishlist/app/kustomization.yaml`:

  ```yaml
  # yaml-language-server: $schema=https://json.schemastore.org/kustomization
  ---
  apiVersion: kustomize.config.k8s.io/v1beta1
  kind: Kustomization
  resources:
    - helmrelease.yaml
  ```

- [ ] **Step 4: Validate the Flux registration**

  Run:

  ```bash
  kustomize build kubernetes/apps/self-hosted
  ```

  Expected: PASS and output a `Kustomization` named `wishlist` targeting the
  `self-hosted` namespace.

- [ ] **Step 5: Commit the Flux registration**

  ```bash
  git add kubernetes/apps/self-hosted/kustomization.yaml \
    kubernetes/apps/self-hosted/wishlist/ks.yaml \
    kubernetes/apps/self-hosted/wishlist/app/kustomization.yaml
  git commit -m "feat(flux): register Wishlist application"
  ```

### Task 2: Deploy the hardened, persistent Wishlist workload

**Files:**
- Create: `kubernetes/apps/self-hosted/wishlist/app/helmrelease.yaml`
- Test: rendered HelmRelease and its generated Kubernetes resources

**Interfaces:**
- Consumes: the `app-template` OCIRepository in `flux-system`, the
  `self-hosted` namespace, the external Cilium Gateway, and Rook's
  `ceph-block` StorageClass.
- Produces: `wishlist` Deployment, Service, 10Gi RWO Ceph PVC, external
  HTTPRoute, and Gatus endpoint.

- [ ] **Step 1: Confirm the upstream image supports the planned security context**

  Run:

  ```bash
  curl --fail --silent --show-error \
    https://raw.githubusercontent.com/cmintey/wishlist/main/entrypoint.sh
  ```

  Expected: output sets `DATABASE_URL` to
  `/usr/src/app/data/prod.db` and starts the app after Prisma migrations,
  confirming both persisted mounts are necessary.

- [ ] **Step 2: Add the HelmRelease**

  Create `kubernetes/apps/self-hosted/wishlist/app/helmrelease.yaml`:

  ```yaml
  # yaml-language-server: $schema=https://raw.githubusercontent.com/bjw-s/helm-charts/main/charts/other/app-template/schemas/helmrelease-helm-v2.schema.json
  ---
  apiVersion: helm.toolkit.fluxcd.io/v2
  kind: HelmRelease
  metadata:
    name: &app wishlist
  spec:
    interval: 30m
    chartRef:
      kind: OCIRepository
      name: app-template
      namespace: flux-system

    values:
      controllers:
        wishlist:
          annotations:
            reloader.stakater.com/auto: "true"
          containers:
            wishlist:
              image:
                repository: ghcr.io/cmintey/wishlist
                tag: v0.66.0@sha256:073ab4de0f27a93a79410172bedfa3947bed4718f050396547516def790f1f49
              env:
                ORIGIN: https://wishlist.zebernst.dev
              probes:
                liveness: &probe
                  enabled: true
                  custom: true
                  spec:
                    httpGet:
                      path: /
                      port: &port 3280
                readiness: *probe
              resources:
                requests:
                  cpu: 10m
                  memory: 64Mi
                limits:
                  memory: 256Mi
              securityContext:
                allowPrivilegeEscalation: false
                readOnlyRootFilesystem: true
                capabilities: { drop: ["ALL"] }
      defaultPodOptions:
        priorityClassName: external-facing
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          runAsGroup: 1000
          fsGroup: 1000
          fsGroupChangePolicy: OnRootMismatch
          seccompProfile: { type: RuntimeDefault }
      service:
        wishlist:
          controller: *app
          ports:
            http:
              port: *port
      route:
        app:
          annotations:
            gatus.home-operations.com/endpoint: |
              name: "{{ .Release.Name }}"
              group: "{{ .Release.Namespace }}"
          hostnames:
            - "{{ .Release.Name }}.zebernst.dev"
          parentRefs:
            - name: external
              namespace: kube-system
              sectionName: https
      persistence:
        data:
          type: persistentVolumeClaim
          size: 10Gi
          accessMode: ReadWriteOnce
          storageClass: ceph-block
          advancedMounts:
            wishlist:
              wishlist:
                - path: /usr/src/app/data
                - path: /usr/src/app/uploads
        tmp:
          type: emptyDir
          globalMounts:
            - path: /tmp
  ```

- [ ] **Step 3: Render and validate the manifest**

  Run:

  ```bash
  flate test helmrelease --path ./kubernetes --allow-missing-secrets
  flate test kustomization --path ./kubernetes --allow-missing-secrets
  ```

  Expected: both commands exit 0. The rendered resources include an RWO PVC
  with `storageClassName: ceph-block`, a Service on port 3280, and an HTTPRoute
  for `wishlist.zebernst.dev` attached to the external Gateway.

- [ ] **Step 4: Commit the deployable workload**

  ```bash
  git add kubernetes/apps/self-hosted/wishlist/app/helmrelease.yaml
  git commit -m "feat(wishlist): deploy public Wishlist service"
  ```

### Task 3: Provision identity and complete post-deployment configuration

**Files:**
- Modify: `docs/superpowers/specs/2026-09-17-wishlist-design.md`
- Test: Pocket ID client, Wishlist login, signup, and public registry behavior

**Interfaces:**
- Consumes: reachable `https://wishlist.zebernst.dev`, the initial local
  Wishlist administrator, and a Pocket ID client secret stored in 1Password.
- Produces: native OIDC authentication through Pocket ID with public signup
  disabled.

- [ ] **Step 1: Deploy the committed manifest revision**

  Run:

  ```bash
  flux reconcile kustomization wishlist --namespace self-hosted --with-source
  kubectl --namespace self-hosted get helmrelease,pvc,httproute,pod \
    -l app.kubernetes.io/name=wishlist
  ```

  Expected: Flux reconciliation succeeds; the HelmRelease is Ready; the PVC is
  Bound; the HTTPRoute is Accepted and ResolvedRefs; and the pod is Ready.

- [ ] **Step 2: Register the Pocket ID client without storing its secret in Git**

  In Pocket ID at `https://id.zebernst.dev`, create a confidential OIDC client
  named `Wishlist` with exact redirect URI:

  ```text
  https://wishlist.zebernst.dev/login
  ```

  Store its generated client secret in the `wishlist` item in 1Password.
  Record the Pocket ID issuer URL, client ID, and client secret for the next
  step; do not place any of those values in repository files.

- [ ] **Step 3: Configure Wishlist through its supported administration UI**

  1. Open `https://wishlist.zebernst.dev` and use the setup wizard to create
     the initial local administrator.
  2. Open Administration Settings and turn off **Public Signup**.
  3. In the OIDC settings, set issuer to `https://id.zebernst.dev`, then enter
     the Pocket ID client ID and client secret.
  4. Save the settings and sign out.

- [ ] **Step 4: Verify public, identity, and monitoring behavior**

  Run:

  ```bash
  curl --fail --location --silent --show-error \
    https://wishlist.zebernst.dev/ > /dev/null
  ```

  Expected: exit 0. Then confirm a Pocket ID user can complete OIDC login,
  direct public signup is unavailable, an administrator can create an invite,
  and an unauthenticated public registry URL can still be viewed and claimed.
  Confirm the `wishlist` endpoint is healthy in
  `https://status.zebernst.dev`.

- [ ] **Step 5: Commit the completed operator runbook**

  Update the design specification only if the actual Pocket ID issuer or
  application behavior differs from the documented procedure. Then commit:

  ```bash
  git add docs/superpowers/specs/2026-09-17-wishlist-design.md
  git commit -m "docs(wishlist): record OIDC onboarding"
  ```
