# OIXA Protocol — Pending Actions (Manual Steps Required)

> Claude Code completed everything it could autonomously.
> The items below are blocked by credentials, keys, or manual setup.
> Each item has exact instructions for when you're ready.

---

## 🔴 BLOCKER 1 — VPS SSH Key (Deploy)

**What:** Auto-deploy via GitHub Actions requires your SSH key authorized on the VPS.

**Command (run once from this Mac):**
```bash
ssh-copy-id root@64.23.235.34
```

If you don't have a key yet:
```bash
ssh-keygen -t ed25519 -C "oixa-deploy"
ssh-copy-id root@64.23.235.34
```

**Then add to GitHub Secrets:**
Go to: https://github.com/ivoshemi-sys/oixa-protocol/settings/secrets/actions
Add these 3 secrets:
- `VPS_HOST` = `64.23.235.34`
- `VPS_USER` = `root`
- `VPS_SSH_KEY` = paste your private key (`cat ~/.ssh/id_ed25519`)

**After this is done:** every push to `main` auto-deploys. The workflow is at `.github/workflows/deploy.yml`.

---

## 🔴 BLOCKER 2 — Cold Wallet Address (Commission Sweep)

**What:** Commission sweep runs every 6h but sends to `PENDING_WALLET` until you configure this.

**When you have your cold wallet address:**
1. Add to `.env` on the VPS:
   ```
   PROTOCOL_WALLET=0xYOUR_WALLET_ADDRESS
   ```
2. Restart the service:
   ```bash
   ssh root@64.23.235.34 'systemctl restart oixa-protocol'
   ```

**Phase 2 note:** In Phase 2 this will trigger real USDC transfers on Base mainnet via the blockchain escrow client. Currently it records the intent in the ledger and sends a Telegram alert.

---

## 🔴 BLOCKER 3 — PyPI API Token (Package Publish)

**What:** `oixa-protocol 0.1.0` package is built and ready. Needs your PyPI token to upload.

**When you have your token:**
```bash
cd /Users/Openclaw/oixa-protocol/packages/oixa-protocol
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-PASTE_TOKEN_HERE python3 -m twine upload dist/*
```

**Get token:** https://pypi.org/manage/account/token/

---

## 🔴 BLOCKER 4 — First VPS Deploy (one-time setup)

**What:** The VPS needs to be provisioned once before auto-deploy can work.

**Run from this Mac:**
```bash
bash scripts/deploy.sh 64.23.235.34 root
```

This script:
- Installs Python, nginx, ufw
- Clones the repo
- Creates a systemd service
- Opens ports 22, 80, 443, 8000
- Runs a health check

**After this:** GitHub Actions handles all future deploys automatically.

---

## 🟡 PENDING 5 — LangChain Hub Publish

Toolkit code is at `agents/oixa_langchain.py`. Need a LangChain Hub account to publish.
See `agents/PUBLISH_TO_REGISTRIES.md` for instructions.

---

## 🟡 PENDING 6 — Stripe Keys

Stripe Crypto Onramp is fully implemented. Activate by adding to `.env`:
```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## 🟡 PENDING 7 — oixa.io Domain → VPS

Point `oixa.io` DNS to `64.23.235.34`:
- A record: `@` → `64.23.235.34`
- A record: `www` → `64.23.235.34`

Then set up nginx + Let's Encrypt on the VPS:
```bash
ssh root@64.23.235.34
apt install -y nginx certbot python3-certbot-nginx
certbot --nginx -d oixa.io -d www.oixa.io
```

Configure nginx to proxy to port 8000 and serve `server/static/index.html` at root.

---

## ✅ COMPLETED (no action needed)

- [x] PostgreSQL migration code (database.py has dual SQLite/PG adapter)
- [x] docker-compose.yml with postgres + oixa services
- [x] Rate limiter removed (now unlimited — set MAX_REQUESTS_PER_MINUTE=0)
- [x] Commission sweep every 6h (server/core/commission_sweep.py)
- [x] Daily DB backup (server/core/backup.py + scripts/backup.sh)
- [x] Telegram alerts: escrow, payment, dispute, bid, auction, sweep, server start
- [x] Stripe Crypto Onramp fully implemented
- [x] GitHub Actions workflow (auto-deploy on push to main)
- [x] Landing page (server/static/index.html) — served at /landing
- [x] Dashboard (server/static/dashboard.html) — served at /dashboard
- [x] Developer docs (docs/quickstart.md + docs/api-reference.md)
- [x] Registry files: LangChain, CrewAI, AutoGPT, Haystack, Composio, AgentOps, Semantic Kernel, A2A
- [x] Discovery endpoints: MCP, A2A, OpenAI plugin, /.well-known/*
- [x] PyPI package built (dist/ ready for upload)
