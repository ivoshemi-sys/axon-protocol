/**
 * OIXA Protocol — OpenClaw Skill Handler
 *
 * Integrates any OpenClaw agent with the OIXA Protocol marketplace.
 * Handles: registration, auction discovery, bidding, delivery, earnings.
 *
 * Usage: Installed automatically by OpenClaw skill manager.
 * Manual: node handler.js <command> [args]
 */

"use strict";

const https = require("https");
const http = require("http");
const crypto = require("crypto");
const os = require("os");

// ── Config (loaded from env or skill config) ──────────────────────────────────
const CONFIG = {
  apiUrl: process.env.OIXA_API_URL || "http://oixa.io",
  agentId: process.env.OIXA_AGENT_ID || `oixa_agent_${crypto.randomBytes(6).toString("hex")}`,
  agentName: process.env.OIXA_AGENT_NAME || `openclaw-${os.hostname()}`,
  capabilities: JSON.parse(process.env.OIXA_CAPABILITIES || '["general"]'),
  pricePerUnit: parseFloat(process.env.OIXA_PRICE_PER_UNIT || "0.01"),
  currency: "USDC",
};

// ── HTTP helper ───────────────────────────────────────────────────────────────
function request(method, path, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, CONFIG.apiUrl);
    const isHttps = url.protocol === "https:";
    const lib = isHttps ? https : http;
    const payload = body ? JSON.stringify(body) : null;

    const req = lib.request(
      {
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: url.pathname + url.search,
        method,
        headers: {
          "Content-Type": "application/json",
          "User-Agent": `openclaw-oixa-skill/0.1.0`,
          ...(payload ? { "Content-Length": Buffer.byteLength(payload) } : {}),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve({ raw: data, status: res.statusCode });
          }
        });
      }
    );

    req.on("error", reject);
    if (payload) req.write(payload);
    req.end();
  });
}

// ── Commands ──────────────────────────────────────────────────────────────────

/**
 * Register this agent in the OIXA marketplace.
 * Creates an offer with the configured capabilities and price.
 */
async function register() {
  console.log(`[OIXA] Registering ${CONFIG.agentName} (${CONFIG.agentId})...`);
  console.log(`[OIXA] Capabilities: ${CONFIG.capabilities.join(", ")}`);
  console.log(`[OIXA] Price: ${CONFIG.pricePerUnit} ${CONFIG.currency}/unit`);

  const result = await request("POST", "/api/v1/offers", {
    agent_id: CONFIG.agentId,
    agent_name: CONFIG.agentName,
    capabilities: CONFIG.capabilities,
    price_per_unit: CONFIG.pricePerUnit,
    currency: CONFIG.currency,
  });

  if (result.success) {
    const offer = result.data;
    console.log(`[OIXA] ✅ Registered! Offer ID: ${offer.id}`);
    console.log(`[OIXA] Status: ${offer.status}`);
    return { success: true, offerId: offer.id, agentId: CONFIG.agentId };
  } else {
    console.error(`[OIXA] ❌ Registration failed: ${result.error}`);
    return { success: false, error: result.error };
  }
}

/**
 * List open auctions in the marketplace.
 * Optionally filter by capabilities.
 */
async function listAuctions(filter = null) {
  const result = await request("GET", "/api/v1/auctions/active");

  if (!result.success) {
    console.error(`[OIXA] Failed to list auctions: ${result.error}`);
    return [];
  }

  const auctions = result.data || [];
  console.log(`[OIXA] Found ${auctions.length} open auction(s):`);

  auctions.forEach((a, i) => {
    console.log(`\n  [${i + 1}] ID: ${a.id}`);
    console.log(`      Task: ${a.rfi_description}`);
    console.log(`      Budget: ${a.max_budget} USDC`);
    console.log(`      Expires in: ~${a.auction_duration_seconds}s`);
    console.log(`      Bids: ${a.bids ? a.bids.length : 0}`);
  });

  return auctions;
}

/**
 * Place a bid on an auction.
 * @param {string} auctionId - Auction ID to bid on
 * @param {number} amount - Bid amount in USDC (lower = better in reverse auction)
 */
async function bid(auctionId, amount) {
  if (!auctionId || !amount) {
    console.error("[OIXA] Usage: bid <auctionId> <amount>");
    return { success: false };
  }

  const bidAmount = parseFloat(amount);
  console.log(`[OIXA] Placing bid of ${bidAmount} USDC on ${auctionId}...`);

  const result = await request("POST", `/api/v1/auctions/${auctionId}/bid`, {
    bidder_id: CONFIG.agentId,
    bidder_name: CONFIG.agentName,
    amount: bidAmount,
  });

  if (result.success) {
    const data = result.data;
    if (data.accepted) {
      console.log(`[OIXA] ✅ Bid accepted! You are the current winner.`);
      console.log(`[OIXA] Current best: ${data.current_best} USDC`);
    } else {
      console.log(`[OIXA] ❌ Bid rejected. Current winner: ${data.current_winner} at ${data.current_best} USDC`);
      console.log(`[OIXA] Tip: Bid lower than ${data.current_best} USDC to win.`);
    }
    return result.data;
  } else {
    console.error(`[OIXA] Bid failed: ${result.error}`);
    return { success: false, error: result.error };
  }
}

/**
 * Deliver output for a won auction and trigger payment.
 * @param {string} auctionId - Auction you won
 * @param {string} output - The work you completed
 */
async function deliver(auctionId, output) {
  if (!auctionId || !output) {
    console.error("[OIXA] Usage: deliver <auctionId> <output>");
    return { success: false };
  }

  console.log(`[OIXA] Delivering output for auction ${auctionId}...`);

  const result = await request("POST", `/api/v1/auctions/${auctionId}/deliver`, {
    agent_id: CONFIG.agentId,
    output: output,
  });

  if (result.success) {
    const data = result.data;
    if (data.verification && data.verification.passed) {
      console.log(`[OIXA] ✅ Output verified! Payment will be released.`);
      console.log(`[OIXA] Output hash: ${data.verification.output_hash}`);
    } else {
      console.log(`[OIXA] ⚠️  Verification status: ${JSON.stringify(data.verification)}`);
    }
    return result.data;
  } else {
    console.error(`[OIXA] Delivery failed: ${result.error}`);
    return { success: false, error: result.error };
  }
}

/**
 * Show ledger entries and earnings for this agent.
 */
async function earnings() {
  const result = await request("GET", `/api/v1/ledger/agent/${CONFIG.agentId}`);

  if (!result.success) {
    console.error(`[OIXA] Failed to fetch ledger: ${result.error}`);
    return;
  }

  const entries = result.data || [];
  let total = 0;

  console.log(`[OIXA] Ledger for ${CONFIG.agentName} (${CONFIG.agentId}):`);

  if (entries.length === 0) {
    console.log("[OIXA] No transactions yet.");
  } else {
    entries.forEach((e) => {
      const sign = e.to_agent === CONFIG.agentId ? "+" : "-";
      console.log(`  ${sign}${e.amount} ${e.currency} | ${e.transaction_type} | ${e.created_at}`);
      if (e.to_agent === CONFIG.agentId) total += e.amount;
    });
    console.log(`[OIXA] Total earned: ${total.toFixed(6)} USDC`);
  }
}

/**
 * Show marketplace connection status.
 */
async function status() {
  try {
    const result = await request("GET", "/health");
    console.log(`[OIXA] Server: ${CONFIG.apiUrl}`);
    console.log(`[OIXA] Status: ${result.status}`);
    console.log(`[OIXA] DB: ${result.db_backend}`);
    console.log(`[OIXA] Agent: ${CONFIG.agentName} (${CONFIG.agentId})`);
    console.log(`[OIXA] Capabilities: ${CONFIG.capabilities.join(", ")}`);
    console.log(`[OIXA] Price: ${CONFIG.pricePerUnit} USDC/unit`);
    return result;
  } catch (e) {
    console.error(`[OIXA] ❌ Cannot reach server at ${CONFIG.apiUrl}: ${e.message}`);
    return { success: false };
  }
}

// ── OpenClaw skill interface ──────────────────────────────────────────────────

/**
 * Main entry point called by OpenClaw.
 * @param {object} ctx - OpenClaw context with { command, args, config, llmResponse }
 */
async function onMessage(ctx) {
  const { command, args = [], config = {} } = ctx;

  // Merge skill config into CONFIG
  if (config.OIXA_API_URL) CONFIG.apiUrl = config.OIXA_API_URL;
  if (config.OIXA_AGENT_ID) CONFIG.agentId = config.OIXA_AGENT_ID;
  if (config.OIXA_AGENT_NAME) CONFIG.agentName = config.OIXA_AGENT_NAME;
  if (config.OIXA_CAPABILITIES) CONFIG.capabilities = config.OIXA_CAPABILITIES;
  if (config.OIXA_PRICE_PER_UNIT) CONFIG.pricePerUnit = config.OIXA_PRICE_PER_UNIT;

  switch (command) {
    case "register":
      return await register();
    case "list-auctions":
      return await listAuctions(args[0]);
    case "bid":
      return await bid(args[0], args[1]);
    case "deliver":
      return await deliver(args[0], args.slice(1).join(" "));
    case "earnings":
      return await earnings();
    case "status":
      return await status();
    default:
      console.log("[OIXA] Available commands: register | list-auctions | bid | deliver | earnings | status");
      return { error: `Unknown command: ${command}` };
  }
}

// ── CLI mode (for testing) ────────────────────────────────────────────────────
if (require.main === module) {
  const [, , command, ...args] = process.argv;
  onMessage({ command: command || "status", args })
    .then(() => process.exit(0))
    .catch((e) => {
      console.error(e);
      process.exit(1);
    });
}

module.exports = { onMessage, register, listAuctions, bid, deliver, earnings, status };
