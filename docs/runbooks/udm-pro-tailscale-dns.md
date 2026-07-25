# UDM Pro: DNS over Tailscale stops working

## Context

Tailscale split DNS is configured to resolve `zebernst.dev` and `.internal` domains using the UDM Pro as the nameserver. This allows tailnet clients (phones, laptops off-site, etc.) to reach internally-hosted apps by name — DNS records for those apps are synced to the UDM Pro's dnsmasq via ExternalDNS.

When this is working correctly, a query for e.g. `myapp.zebernst.dev` from a tailnet client:
1. Tailscale MagicDNS routes the query to the UDM Pro's IP (per the split DNS nameserver config)
2. The query arrives on the `tailscale0` interface of the UDM Pro
3. dnsmasq resolves it from the records ExternalDNS has synced

**Symptoms:** DNS queries for internal apps time out from tailnet clients (off-LAN). Apps are unreachable by hostname even though Tailscale connectivity itself is up. Devices on the local LAN are unaffected.

**Cause:** dnsmasq on UniFi OS only listens on traditional bridge interfaces (br0, br32, etc.) as defined in the auto-generated `/run/dnsmasq.dns.conf.d/main.conf`. The `tailscale0` interface is not included, so DNS requests arriving from tailnet clients are silently dropped.

## Immediate fix

SSH into the UDM Pro and restart the service that injects the tailscale0 dnsmasq config:

```sh
systemctl restart tailscale-dnsmasq
```

Verify DNS is resolving again from a tailnet client.

## How it works

A custom oneshot systemd service (`tailscale-dnsmasq.service`) runs after `tailscaled` starts. It executes `/data/on_boot.d/20-tailscale-dnsmasq.sh`, which:

1. Creates `/run/dnsmasq.dns.conf.d/` if it doesn't exist
2. Writes a dnsmasq config that adds `tailscale0` to the listening interfaces
3. Waits up to 10 seconds for `tailscale0` to appear
4. Restarts dnsmasq

This service is enabled and persists across reboots, but can stop being effective if UniFi OS regenerates its dnsmasq config and overwrites the interface list.

## Re-deploying from scratch

If the service or boot script is missing (e.g. after a UDM Pro firmware reset), recreate it:

**`/data/on_boot.d/20-tailscale-dnsmasq.sh`:**

```sh
#!/bin/sh
mkdir -p /run/dnsmasq.dns.conf.d
cat > /run/dnsmasq.dns.conf.d/tailscale.conf <<'EOF'
interface=tailscale0
EOF

# Wait for tailscale0 to come up (up to 10s)
for i in $(seq 1 10); do
    ip link show tailscale0 >/dev/null 2>&1 && break
    sleep 1
done

systemctl restart dnsmasq
```

```sh
chmod +x /data/on_boot.d/20-tailscale-dnsmasq.sh
```

**`/etc/systemd/system/tailscale-dnsmasq.service`:**

```ini
[Unit]
Description=Configure dnsmasq for Tailscale interface
After=tailscaled.service

[Service]
Type=oneshot
ExecStart=/data/on_boot.d/20-tailscale-dnsmasq.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```sh
systemctl daemon-reload
systemctl enable --now tailscale-dnsmasq
systemctl status tailscale-dnsmasq
```

## References

- [SierraSoftworks/tailscale-unifi#122](https://github.com/SierraSoftworks/tailscale-unifi/issues/122)
