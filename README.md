<div align="center">

<img src="https://github.com/user-attachments/assets/0248f379-cc4a-4a59-a400-014a750c61fa" align="center" width="144px" height="144px"/>


### My homelab k8s cluster <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/2728/512.gif" alt="🚀" width="16" height="16">

_... automated via [Flux](https://github.com/fluxcd/flux2), [Renovate](https://github.com/renovatebot/renovate) and [GitHub Actions](https://github.com/features/actions)_ <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f916/512.gif" alt="🤖" width="16" height="16">

</div>

<div align="center">

[![Talos](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Ftalos_version&style=for-the-badge&logo=talos&logoColor=white&color=blue&label=%20)](https://talos.dev)&nbsp;&nbsp;
[![Kubernetes](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fkubernetes_version&style=for-the-badge&logo=kubernetes&logoColor=white&color=blue&label=%20)](https://kubernetes.io)&nbsp;&nbsp;
[![Flux](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fflux_version&style=for-the-badge&logo=flux&logoColor=white&color=blue&label=%20)](https://fluxcd.io)&nbsp;&nbsp;
[![Renovate](https://img.shields.io/github/actions/workflow/status/zebernst/homelab/renovate.yaml?branch=main&label=&logo=renovate&style=for-the-badge&color=blue)](https://github.com/zebernst/homelab/actions/workflows/renovate.yaml)

</div>

<div align="center">

[![Home-Internet](https://img.shields.io/uptimerobot/status/m798207245-e361357b4ae0adccce695dd9?style=for-the-badge&logo=ubiquiti&logoColor=white&logoSize=auto&label=Home%20Internet&color=brightgreen)](https://status.zebernst.dev)&nbsp;&nbsp;
[![Status-Page](https://img.shields.io/uptimerobot/status/m798207270-986abc3b5ee42d8f51b9fc5c?color=brightgreeen&label=Status%20Page&style=for-the-badge&logo=statuspage&logoColor=white)](https://status.zebernst.dev)&nbsp;&nbsp;
[![Alertmanager](https://img.shields.io/endpoint?url=https%3A%2F%2Fhealthchecks.io%2Fb%2F2%2F75190d22-c52a-410d-9f45-9bd7c95cbb96.shields?color=brightgreeen&label=Alertmanager&style=for-the-badge&logo=prometheus&logoColor=white)](https://status.zebernst.dev)
</div>

<div align="center">

[![Age-Days](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fcluster_age_days&style=flat-square&label=Age)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Uptime-Days](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fcluster_uptime_days&style=flat-square&label=Uptime)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Node-Count](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fcluster_node_count&style=flat-square&label=Nodes)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Pod-Count](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fcluster_pod_count&style=flat-square&label=Pods)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![CPU-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fcluster_cpu_usage&style=flat-square&label=CPU)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Memory-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fcluster_memory_usage&style=flat-square&label=Memory)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Power-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.zebernst.dev%2Fcluster_power_usage&style=flat-square&label=Power)](https://github.com/kashalls/kromgo)

</div>

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f4a1/512.gif" alt="✏" width="20" height="20"> Overview

This is a repository for my home infrastructure and Kubernetes cluster. I try to adhere to Infrastructure as Code (IaC) and GitOps practices using tools like [Kubernetes](https://github.com/kubernetes/kubernetes), [Flux](https://github.com/fluxcd/flux2), [Renovate](https://github.com/renovatebot/renovate) and [GitHub Actions](https://github.com/features/actions).

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f331/512.gif" alt="🌱" width="20" height="20"> Kubernetes

This hyper-converged cluster runs [Talos Linux](https://github.com/siderolabs/talos), an immutable and ephemeral Linux distribution tailored for [Kubernetes](https://github.com/kubernetes/kubernetes), and is deployed on bare-metal Minisforum MS-01 mini-PCs. Currently, persistent storage is provided via [Rook](https://github.com/rook/rook) in order to enable resilient block-, file-, and object-storage within the cluster. A Synology NAS handles media file storage and backups, and is also available as an alternate storage location with the help of a [custom fork](https://github.com/zebernst/synology-csi-talos) of the official Synology CSI for workloads that should not be hyper-converged. The cluster is designed to enable a full teardown without any data loss.

🔸 _[Click here](./kubernetes/bootstrap/talos/talconfig.yaml) to see my Talos configuration._

There is a template at [onedr0p/cluster-template](https://github.com/onedr0p/cluster-template) if you want to follow along with many of the practices I use here.

### Core Components

[//]: # (- [actions-runner-controller]&#40;https://github.com/actions/actions-runner-controller&#41;: Self-hosted Github runners.)
- [cert-manager](https://github.com/cert-manager/cert-manager): Manage SSL certificates for services in my cluster.
- [cilium](https://github.com/cilium/cilium): eBPF-based networking for my workloads.
- [cloudflared](https://github.com/cloudflare/cloudflared): Enables Cloudflare secure access to my services.
- [external-dns](https://github.com/kubernetes-sigs/external-dns): Automatically syncs ingress DNS records to a DNS provider.
- [external-secrets](https://github.com/external-secrets/external-secrets): Managed Kubernetes secrets using [1Password Connect](https://github.com/1Password/connect).
- [ingress-nginx](https://github.com/kubernetes/ingress-nginx): Kubernetes ingress controller using NGINX as a reverse proxy and load balancer.
- [rook](https://github.com/rook/rook): Distributed block, file, and object storage for stateful workloads.
- [spegel](https://github.com/spegel-org/spegel): Stateless cluster-local OCI registry mirror.
- [volsync](https://github.com/backube/volsync): Backup and recovery of persistent volume claims.

### GitOps

[Flux](https://github.com/fluxcd/flux2) monitors my [kubernetes](./kubernetes) folder (see Directories below) and implements changes to my cluster based on the YAML manifests.

Flux operates by recursively searching the [kubernetes/apps](./kubernetes/apps) folder until it locates the top-level `kustomization.yaml` in each directory. It then applies all the resources listed in it. This `kustomization.yaml` typically contains a namespace resource and one or more Flux kustomizations. These Flux kustomizations usually include a `HelmRelease` or other application-related resources, which are then applied.

[Renovate](https://github.com/renovatebot/renovate) monitors my **entire** repository for dependency updates, automatically creating a PR when updates are found. When the relevant PRs are merged, [Flux](https://github.com/fluxcd/flux2) then applies the changes to my cluster.

### Directories

This Git repository contains the following directories under [kubernetes/](./kubernetes).

```sh
📁 kubernetes
├── 📁 apps           # applications
├── 📁 bootstrap      # bootstrap procedures
├── 📁 components     # reusable kustomize components
└── 📁 flux           # core flux configuration
```

### Cluster layout

This is a high-level look how Flux deploys my applications with dependencies. Below there are 3 Flux kustomizations `cloudnative-pg`, `postgres-cluster`, and `atuin`. `cloudnative-pg` is the first app that needs to be running and healthy before `postgres-cluster` and once `postgres-cluster` is healthy, then `atuin` will be deployed.

```mermaid
graph TD;
  id1>Kustomization: cluster] -->|Creates| id2>Kustomization: cluster-apps];
  id2>Kustomization: cluster-apps] -->|Creates| id3>Kustomization: cloudnative-pg];
  id2>Kustomization: cluster-apps] -->|Creates| id5>Kustomization: postgres-cluster]
  id2>Kustomization: cluster-apps] -->|Creates| id8>Kustomization: atuin]
  id3>Kustomization: cloudnative-pg] -->|Creates| id4[HelmRelease: cloudnative-pg];
  id5>Kustomization: postgres-cluster] -->|Depends on| id3>Kustomization: cloudnative-pg];
  id5>Kustomization: postgres-cluster] -->|Creates| id10[Postgres Cluster];
  id8>Kustomization: atuin] -->|Creates| id9(HelmRelease: atuin);
  id8>Kustomization: atuin] -->|Depends on| id5>Kustomization: postgres-cluster];
```

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f30e/512.gif" alt="🌎" width="20" height="20"> Networking & DNS

<details>
  <summary>Click to see a high-level phsyical network diagram</summary>

  <img src="docs/assets/network-diagram.excalidraw.svg" align="center" width="600px" alt="network"/>
</details>

Apps hosted on my cluster are exposed using any combination of three different methods, depending on their use-case, security requirements, and intended audience. All three methods utilise fully encrypted HTTPS connections – TLS certificates are automatically provisioned and renewed by [Cert Manager](https://cert-manager.io) for each application.

### Local Network

The first and easiest way that an app can be exposed is strictly on my local network. This is most often used for apps and services that have to do with home automation – given that every smart home device is on my local network, there is no need to expose e.g. a supporting service like MQTT any further than that.

Local deployments are accomplished by creating an Ingress of type `internal`, which will register a virtual IP for the service in a designated subnet (advertised via BGP) and provision a DNS record on the router with  the [ExternalDNS webhook provider for UniFi](https://github.com/kashalls/external-dns-unifi-webhook).

### Privately Exposed (Tailscale)

The second and most common way that an app can be exposed is via [Tailscale](https://tailscale.com/kb/1236/kubernetes-operator). Creating an Ingress with the `tailscale` class will expose the application to my Tailnet, and [automagically](https://tailscale.com/kb/1081/magicdns) configure DNS records. Most self-hosted apps and dashboards are exposed using this Ingress class, so that they are accessible on my personal devices at a consistent URL no matter if I'm at home or abroad.

Tailscale also serves as a Kubernetes auth proxy, which I use in conjunction with the [Nautik](https://nautik.io/) iOS app to monitor and administer my Kubernetes cluster on-the-go.

### Publicly Exposed

The final and least common way to expose an app is via `cloudflared`, the [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) daemon. By routing all external traffic through Cloudflare's infrastructure, I gain the benefits of their global security infrastructure (notably DDoS protection). This is generally used for webhook endpoints which require access from the wider Internet, though I do expose a select few apps for friends and family.

Creating an `external` Ingress will trigger using [ExternalDNS](https://github.com/kubernetes-sigs/external-dns) to provision a CNAME DNS record on Cloudflare which points at the Cloudflare Tunnel endpoint. The tunnel routes traffic securely into my cluster, where the ingress controller further routes it to the destination Service.

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f48e/512.gif" alt="☁️" width="20" height="20"> Cloud Dependencies

While most of my infrastructure and workloads are self-hosted, I do rely upon the cloud for certain key parts of my setup. This saves me from having to worry about three things:
1. Dealing with chicken/egg scenarios
2. Critical services that need to be accessible, whether my cluster is online or not.
3. The "hit by a bus" scenario - what happens to critical apps (e.g. Email, Password Manager, Photos, etc.) that my friends and family rely on when I'm no longer around.

Alternative solutions to the first two of these problems would be to host a Kubernetes cluster in the cloud and deploy applications like [Vault](https://www.vaultproject.io/), [Vaultwarden](https://github.com/dani-garcia/vaultwarden), [ntfy](https://ntfy.sh/), and [Gatus](https://gatus.io/); however, maintaining another cluster and monitoring another group of workloads would frankly be more time and effort than I am willing to put in. (and would probably cost more or equal out to the same costs as described below)

| Service                                     | Use                                                               | Cost           |
|---------------------------------------------|-------------------------------------------------------------------|----------------|
| [1Password](https://1password.com/)         | Secrets with [External Secrets](https://external-secrets.io/)     | ~$36/yr        |
| [Cloudflare](https://www.cloudflare.com/)   | Domain/DNS                                                        | ~$24/yr        |
| [Backblaze](https://www.backblaze.com)      | S3-compatible object storage                                      | ~$36/yr        |
| [GitHub](https://github.com/)               | Hosting this repository and continuous integration/deployments    | Free           |
| [Pushover](https://pushover.net/)           | Kubernetes Alerts and application notifications                   | $5 OTP         |
| [UptimeRobot](https://uptimerobot.com/)     | Monitoring internet connectivity and external facing applications | Free           |
| [Healthchecks.io](https://healthchecks.io/) | Dead man's switch for monitoring cron jobs                        | Free           |
|                                             |                                                                   | Total: ~$10/mo |

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/2699_fe0f/512.gif" alt="⚙" width="20" height="20"> Hardware

<details>
  <summary>Click to see my rack</summary>

  ![1B51EA7B-3517-4614-B7FC-A15943763705_1_105_c](https://github.com/user-attachments/assets/dd9a2259-7ff3-42d4-a420-2711557483eb)
</details>


| Device                      | Count | OS Disk     | Data Disk                                                              | RAM  | OS          | Purpose                    |
|-----------------------------|-------|-------------|------------------------------------------------------------------------|------|-------------|----------------------------|
| MS-01 (i9-12900H)           | 3     | 1TB M.2 SSD | 2TB M.2 SSD (Rook)                                                     | 96GB | Talos Linux | Kubernetes (control plane) |
| Custom build ([link][pcpp]) | 1     | 1TB M.2 SSD | 4TB M.2 SSD                                                            | 96GB | Talos Linux | Kubernetes (gpu workloads) |
| Synology DS918+             | 1     | -           | 2x14TB&nbsp;HDD + 2x18TB&nbsp;HDD + 2x1TB&nbsp;SSD&nbsp;R/W&nbsp;Cache | 16GB | DSM 7       | NAS/NFS/Backup             |
| JetKVM                      | 2     | -           | -                                                                      | -    | -           | KVM                        |
| Home Assistant Yellow       | 1     | 8GB eMMC    | 1TB M.2 SSD                                                            | 4GB  | HAOS        | Home Automation            |
| UniFi UDM Pro               | 1     | -           | -                                                                      | -    | UniFi OS    | Router                     |
| UniFi USW Pro 24 PoE        | 1     | -           | -                                                                      | -    | UniFi OS    | Core Switch                |
| Unifi USP PDU Pro           | 1     | -           | -                                                                      | -    | UniFi OS    | PDU                        |
| CyberPower OR500LCDRM1U     | 1     | -           | -                                                                      | -    | -           | UPS                        |

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f64f/512.gif" alt="🙏" width="20" height="20"> Gratitude and Thanks

Huge thank-you to the folks over at the [Home Operations](https://github.com/home-operations) community, especially [@onedrop](https://github.com/onedr0p), [@bjw-s](https://github.com/bjw-s), and [@buroa](https://github.com/buroa) – their home-ops repos have been an amazing resource to draw upon.

Be sure to check out [kubesearch.dev](https://kubesearch.dev) for further ideas and reference for deploying applications on Kubernetes.

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f6a7/512.gif" alt="🚧" width="20" height="20"> Changelog

See the latest [release](https://github.com/zebernst/homelab/releases/latest) notes.

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/2696_fe0f/512.gif" alt="⚖" width="20" height="20"> License

See [LICENSE](./LICENSE).

[pcpp]: https://pcpartpicker.com/b/qLrD4D
