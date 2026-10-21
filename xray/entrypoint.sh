#!/bin/sh
# Translate VLESS_PROXY_URL into an Xray config with a SOCKS5 inbound on
# 0.0.0.0:10808. Railway's private WireGuard mesh provides transport
# encryption between services, so plain SOCKS5 is fine inside the mesh.
set -eu

VLESS_URL="${VLESS_PROXY_URL:-}"
if [ -z "$VLESS_URL" ]; then
  # Default matches the spec — safe to ship because it's a public share link
  # and NOT a secret. Override via Railway Variables in production.
  VLESS_URL='vless://cf8a6224-1855-45a0-be64-76289bac5b54@104.19.49.238:443?encryption=none&security=tls&sni=misty-garden-fa6c-03a4df3e.pages.dev&fp=chrome&ech=cloudflare-ech.com%2Budp%3A%2F%2F1.1.1.1&type=ws&host=misty-garden-fa6c-03a4df3e.pages.dev&path=%2F98643feed4c6#super-downloader'
fi

echo "[xray] parsing VLESS_PROXY_URL"
CONFIG=$(python3 - "$VLESS_URL" <<'PY'
import json, os, sys, urllib.parse

raw = sys.argv[1]
u = urllib.parse.urlsplit(raw)
assert u.scheme == "vless", f"expected vless://, got {u.scheme}"

uuid = u.username
host = u.hostname
port = u.port or 443
q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query, keep_blank_values=True).items()}

sni   = q.get("sni") or q.get("host") or host
fp    = q.get("fp", "chrome")
ech   = q.get("ech")
typ   = q.get("type", "tcp")
ws_host = q.get("host") or sni
ws_path = urllib.parse.unquote(q.get("path", "/"))
security = q.get("security", "tls")

stream = {"network": typ, "security": security}
if typ == "ws":
    stream["wsSettings"] = {
        "path": ws_path,
        "headers": {"Host": ws_host},
    }
if security == "tls":
    stream["tlsSettings"] = {
        "serverName": sni,
        "fingerprint": fp,
        "allowInsecure": False,
    }
    if ech:
        stream["tlsSettings"]["echConfigList"] = ech

config = {
    "log": {"loglevel": "warning", "access": "/dev/null", "error": "/dev/stderr"},
    "inbounds": [
        {
            "tag": "socks-in",
            "listen": "0.0.0.0",
            "port": 10808,
            "protocol": "socks",
            "settings": {
                "auth": "noauth",
                "udp": True,
                "ip": "0.0.0.0",
            },
            "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
        }
    ],
    "outbounds": [
        {
            "tag": "vless-out",
            "protocol": "vless",
            "settings": {
                "vnext": [
                    {
                        "address": host,
                        "port": port,
                        "users": [
                            {"id": uuid, "encryption": "none", "flow": ""},
                        ],
                    }
                ],
            },
            "streamSettings": stream,
        },
        {"tag": "direct", "protocol": "freedom"},
        {"tag": "block", "protocol": "blackhole"},
    ],
    "routing": {
        "rules": [
            {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
        ]
    },
}
print(json.dumps(config))
PY
)

echo "$CONFIG" > /etc/xray/config.json

echo "[xray] starting SOCKS5 on 0.0.0.0:10808 -> $(echo "$VLESS_URL" | sed 's|@.*|@<redacted>|')"
exec /usr/local/bin/xray -c /etc/xray/config.json