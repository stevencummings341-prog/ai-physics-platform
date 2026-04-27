# Handoff: Public Share Tunnel (2026-04-24)

## Why This Handoff Exists

Another research team needs to use the physics experiments from
their own computers (e.g. over the campus LAN) without SSH access
to this cluster. This server has no public or campus-routable IP
— it's a Kubernetes-managed container (`8povf22jpsh6k-0`, DNS
search `...svc.cluster.local`, CGNAT IP `100.90.51.227`) reached
only through Cursor's outbound SSH tunnel. Direct inbound access
from the campus network is therefore not possible; the solution
is an outbound tunnel from this container to a public relay.

## What Was Added

- `share.sh` — one-shot public link manager at repo root.
- `launchers/bin/bore` — bore CLI v0.6.0 (x86_64-musl, 2.7 MB),
  statically linked, used as the default tunnel provider.
- README section **Sharing With Another Team (Public Link)**
  documenting the end-user workflow.
- `state/active_context.json` now has a `public_share` block.

## How It Works

```
Browser → http://bore.pub:<PORT>
               │  (bore.pub public edge TCP)
               ▼
bore client (this container)  →  127.0.0.1:5173 (Vite dev server)
               │  Vite proxy routes:
               │    /offer, /camera, /load_usd → :8080 (WebRTC HTTP)
               │    /ws                        → :30000 (control/telemetry)
               │    /video_feed                → :8080 (WS-JPEG fallback)
               ▼
            Isaac Sim backend
```

The remote viewer's browser sees a single origin; Vite proxies
WebSocket + WebRTC-signaling + WS-JPEG video through the same
port. `allowedHosts: true` in `frontend/vite.config.ts` means
Vite accepts the Host header that bore.pub rewrites in. WebRTC
media (UDP) cannot traverse a TCP tunnel; after the ~8 s ICE
timeout, `WebRTCIsaacViewer.tsx` auto-falls-back to WS-JPEG
which traverses fine.

## Provider Choice

Tried these tunnel services from this container — results:

| Provider            | Status | Notes |
|---------------------|--------|-------|
| **bore.pub**        | works  | pure TCP, open-source, no TTL, HTTP only. **default** |
| **localhost.run**   | works  | HTTPS, SSH-based, anonymous URL expires in ~1 h. Fallback for HTTPS-required viewers: `./share.sh --via lhr` |
| Cloudflare Quick Tunnel | **blocked** | egress firewall drops connections to 104.16.0.0/12 (Cloudflare anycast) |
| ngrok               | **blocked** | `connect.ngrok-agent.com:443` unreachable |
| serveo.net          | connection closed | now requires public-key auth |
| pinggy.io (anon)    | works but unstable | 60-min TTL + frequent connection resets |

bore was picked as default for simplicity (no SSH auth dependency,
no TTL) and a single binary. localhost.run remains available as
the HTTPS fallback via `./share.sh --via lhr`.

## Usage Recap

```bash
./launch.sh --status   # confirm Frontend + WebRTC + WebSocket all RUNNING
./share.sh             # start bore tunnel in background, print URL
./share.sh --url       # print the current public URL
./share.sh --status    # show tunnel + backend status
./share.sh --stop      # close tunnel
./share.sh --restart   # new URL
./share.sh --via lhr   # HTTPS via localhost.run instead
```

## Gotchas for Future Agents

1. **Do not verify the tunnel by curling it from inside this
   container.** The traffic traverses the cluster egress twice
   (once as bore-client control channel, once as the test HTTP
   client), and the egress conntrack / NAT table saturates after
   ~2 requests, producing false "Connection timed out" errors.
   External viewers only transit the egress once (inbound) and do
   not hit this limit. Verify by having a real remote browser
   open the URL, or by doing one isolated curl at most.

2. **New URL every restart.** bore.pub hands out a fresh random
   port for each control-channel reconnect. Always re-share after
   `--restart` or a container reboot. Use `./share.sh --url` to
   fetch the current URL for scripts.

3. **Isaac Sim must be up separately.** `share.sh` only exposes
   the Vite frontend; if the Isaac Sim backend is down, viewers
   will load the UI and then see "connection failed" when they
   try to drive an experiment. Always run
   `./launch.sh --status` before sharing the URL.

4. **Video first-paint delay (~8 s).** First-time remote viewers
   see a spinner while WebRTC times out and the viewer falls back
   to WS-JPEG. This is by design — do not change the ICE timeout
   without also changing the fallback logic in
   `frontend/src/components/WebRTCIsaacViewer.tsx`.

5. **`pkill -f 'ssh.*...'` is dangerous in this container.**
   Cursor's shell wrapper keeps previous commands in its
   process-table line, so broad patterns can kill the active
   shell. `share.sh` uses very specific patterns
   (`bore local 5173` / `ssh .*-R 80:localhost:5173 .*$LHR_HOST`)
   that cannot match the wrapper. Keep it that way.

## Related Files

- `share.sh` — tunnel manager
- `launchers/bin/bore` — bore v0.6.0 binary
- `README.md` — user-facing section "Sharing With Another Team"
- `state/active_context.json` — machine-readable `public_share` block
- `frontend/vite.config.ts` — `allowedHosts: true` + proxy rules
- `frontend/src/components/WebRTCIsaacViewer.tsx` — WebRTC →
  WS-JPEG auto-fallback

## Not Done / Open Items

- No concurrency control on the backend: multiple remote viewers
  on the same URL all drive the same Isaac Sim scene; if two
  people click "Start" simultaneously, the experiment state races.
  Current usage assumption is **one viewer at a time**, as per
  the user's stated requirement on 2026-04-24.
- No authentication on the public URL. Anyone who knows the bore
  port can drive the experiment. If we later need access control,
  either rotate the URL more often, switch to `--via lhr` with a
  named localhost.run account + IP allowlist, or front the Vite
  server with HTTP-basic-auth at the proxy layer.
