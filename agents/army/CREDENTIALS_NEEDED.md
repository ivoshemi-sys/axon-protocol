# OIXA Diffusion Army — Credenciales necesarias
## Ordenadas por impacto en difusión

---

## 🔴 CRÍTICO — Sin esto el ejército no puede actuar

### 1. Twitter/X API — xurl (Impacto: ★★★★★)
**Activa:** community-manager, creador-contenido, xurl skill
**Qué permite:** Posts automáticos, búsqueda de threads, respuestas, DMs

**Cómo obtenerlas:**
1. Ir a https://developer.twitter.com/en/portal/dashboard
2. Crear una nueva App (Free tier alcanza para búsqueda y posting básico)
3. En "Keys and Tokens" → generar todo:
   - API Key (Consumer Key)
   - API Secret (Consumer Secret)
   - Access Token
   - Access Token Secret
   - Bearer Token

**Configurar xurl:**
```bash
xurl auth login
# Seguir el proceso OAuth interactivo
# O configurar manualmente:
xurl auth add --name oixa \
  --consumer-key TU_API_KEY \
  --consumer-secret TU_API_SECRET \
  --access-token TU_ACCESS_TOKEN \
  --access-token-secret TU_ACCESS_TOKEN_SECRET
xurl whoami  # verificar
```

**Nivel de cuenta recomendado:** Basic ($100/mes) o Free (con límites)
**Tier Free:** 1,500 tweets/mes write, 10,000 reads/mes — suficiente para empezar.

---

### 2. GitHub Personal Access Token — Impacto: ★★★★★
**Activa:** protocolo-director, diffusion agent (PRs automáticos), gh-issues skill, github skill

**Qué permite:**
- Abrir issues en repos de LangChain, CrewAI, AutoGPT, etc.
- Crear PRs automáticos en google-a2a/a2a-samples y AutoGPT
- Fork + commit + PR desde el diffusion agent

**Cómo obtenerlo:**
1. Ir a https://github.com/settings/tokens
2. "Generate new token (classic)"
3. Scopes necesarios:
   - `repo` (full access) — para crear issues, PRs, forks
   - `read:user` — para buscar repos
4. Copiar el token (solo se muestra una vez)

**Configurar:**
```bash
# En el VPS (para diffusion agent)
echo "GITHUB_TOKEN=ghp_tu_token_aqui" >> /opt/oixa-protocol/.env
systemctl restart oixa-diffusion

# En local (para protocolo-director via gh CLI)
gh auth login --with-token <<< "ghp_tu_token_aqui"
# O configurar en OpenClaw:
# openclaw config set github.token ghp_tu_token_aqui
```

---

## 🟠 ALTO IMPACTO — Siguiente paso inmediato

### 3. Discord Bot Token — Impacto: ★★★★☆
**Activa:** discord skill (community-manager, protocolo-director)

**Qué permite:** Presencia en servidores de LangChain, CrewAI, AutoGPT, Hugging Face

**Cómo obtenerlo:**
1. Ir a https://discord.com/developers/applications
2. New Application → "OIXA Protocol"
3. Bot → Reset Token → copiar
4. OAuth2 → URL Generator → bot + permissions:
   - Send Messages, Read Message History, Add Reactions
5. Invitar el bot a los servidores target

**Configurar en OpenClaw:**
```bash
openclaw config set channels.discord.token "BOT_TOKEN_AQUI"
# Después de esto: openclaw skills check  →  discord ✅ ready
```

**Servidores a unirse primero:**
- LangChain Discord: https://discord.gg/6adMQxSpJS
- CrewAI Discord: https://discord.gg/X4JWnZnxPb
- AutoGPT Discord: https://discord.gg/autogpt
- Hugging Face Discord: https://discord.gg/hugging-face-879548962464493619
- Fetch.ai Discord: https://discord.gg/fetchai

---

### 4. dev.to API Key — Impacto: ★★★★☆
**Activa:** documentador, creador-contenido

**Qué permite:** Publicar artículos en dev.to programáticamente

**Cómo obtenerla:**
1. Ir a https://dev.to/settings/extensions
2. "Generate API Key"
3. Nombre: "OIXA Diffusion Agent"

**Configurar en OpenClaw (agente documentador):**
Agregar en TOOLS.md del agente:
```
DEV_TO_API_KEY=tu_key_aqui
```

**API de publicación:**
```bash
curl -X POST https://dev.to/api/articles \
  -H "api-key: TU_KEY" \
  -H "Content-Type: application/json" \
  -d '{"article": {"title": "...", "body_markdown": "...", "published": true, "tags": ["ai","agents","usdc"]}}'
```

---

### 5. Reddit — PRAW Credentials — Impacto: ★★★☆☆
**Activa:** community-manager (agent-reach skill con Reddit)

**Qué permite:** Monitorear y comentar en r/LangChain, r/MachineLearning, r/AIAgents

**Cómo obtenerlas:**
1. Ir a https://www.reddit.com/prefs/apps
2. "Create App" → Script
3. Guardar:
   - client_id
   - client_secret
   - username (cuenta Reddit)
   - password

**Nota:** Usar cuenta separada para posting de OIXA, no la personal.

---

## 🟡 MEDIO PLAZO

### 6. Medium API — Impacto: ★★★☆☆
**Activa:** creador-contenido (cross-posting de artículos)

1. Ir a https://medium.com/me/settings
2. "Integration tokens" → Generate
3. API: `POST https://api.medium.com/v1/users/{userId}/posts`

---

### 7. LinkedIn Credentials — Impacto: ★★★☆☆
**Activa:** community-manager (monitoring y commenting)

1. LinkedIn Developer Portal: https://www.linkedin.com/developers/apps
2. Crear app → OAuth 2.0
3. Scopes: `w_member_social`, `r_liteprofile`

---

### 8. AGENTVERSE_API_KEY — Impacto: ★★★☆☆
**Activa:** diffusion agent (AgentVerse registrar — full marketplace listing)

1. Ir a https://agentverse.ai/settings
2. API Keys → Create
3. Agregar en VPS: `echo "AGENTVERSE_API_KEY=tu_key" >> /opt/oixa-protocol/.env`

---

### 9. HUGGINGFACE_TOKEN — Impacto: ★★☆☆☆
**Activa:** diffusion agent (HuggingFace registrar — model card)

1. Ir a https://huggingface.co/settings/tokens
2. New token → Write access
3. Agregar en VPS: `echo "HUGGINGFACE_TOKEN=hf_..." >> /opt/oixa-protocol/.env`

---

## Setup rápido — checklist de configuración

```bash
# 1. xurl (Twitter) — PRIMERO
xurl auth login

# 2. GitHub — SEGUNDO
gh auth login --with-token <<< "ghp_..."
echo "GITHUB_TOKEN=ghp_..." >> /opt/oixa-protocol/.env && ssh root@64.23.235.34 "echo 'GITHUB_TOKEN=ghp_...' >> /opt/oixa-protocol/.env && systemctl restart oixa-diffusion"

# 3. Discord
openclaw config set channels.discord.token "..."

# 4. Verificar todo
xurl whoami
gh auth status
openclaw skills check | grep -E "xurl|discord"
curl http://64.23.235.34:8000/api/v1/zapier/status
```

---

## Estado actual

| Credencial | Status | Agentes desbloqueados |
|-----------|--------|----------------------|
| Twitter/X API | ⚠️ ACCESS TOKEN EXPIRADO — regenerar en dev portal | community-manager, creador-contenido |
| GitHub Token | ✅ CONFIGURADO (ghp_mOt…) — VPS + protocolo-director | protocolo-director, diffusion agent |
| Discord Bot | ⏳ PENDIENTE | community-manager |
| dev.to API | ⏳ PENDIENTE | documentador |
| Telegram Bot | ✅ CONFIGURADO | todos (alertas) |
| AgentOps | ✅ CONFIGURADO | todos (logging) |
| OIXA API VPS | ✅ VIVO | todos |

*Actualizar cuando se configuren las credenciales.*
