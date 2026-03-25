# OIXA Protocol — Pending Actions (Manual Steps Required)

> Claude Code completed everything it could autonomously.
> The items below are blocked by credentials, keys, or manual setup.
> Each item has exact instructions for when you're ready.

---

## 🔴 BLOCKER 1 — GitHub Secrets for Auto-Deploy (READY — just paste)

A dedicated CI/CD SSH key pair was generated (2026-03-25). The **public key is already installed** on the VPS at `root@64.23.235.34`.

**Go to:** https://github.com/ivoshemi-sys/oixa-protocol/settings/secrets/actions

Add these 3 secrets **exactly**:

| Secret name | Value |
|-------------|-------|
| `VPS_HOST` | `64.23.235.34` |
| `VPS_USER` | `root` |
| `VPS_SSH_KEY` | *(paste the private key below)* |

**Private key to paste for `VPS_SSH_KEY`:**
```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW
QyNTUxOQAAACDhuwUSljM/YUInknsg3nGq81W1+tczpvw4LMJwDEPdrAAAAKA76drNO+na
zQAAAAtzc2gtZWQyNTUxOQAAACDhuwUSljM/YUInknsg3nGq81W1+tczpvw4LMJwDEPdrA
AAAEAs9geBIMpjpSBu5OwopFdwXLGpaIX7vUTWPQs3gYauJ+G7BRKWMz9hQieSeyDecarz
VbX61zOm/DgswnAMQ92sAAAAGm9peGEtZ2l0aHViLWFjdGlvbnMtZGVwbG95AQID
-----END OPENSSH PRIVATE KEY-----
```

**After adding secrets:** every push to `main` auto-deploys via `.github/workflows/deploy.yml`.

---

## 🔴 BLOCKER 2 — Cold Wallet Address (Commission Sweep)

**What:** Commission sweep runs every 6h but accumulates in ledger until wallet is configured.

**When you have your cold wallet address:**
1. SSH to VPS: `ssh root@64.23.235.34`
2. Edit .env: `nano /opt/oixa-protocol/.env`
3. Add: `PROTOCOL_WALLET=0xYOUR_WALLET_ADDRESS`
4. Restart: `systemctl restart oixa-protocol`

**Note:** In Phase 2 this triggers real USDC transfers on Base mainnet.

---

## 🔴 BLOCKER 3 — PyPI API Token (Package Publish)

**What:** `oixa-protocol 0.1.0` package is built and ready.

**When you have your token:**
```bash
cd /Users/Openclaw/oixa-protocol/packages/oixa-protocol
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-PASTE_TOKEN_HERE python3 -m twine upload dist/*
```

**Get token:** https://pypi.org/manage/account/token/

---

## 🟡 PENDING 4 — Multi-Arbiter API Keys (GPT-4 + Gemini)

**What:** Multi-arbiter voting is implemented (2-of-3: Claude + GPT-4 + Gemini). Claude works if `ANTHROPIC_API_KEY` is set. Add the others for full 3-LLM voting.

**Add to `.env` on VPS** (`nano /opt/oixa-protocol/.env`):
```
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
```

Get keys: https://platform.openai.com/api-keys | https://aistudio.google.com/apikey

---

## 🟡 PENDING 5 — PostgreSQL: Keep DATABASE_URL After Each Deploy

**What:** `scripts/deploy.sh` copies local `.env` to VPS, overwriting the PostgreSQL `DATABASE_URL`.

**Current workaround (automated — run after each deploy):**
```bash
ssh root@64.23.235.34 'sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://oixa:oixa_secure_2026@localhost:5432/oixa|" /opt/oixa-protocol/.env && systemctl restart oixa-protocol'
```

**Permanent fix:** Add `DATABASE_URL=postgresql://oixa:oixa_secure_2026@localhost:5432/oixa` to your local `.env` (or update `deploy.sh` to merge VPS-specific vars instead of overwriting).

---

## 🟡 PENDING 6 — oixa.io Domain → VPS

Point `oixa.io` DNS to `64.23.235.34`:
- A record: `@` → `64.23.235.34`
- A record: `www` → `64.23.235.34`

Then on VPS:
```bash
ssh root@64.23.235.34
apt install -y certbot python3-certbot-nginx
certbot --nginx -d oixa.io -d www.oixa.io
```

---

## 🟡 PENDING 7 — Stripe Keys

```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## 🟡 PENDING 8 — Security Audit Follow-ups (see SECURITY_AUDIT.md)

Priority actions from the audit:
1. **Migrate contract `protocol` address to Gnosis Safe** — prevents single-key compromise (HIGH-01)
2. **Add escrow expiry + self-refund** to OIXAEscrow.sol (MEDIUM-01)
3. **Add ReentrancyGuard** (MEDIUM-02)

Slither + Mythril scan to be run after `solc` install on VPS:
```bash
ssh root@64.23.235.34
pip install solc-select slither-analyzer
solc-select install 0.8.20 && solc-select use 0.8.20
slither /opt/oixa-protocol/server/blockchain/contracts/OIXAEscrow.sol
```

---

## 🟡 PENDING 9 — LangChain Hub Publish

Toolkit at `agents/oixa_langchain.py`. See `agents/PUBLISH_TO_REGISTRIES.md`.

---

## ✅ COMPLETED (no action needed)

- [x] PostgreSQL on VPS — `db_backend: postgresql` confirmed ✅ (2026-03-25)
- [x] Daily backup cron on VPS — runs at 03:00 UTC ✅ (2026-03-25)
- [x] CI/CD SSH key pair generated and public key installed on VPS ✅ (2026-03-25)
- [x] Multi-arbiter (Claude + GPT-4 + Gemini, 2-of-3 voting) ✅ (2026-03-25)
- [x] Security audit — SECURITY_AUDIT.md written ✅ (2026-03-25)
- [x] End-to-end onboarding test — offer + auction + bid confirmed working ✅ (2026-03-25)
- [x] All "10 minutes" → "10 seconds" replaced across all files ✅ (2026-03-20)
- [x] Deploy to VPS via scripts/deploy.sh ✅ (2026-03-25)
- [x] PostgreSQL migration code (database.py has dual SQLite/PG adapter)
- [x] docker-compose.yml with postgres + oixa services
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
