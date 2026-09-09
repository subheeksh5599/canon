"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Activity, ArrowRight, CheckCircle2, FileText, Landmark, Layers,
  RefreshCw, Scale, ScrollText, Sparkles, XCircle,
} from "lucide-react";
import { api, ACTOR_LABEL, EXPLORER, fmt, isTxHash, short, type Terms, type Tx } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

export type Section = "overview" | "deal" | "transactions" | "institution";

const NAV: { id: Section; label: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", icon: Activity },
  { id: "deal", label: "New transaction", icon: Sparkles },
  { id: "transactions", label: "Transactions", icon: ArrowRight },
  { id: "institution", label: "Doctrine · cases · appeals", icon: Scale },
];

export function Sidebar({
  current,
  onNav,
  disabled,
}: {
  current: Section;
  onNav: (s: Section) => void;
  disabled?: boolean;
}) {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-sidebar px-3 py-5">
      <div className="flex items-center justify-between px-2 pb-6">
        <span className="term-mono text-lg font-semibold tracking-tight">CANON</span>
        {disabled ? (
          <span className="term-mono flex items-center gap-1.5 rounded border border-[rgba(224,106,94,0.4)] bg-[rgba(224,106,94,0.1)] px-1.5 py-0.5 text-[9px] uppercase tracking-widest text-[#e06a5e]">
            <span className="inline-block size-1.5 rounded-full bg-[#e06a5e]" /> offline
          </span>
        ) : (
          <span className="rounded border border-border px-1.5 py-0.5 text-[9px] uppercase tracking-widest text-muted-foreground">
            venue
          </span>
        )}
      </div>
      <div className="px-1 pb-4">
        <WalletChip disabled={disabled} />
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map((n) => (
          <button
            key={n.id}
            type="button"
            disabled={disabled}
            onClick={() => onNav(n.id)}
            aria-disabled={disabled}
            className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
              current === n.id
                ? "bg-[rgba(95,201,168,0.12)] text-[#5fc9a8] border border-[rgba(95,201,168,0.4)]"
                : "text-muted-foreground border border-transparent"
            } ${disabled ? "cursor-not-allowed opacity-45 hover:bg-transparent" : "hover:bg-muted hover:text-foreground"}`}
          >
            <n.icon className="size-4" />
            {n.label}
          </button>
        ))}
      </nav>
      <div className="mt-auto px-1">
        <div className="px-1 text-[11px] leading-relaxed text-muted-foreground">
          {disabled ? (
            <>
              <div className="term-mono mb-1 text-[10px] uppercase tracking-widest">
                start the backend to navigate
              </div>
              The engine lives on the machine that runs the venue — this console drives it directly.
            </>
          ) : (
            <>
              <div className="term-mono mb-1 text-[10px] uppercase tracking-widest">
                memory is load-bearing
              </div>
              Delete Sibyl and the venue cannot construct terms.
            </>
          )}
        </div>
      </div>
    </aside>
  );
}

type EthProvider = {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
  on?: (event: string, cb: (accounts: string[]) => void) => void;
};

function WalletChip({ disabled }: { disabled?: boolean }) {
  const [addr, setAddr] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const provider = () =>
    typeof window !== "undefined"
      ? (window as unknown as { ethereum?: EthProvider }).ethereum
      : undefined;

  const connect = async () => {
    const p = provider();
    if (!p) {
      setErr("No injected wallet found (MetaMask, Coinbase, OKX).");
      return;
    }
    try {
      const res = await p.request({ method: "eth_requestAccounts", params: [] });
      const accounts = (res ?? []) as string[];
      const first = (accounts[0] ?? "").toLowerCase();
      if (first) {
        setAddr(first);
        setErr(null);
        p.on?.("accountsChanged", (as) => setAddr((as[0] ?? "").toLowerCase() || null));
      }
    } catch (e) {
      setErr("Wallet connection rejected.");
    }
  };

  return (
    <div className="rounded-sm border border-border bg-card px-2 py-2">
      <div className="term-mono mb-1.5 text-[9px] uppercase tracking-widest text-muted-foreground">
        Wallet
      </div>
      {addr ? (
        <div className="flex items-center justify-between gap-2 px-1">
          <a
            href={`https://sepolia.basescan.org/address/${addr}`}
            target="_blank"
            rel="noreferrer"
            className="term-mono truncate text-[11px] text-[#5fc9a8] underline decoration-[#5fc9a8]/40 underline-offset-2"
            title="Open on Basescan"
          >
            {addr.slice(0, 6)}…{addr.slice(-4)}
          </a>
          <span className="flex items-center gap-1.5">
            <span className="inline-block size-1.5 rounded-full bg-[#5fc9a8]" />
            <span className="term-mono text-[10px] text-muted-foreground">84532</span>
          </span>
        </div>
      ) : (
        <button
          type="button"
          disabled={disabled}
          onClick={connect}
          className={`data flex w-full items-center justify-center gap-2 rounded-sm border border-border px-3 py-1.5 text-[11px] transition-colors ${
            disabled
              ? "cursor-not-allowed opacity-45"
              : "text-muted-foreground hover:border-[#5fc9a8] hover:text-[#5fc9a8]"
          }`}
        >
          Connect wallet
        </button>
      )}
      {err && !addr && <div className="mt-1.5 px-1 text-[10px] text-[#e06a5e]">{err}</div>}
    </div>
  );
}

function TxLink({ hash, label }: { hash?: string | null; label?: string }) {
  if (!hash || !isTxHash(hash)) return null;
  return (
    <a
      href={`${EXPLORER}/tx/${hash}`}
      target="_blank"
      rel="noreferrer"
      className="term-mono text-[10px] text-[#5fc9a8] underline decoration-[#5fc9a8]/40 underline-offset-2 hover:text-[#74d4b6]"
      title="Open on Base Sepolia explorer"
    >
      {label ?? short(hash, 12)} ↗
    </a>
  );
}

type Status = { doctrine_version: number; cases: number; pool: number; journal_ok: boolean; actors: Record<string, string> };

export function Overview({ bump }: { bump: number }) {
  const [st, setSt] = useState<Status | null>(null);
  const [down, setDown] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const s = await api<{ ok: true } & Status>("/api/status");
      setSt(s);
      setDown(false);
      const m = await api<{ events: any[] }>("/api/memory");
      setEvents(m.events.slice(0, 14));
    } catch {
      setDown(true);
    }
  }, []);
  useEffect(() => { load(); }, [load, bump]);

  const reset = async () => {
    setBusy(true);
    try {
      const r = await api<{ doctrine_version: number; cases: number }>("/api/reset", { method: "POST" });
      toast.success(`Market reset — doctrine v${r.doctrine_version}, ${r.cases} historical cases`);
      load();
    } catch (e: any) {
      toast.error(e.message);
    } finally { setBusy(false); }
  };

  const stats = [
    { k: "Doctrine", v: st ? `v${st.doctrine_version}` : "…", note: "stored in Sibyl REFERENCE" },
    { k: "Resolved cases", v: st ? String(st.cases) : "…", note: "5 seed the demo market" },
    { k: "Journal", v: st ? (st.journal_ok ? "chain intact" : "BROKEN") : "…", note: "hash-verified" },
    { k: "Pool", v: st ? fmt(st.pool) : "…", note: "fees + forfeited bonds" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.03em]">The venue</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Agents transact here under terms the economy itself writes.
          </p>
        </div>
        <Button variant="outline" onClick={reset} disabled={busy}>
          <RefreshCw className={busy ? "animate-spin" : ""} /> Reset market
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.k} className="border border-border bg-card">
            <CardContent className="p-5">
              <div className="text-[11px] uppercase tracking-widest text-muted-foreground">{s.k}</div>
              <div className="term-mono mt-2 text-2xl font-semibold">{s.v}</div>
              <div className="mt-1 text-[11px] text-muted-foreground">{s.note}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {down && (
        <div className="border border-border bg-card rounded-sm px-5 py-4 text-sm text-muted-foreground">
          The engine is not responding on <span className="term-mono">localhost:8000</span>. Start it
          from the repo root: <span className="term-mono">.venv/bin/uvicorn server.main:app --port 8000</span>.
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><ScrollText className="size-4 text-[#5fc9a8]" /> Live memory journal</CardTitle>
            <CardDescription>Every decision the venue has recorded, chain-hashed in Sibyl.</CardDescription>
          </CardHeader>
          <CardContent className="max-h-80 space-y-1 overflow-auto pr-1">
            {events.map((e) => (
              <div key={`${e.seq}-${e.hash}`} className="term-mono flex items-center gap-3 rounded-md bg-muted/50 px-3 py-1.5 text-xs">
                <span className="w-8 text-muted-foreground">#{e.seq}</span>
                <span className="flex-1 truncate">{e.acted}</span>
                <span className="text-muted-foreground">{e.ts?.slice(11, 19)}</span>
                <span className="text-[#5fc9a8]/60">{e.hash}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base"><Layers className="size-4 text-[#5fc9a8]" /> What CANON is not</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {[
              ["Not a risk score", "The output is an executable contract, never a number on a dashboard."],
              ["Not a warning", "It never says be careful — it changes the deal."],
              ["Not a denial", "The economy keeps moving; the terms keep it safe."],
              ["Load-bearing", "Remove Sibyl and the venue cannot construct authoritative terms."],
            ].map(([k, v]) => (
              <div key={k} className="flex gap-3 rounded-lg border border-border bg-muted/30 p-3">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-[#5fc9a8]" />
                <div><div className="font-medium">{k}</div><div className="text-muted-foreground">{v}</div></div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function TermsCard({ terms }: { terms: Terms }) {
  if (!terms) return null;
  return (
    <Card className="border border-border bg-card ring-1 ring-[rgba(95,201,168,0.2)]">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">APPROVED under these terms</CardTitle>
          <Badge className="rounded-full bg-[rgba(95,201,168,0.12)] text-[#5fc9a8]">doctrine v{terms.doctrine_version}</Badge>
        </div>
        <CardDescription className="term-mono text-xs">{terms.rule_ids.join(", ") || "no doctrine — naive market terms"}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["Upfront", fmt(terms.upfront_usd)],
            ["Milestones", String(terms.milestones.length)],
            ["Bond", fmt(terms.bond_usd)],
            ["Coverage", `${Math.round(terms.coverage_ratio * 100)}%`],
          ].map(([k, v]) => (
            <div key={k} className="rounded-lg border border-border bg-black/25 px-3 py-2.5">
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{k}</div>
              <div className="term-mono mt-0.5 text-lg font-semibold">{v}</div>
            </div>
          ))}
        </div>
        <div className="mt-3 term-mono text-[11px] leading-relaxed text-muted-foreground">
          {terms.reason} · total escrowed {fmt(terms.total_milestones)}
        </div>
      </CardContent>
    </Card>
  );
}

export function DealStudio({ onDone }: { onDone: () => void }) {
  const [provider, setProvider] = useState("0x31eafd3fe36d6c891ea5b369a876166dffabf320");
  const [amount, setAmount] = useState("400");
  const [terms, setTerms] = useState<Terms | null>(null);
  const [tx, setTx] = useState<Tx | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [claimRes, setClaimRes] = useState<any>(null);
  const [evidence, setEvidence] = useState("TX_VERIFIED");

  const run = async (action: string, fn: () => Promise<void>) => {
    setBusy(action);
    try { await fn(); } catch (e: any) { toast.error(e.message); } finally { setBusy(null); }
  };

  const evaluate = () => run("eval", async () => {
    const r = await api<{ terms: Terms }>("/api/evaluate", {
      method: "POST", body: JSON.stringify({ provider, job_value_usd: Number(amount) }),
    });
    setTerms(r.terms);
    toast.success(`Terms generated from doctrine v${r.terms.doctrine_version}`);
  });

  const create = () => run("create", async () => {
    const r = await api<{ tx: Tx }>("/api/transactions", {
      method: "POST", body: JSON.stringify({ provider, job_value_usd: Number(amount) }),
    });
    setTx(r.tx); setTerms(r.tx.terms); onDone();
    toast.success("Transaction created and termed");
  });

  const act = (action: string) => run(action, async () => {
    const r = await api<{ tx: Tx }>(`/api/transactions/${tx!.tx_id}/${action}`, {
      method: "POST", body: JSON.stringify({ provider }),
    });
    setTx(r.tx); onDone();
    toast.success(`Transaction ${r.tx.state}`);
  });

  const claim = () => run("claim", async () => {
    const r = await api<{ result: any }>(`/api/transactions/${tx!.tx_id}/claim`, {
      method: "POST", body: JSON.stringify({ evidence_source: evidence }),
    });
    setClaimRes(r.result); onDone();
    toast.success(`Claim resolved — signal ${r.result.signal}, doctrine ${r.result.doctrine_version_after}`);
  });

  const canFund = tx && tx.state === "TERMED";
  const canFinish = tx && (tx.state === "FUNDED");
  const canClaim = tx && tx.state === "FAILED";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.03em]">New transaction</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The venue recalls collective precedent and constructs the deal. Nothing here is an LLM guess.
        </p>
      </div>

      <Card className="border-border">
        <CardContent className="space-y-4 p-5">
          <div>
            <Label>Counterparty</Label>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {(["0x20fd7bec60829230a1cfbe4caf25a12ab2e49aa9", "0x31eafd3fe36d6c891ea5b369a876166dffabf320"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setProvider(p)}
                  className={`rounded-lg border px-4 py-3 text-left transition-colors ${
                    provider === p ? "border-[rgba(95,201,168,0.5)] bg-[rgba(95,201,168,0.12)]" : "border-border bg-muted/40 hover:bg-muted"
                  }`}
                >
                  <div className="text-sm font-medium">{ACTOR_LABEL[p]}</div>
                  <div className="term-mono mt-0.5 text-[10px] text-muted-foreground">{short(p, 14)}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Job</Label>
              <Input value="research agent" disabled className="mt-1.5" />
            </div>
            <div>
              <Label htmlFor="amt">Job value (USD)</Label>
              <Input id="amt" value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} className="mt-1.5 term-mono" />
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={evaluate} disabled={busy !== null || !amount}>
              <Sparkles /> Evaluate against doctrine
            </Button>
            <Button variant="outline" onClick={create} disabled={busy !== null}>
              Create & fund on Base
            </Button>
          </div>
        </CardContent>
      </Card>

      {terms && <TermsCard terms={terms} />}

      {tx && (
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="size-4 text-[#5fc9a8]" /> {short(tx.tx_id, 16)}
              <Badge className="rounded-full">{tx.state}</Badge>
              <TxLink hash={tx.chain_ref} />
              {tx.chain?.claim && tx.chain.claim !== tx.chain_ref && <TxLink hash={tx.chain.claim} label="claim" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {canFund && <Button onClick={() => act("execute")} disabled={busy !== null}>Lock escrow + bond</Button>}
            {canFinish && <Button onClick={() => act("complete")} disabled={busy !== null}><CheckCircle2 /> Delivered</Button>}
            {canFinish && <Button variant="destructive" onClick={() => act("fail")} disabled={busy !== null}><XCircle /> Provider failed</Button>}
            {canClaim && (
              <>
                <div className="flex items-center gap-1.5 rounded-lg border border-border bg-muted/40 px-2 py-1 text-xs">
                  Evidence:
                  {["TX_VERIFIED", "ATTESTATION", "TEXT"].map((s) => (
                    <button key={s} onClick={() => setEvidence(s)}
                      className={`rounded px-2 py-0.5 ${evidence === s ? "bg-[rgba(95,201,168,0.12)] text-[#5fc9a8]" : "hover:bg-muted"}`}>
                      {s.replace("_", " ")}
                    </button>
                  ))}
                </div>
                <Button onClick={claim} disabled={busy !== null}>File & resolve claim</Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {claimRes && (
        <Card className="border-[rgba(95,201,168,0.4)] bg-[rgba(95,201,168,0.08)]">
          <CardContent className="space-y-2 p-5 text-sm">
            <div className="font-medium">Claim resolved — this becomes institutional memory</div>
            <div className="term-mono grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
              <span>paid {fmt(claimRes.settlement?.paid)}</span>
              <span>escrow refund {fmt(claimRes.settlement?.escrow_refund)}</span>
              <span>signal {claimRes.signal}</span>
              <span>doctrine v{claimRes.doctrine_version_after}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              A resolved case records real evidence; a bonded appeal amends the doctrine.
              and run the fresh-session proof to see a different deal for the same request.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function Transactions({ bump }: { bump: number }) {
  const [rows, setRows] = useState<Tx[]>([]);
  useEffect(() => {
    api<{ transactions: Tx[] }>("/api/transactions")
      .then((r) => setRows(r.transactions))
      .catch(() => {});
  }, [bump]);
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-[-0.03em]">Transactions</h1>
      <Card className="border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tx</TableHead><TableHead>Provider</TableHead><TableHead>Value</TableHead>
              <TableHead>Terms</TableHead><TableHead>State</TableHead><TableHead>Base</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((t) => (
              <TableRow key={t.tx_id}>
                <TableCell className="term-mono text-xs">{short(t.tx_id, 14)}</TableCell>
                <TableCell className="text-xs">{ACTOR_LABEL[t.provider] ?? short(t.provider)}</TableCell>
                <TableCell className="term-mono text-xs">{fmt(t.job_value_usd)}</TableCell>
                <TableCell className="term-mono text-xs">
                  {t.terms ? `v${t.terms.doctrine_version} · ${t.terms.rule_ids[0] ?? "naive"}` : "—"}
                </TableCell>
                <TableCell>
                  <Badge className="rounded-full">{t.state}</Badge>
                </TableCell>
                <TableCell className="term-mono text-[10px] text-muted-foreground">
                  <div className="flex flex-col items-start gap-1">
                    <TxLink hash={t.chain_ref} />
                    {t.chain?.claim && t.chain.claim !== t.chain_ref && <TxLink hash={t.chain.claim} label="claim" />}
                    {!isTxHash(t.chain_ref) && (t.chain_ref ? short(t.chain_ref, 10) : "—")}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
