"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, ScrollText, Landmark, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";

type DeletionResult = {
  ok: boolean;
  pass_?: boolean;
  doctrine_before?: number;
  refusal?: string;
  error?: string;
};

type JournalInfo = { journal_ok: boolean; events: { seq?: number; event?: string }[] };

type ChainInfo = {
  configured: boolean;
  venue?: string;
  market?: string;
  usdc_balance_usd?: string;
  contract_usdc_usd?: string;
  pool_usdc_usd?: string;
  mirror?: Record<string, { contract_id?: number; escrow?: string; claim?: string; create?: string; fail?: string; complete?: string; open?: string; resolve?: string }>;
};

function sumKind(mirror: ChainInfo["mirror"], kind: string): number {
  if (!mirror) return 0;
  let n = 0;
  for (const v of Object.values(mirror)) if (v && v[kind as keyof typeof v]) n += 1;
  return n;
}

export function IntegrityView() {
  const [journal, setJournal] = useState<JournalInfo | null>(null);
  const [chain, setChain] = useState<ChainInfo | null>(null);
  const [del, setDel] = useState<DeletionResult | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [j, c] = await Promise.all([
        api<JournalInfo>("/api/memory"),
        api<ChainInfo>("/api/chain"),
      ]);
      setJournal(j);
      setChain(c);
    } catch {
      setJournal(null);
      setChain(null);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runDeletion = async () => {
    setBusy(true);
    try {
      const r = await api<DeletionResult>("/api/verify/deletion");
      setDel(r);
    } finally {
      setBusy(false);
    }
  };

  const mirror = chain?.mirror ?? {};
  const dealCount = Object.keys(mirror).filter((k) => !k.startsWith("appeal:")).length;
  const appealCount = Object.keys(mirror).filter((k) => k.startsWith("appeal:")).length;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-[-0.03em]">Integrity</h1>
      <p className="text-sm text-muted-foreground">
        Live facts about the venue: the memory journal, the settlement chain, and the deletion gate.
        Every value below is read from the running venue or from Base Sepolia — nothing is fabricated.
      </p>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <ScrollText className="size-4 text-[#5fc9a8]" /> Memory journal
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Chain integrity</span>
              {journal ? (
                journal.journal_ok ? (
                  <Badge className="rounded-full border border-[rgba(95,201,168,0.4)] bg-[rgba(95,201,168,0.12)] text-[#5fc9a8]">
                    verified
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="rounded-full">broken</Badge>
                )
              ) : (
                <span className="text-muted-foreground">unreachable</span>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Events recorded</span>
              <span className="term-mono">{journal?.events.length ?? "—"}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Every decision is an append-only, hash-chained event in Sibyl; a tampered journal reads
              as broken, never as silent.
            </p>
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Landmark className="size-4 text-[#5fc9a8]" /> Settlement chain
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">State</span>
              {chain?.configured ? (
                <Badge className="rounded-full border border-[rgba(95,201,168,0.4)] bg-[rgba(95,201,168,0.12)] text-[#5fc9a8]">
                  on-chain · 84532
                </Badge>
              ) : (
                <Badge variant="destructive" className="rounded-full">not configured</Badge>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Deals settled</span>
              <span className="term-mono">{dealCount}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Appeals bonded</span>
              <span className="term-mono">{appealCount}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Venue USDC</span>
              <span className="term-mono">{chain ? `$${chain.usdc_balance_usd}` : "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Pool</span>
              <span className="term-mono">{chain ? `$${chain.pool_usdc_usd}` : "—"}</span>
            </div>
            {chain?.market && (
              <a
                href={`https://sepolia.basescan.org/address/${chain.market}`}
                target="_blank"
                rel="noreferrer"
                className="term-mono block truncate text-xs text-[#5fc9a8] underline decoration-[#5fc9a8]/40 underline-offset-2"
              >
                {chain.market.slice(0, 10)}…{chain.market.slice(-6)} ↗
              </a>
            )}
          </CardContent>
        </Card>

        <Card className="border-border">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="size-4 text-[#5fc9a8]" /> Deletion gate
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-xs text-muted-foreground">
              Wipes a consistent copy of the live market and proves the venue cannot construct terms
              without the memory layer.
            </p>
            <Button onClick={runDeletion} disabled={busy} variant="outline" className="w-full">
              <Activity className="size-3.5" /> {busy ? "Running…" : "Run the deletion test"}
            </Button>
            {del?.error && <div className="text-xs text-[#e06a5e]">{del.error}</div>}
            {del?.ok && del.pass_ && (
              <div className="rounded-sm border border-[rgba(95,201,168,0.4)] bg-[rgba(95,201,168,0.08)] px-3 py-2 text-xs">
                <div className="term-mono text-[#5fc9a8]">PASS — venue refused to rule</div>
                <div className="mt-1 text-muted-foreground">
                  doctrine before wipe: v{del.doctrine_before} · {del.refusal}
                </div>
              </div>
            )}
            {del?.ok && !del.pass_ && (
              <div className="rounded-sm border border-[rgba(224,106,94,0.4)] bg-[rgba(224,106,94,0.08)] px-3 py-2 text-xs text-[#e06a5e]">
                FAIL — venue still ruled without memory
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">On-chain settlement records</CardTitle>
          <CardDescription>
            Real transaction hashes registered by the venue (open each on Basescan).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {Object.entries(mirror).length === 0 && (
            <div className="p-3 text-sm text-muted-foreground">No settlement records yet.</div>
          )}
          {Object.entries(mirror).map(([id, reg]) => {
            const kinds: { k: string; label: string }[] = [
              { k: "create", label: "register" },
              { k: "escrow", label: "escrow" },
              { k: "fail", label: "fail" },
              { k: "claim", label: "claim" },
              { k: "open", label: "appeal open" },
              { k: "resolve", label: "appeal resolve" },
            ];
            return (
              <div key={id} className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md bg-muted/30 px-3 py-2">
                <span className="term-mono w-44 truncate text-xs">{id.slice(0, 40)}</span>
                {kinds
                  .filter(({ k }) => reg && reg[k as keyof typeof reg])
                  .map(({ k, label }) => (
                    <a
                      key={k}
                      href={`https://sepolia.basescan.org/tx/${reg[k as keyof typeof reg]}`}
                      target="_blank"
                      rel="noreferrer"
                      className="term-mono text-[10px] text-[#5fc9a8] underline decoration-[#5fc9a8]/40 underline-offset-2"
                    >
                      {label} ↗
                    </a>
                  ))}
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
