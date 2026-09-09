const API_DEFAULT = "http://localhost:8000";
/** Deployed origins proxy /api/* through Vercel rewrites → the VPS backend,
 *  so the base is relative there; local dev talks to the localhost engine. */
export const API =
  process.env.NEXT_PUBLIC_CANON_API ??
  (typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? API_DEFAULT
    : "");

export class EngineOfflineError extends Error {
  constructor() {
    super(
      "The CANON engine is not reachable from this origin. The engine and its Sibyl memory run as a local process — start it and open the console from your machine (or point NEXT_PUBLIC_CANON_API at a hosted backend).",
    );
    this.name = "EngineOfflineError";
  }
}

/** True only when this origin can actually reach the engine:
 *  local dev origins use the default localhost backend; deployed origins
 *  reach it through the Vercel /api rewrite proxy. */
export function engineConfigured(): boolean {
  if (process.env.NEXT_PUBLIC_CANON_API) return true;
  if (typeof window === "undefined") return true; // prerender
  const h = window.location.hostname;
  return (
    h === "localhost" ||
    h === "127.0.0.1" ||
    h.endsWith("vercel.app") ||
    h.endsWith(".vercel.app") ||
    h.endsWith("vercel.dev")
  );
}

export type Terms = {
  upfront_usd: number;
  milestones: number[];
  total_milestones: number;
  bond_usd: number;
  coverage_ratio: number;
  rule_ids: string[];
  doctrine_version: number;
  reason: string;
};

export type Tx = {
  tx_id: string;
  buyer: string;
  provider: string;
  job_type: string;
  job_value_usd: number;
  state: string;
  terms: Terms | null;
  escrow_locked_usd: number;
  chain_ref: string | null;
  chain?: {
    configured?: boolean;
    contract_id?: number;
    create?: string;
    escrow?: string;
    fail?: string;
    claim?: string;
    complete?: string;
  };
  explorer?: string;
  outcome?: string | null;
  created_at: string;
};

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  if (!engineConfigured()) throw new EngineOfflineError();
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const json = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
  if (json.error) throw new Error(json.error);
  return json as T;
}

export const short = (s: string | null | undefined, n = 10) =>
  s ? (s.length > n ? `${s.slice(0, n)}…` : s) : "—";

export const fmt = (n: number) =>
  `$${n.toLocaleString("en-US", { maximumFractionDigits: 2 })}`;

export const EXPLORER = "https://sepolia.basescan.org";
export const isTxHash = (s: string | null | undefined) =>
  !!s && /^0x[0-9a-fA-F]{64}$/.test(s);

export const ACTOR_LABEL: Record<string, string> = {
  "0x3991d5267e013fb9d5f2fbb30b8f3d8ff97c1ad9": "Buyer",
  "0x20fd7bec60829230a1cfbe4caf25a12ab2e49aa9": "Prov-01 · scarred",
  "0x31eafd3fe36d6c891ea5b369a876166dffabf320": "Prov-02 · new",
  "0x1776eba1f2c74b141d0c337ffcdbb0e40d77876b": "Prov-03 · Virtuals agent",
  "0x617b0e8d15c3a48ddf2ec70ab17bf7cc7dbf3046": "Adjudicator",
};
