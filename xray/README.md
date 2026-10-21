# Super Downloader — Xray

Bridges a VLESS+WS+TLS(+ECH) endpoint into a plain SOCKS5 listener on
`0.0.0.0:10808` inside the Railway private network.

## Why

YouTube, Instagram, and others sometimes block datacenter IPs. Routing
outbound traffic through a VLESS endpoint makes the extractors see a
residential-ish IP and dramatically improves success rates.

## Internal exposure only

The SOCKS5 listener is bound to `0.0.0.0` so Railway's WireGuard mesh
(which already encrypts traffic) can reach it at
`xray.railway.internal:10808`. It is **not** published publicly; do not
add a Railway public domain to this service.

## Consumer configuration
PROXY_URL=socks5://xray.railway.internal:10808

text

- **Bot**: `AiohttpSession(proxy=...)` (uses `aiohttp-socks` under the hood).
- **Worker**: yt-dlp's `--proxy` accepts `socks5://` directly.
- **API**: not needed.

Use `socks5://` (not `socks5h://`) because Railway's internal DNS already
resolves `.railway.internal` hostnames, and we want DNS resolution to happen
inside the mesh, not on Xray's upstream.

## Default VLESS

The default `VLESS_PROXY_URL` matches the spec (UUID
`cf8a6224-1855-45a0-be64-76289bac5b54`, server `104.19.49.238:443`, SNI
`misty-garden-fa6c-03a4df3e.pages.dev`, fp `chrome`, ECH
`cloudflare-ech.com+udp://1.1.1.1`, `type=ws`, `host=misty-garden-fa6c-03a4df3e.pages.dev`,
`path=/98643feed4c6`). Override via Railway Variables in production.