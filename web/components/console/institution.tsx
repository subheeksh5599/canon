"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FlaskConical, Gavel, History, ShieldCheck } from "lucide-react";
import { api, fmt, short } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Rule = any;
type Doctrine = { version: number; rules: Rule[]; versions: any[] };

export function DoctrineView({ bump }: { bump: number }) {
  const [doc, setDoc] = useState<Doctrine | null>(null);
  const load = useCallback(() => {
    api<{ version: number; rules: Rule[]; versions: any[] }>("/api/doctrine")
      .then(setDoc).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load, bump]);

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-[-0.03em]">The doctrine</h1>
      <p className="text-sm text-muted-foreground">
        Rules are born from case evidence, amended by appeals, refreshed by supporting cases, and
        retired by decay. Every version is stored in Sibyl with a checksum — the stored rule, not the
        code, governs the next transaction.
      </p>

      {doc && doc.rules.length === 0 && (
        <Card><CardContent className="p-5 text-sm text-muted-foreground">
          No doctrine yet — the venue is running on naive terms (100% upfront, no bond). Five confirmed
          failures in a job class will write doctrine v1.
        </CardContent></Card>
      )}

      <div className="space-y-3">
        {(doc?.rules ?? []).map((r: Rule) => (
          <Card key={r.rule_id} className="border-border">
            <CardContent className="space-y-3 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="term-mono font-semibold">{r.rule_id}</div>
                <Badge className="rounded-full">{r.status}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {[
                  ["Upfront cap", `${Math.round(r.upfront_cap_ratio * 100)}%`],
                  ["Milestones", String(r.milestone_count_min)],
                  ["Bond", `${Math.round(r.bond_ratio * 100)}%`],
                  ["Coverage", `${Math.round(r.coverage_ratio * 100)}%`],
                  ["Supporting cases", String((r.supporting_case_ids ?? []).length)],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-md border border-border bg-black/20 px-2.5 py-1.5">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{k}</div>
                    <div className="term-mono text-sm font-medium">{v}</div>
                  </div>
                ))}
              </div>
              <div className="term-mono text-[11px] text-muted-foreground">
                {r.job_classes ? `pattern: ${r.job_classes.join(", ")} · ` : ""}
                {r.created_by_case ? `created by ${short(r.created_by_case, 18)} · ` : ""}
                {r.supersedes ? `supersedes ${r.supersedes} · ` : ""}
                {r.amended_by_appeal ? `amended by ${short(r.amended_by_appeal, 18)}` : "never appealed"}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {(doc?.versions?.length ?? 0) > 1 && (
        <Card className="border-border bg-muted/20">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base"><History className="size-4 text-[#5fc9a8]" /> Version history</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {doc!.versions.map((v: any) => (
              <Badge key={v.version} variant={v.version === doc!.version ? "default" : "secondary"} className="rounded-full term-mono">
                v{v.version}{v.supersedes ? ` → supersedes v${v.supersedes}` : ""}
              </Badge>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function AppealsView({ bump, onChanged }: { bump: number; onChanged: () => void }) {
  const [appeals, setAppeals] = useState<any[]>([]);
  const [ruleId, setRuleId] = useState("");
  const [arguments_, setArguments_] = useState("");
  const [bond, setBond] = useState("20");

  const load = useCallback(() => {
    api<{ appeals: any[] }>("/api/appeals").then((r) => setAppeals(r.appeals)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load, bump]);

  const open = async () => {
    if (!ruleId) return toast.error("Target a rule id — copy it from the Doctrine tab");
    try {
      await api("/api/appeals", {
        method: "POST",
        body: JSON.stringify({
          challenger: "0xprov000000000000000000000000000003",
          target_rule_id: ruleId, arguments: arguments_, bond_usd: Number(bond),
        }),
      });
      toast.success("Appeal opened — rule frozen for new terms until resolved");
      setRuleId(""); setArguments_(""); load(); onChanged();
    } catch (e: any) { toast.error(e.message); }
  };

  const resolve = async (id: string, decision: string) => {
    try {
      const r = await api<{ doctrine_version: number }>(`/api/appeals/${id}/resolve`, {
        method: "POST", body: JSON.stringify({ decision }),
      });
      toast.success(`Appeal ${decision} — doctrine v${r.doctrine_version}`);
      load(); onChanged();
    } catch (e: any) { toast.error(e.message); }
  };

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-[-0.03em]">Appeals — contestable doctrine</h1>
      <p className="text-sm text-muted-foreground">
        Post a bond, challenge a precedent. A rejected appeal forfeits the bond to the pool; an
        accepted appeal amends the doctrine for every future transaction.
      </p>

      <Card className="border-border">
        <CardContent className="space-y-3 p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="sm:col-span-1">
              <Label>Target rule id</Label>
              <Input value={ruleId} onChange={(e) => setRuleId(e.target.value)} className="mt-1.5 term-mono" placeholder="CANON-001-research" />
            </div>
            <div>
              <Label>Appeal bond (USD)</Label>
              <Input value={bond} onChange={(e) => setBond(e.target.value.replace(/\D/g, ""))} className="mt-1.5 term-mono" />
            </div>
            <div>
              <Label>Grounds</Label>
              <Input value={arguments_} onChange={(e) => setArguments_(e.target.value)} className="mt-1.5" placeholder="rule is disproportionate for clean providers" />
            </div>
          </div>
          <Button onClick={open}><Gavel /> Open appeal (bond posted on Base)</Button>
        </CardContent>
      </Card>

      {appeals.map((a: any) => (
        <Card key={a.name} className="border-border">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="min-w-0">
              <div className="term-mono flex items-center gap-2 text-sm font-medium">
                {a.target_rule_id}
                <Badge className="rounded-full">{a.state}</Badge>
                {a.decision && <Badge variant={a.decision === "ACCEPTED" ? "default" : "secondary"} className="rounded-full">{a.decision}</Badge>}
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">
                by {short(a.challenger, 12)} · bond {fmt(a.bond_usd)} · {a.arguments}
              </div>
            </div>
            {a.state === "OPEN" && (
              <div className="flex gap-2">
                <Button size="sm" onClick={() => resolve(a.name, "ACCEPTED")}>Accept</Button>
                <Button size="sm" variant="destructive" onClick={() => resolve(a.name, "REJECTED")}>Reject</Button>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function CasesView({ bump }: { bump: number }) {
  const [cases, setCases] = useState<any[]>([]);
  useEffect(() => {
    api<{ cases: any[] }>("/api/cases").then((r) => setCases(r.cases)).catch(() => {});
  }, [bump]);
  return (
    <Card className="border-border">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Resolved cases</CardTitle>
        <CardDescription>Only RESOLVED, HIGH/MEDIUM-confidence cases may seed doctrine.</CardDescription>
      </CardHeader>
      <CardContent className="max-h-[420px] space-y-1.5 overflow-auto pr-1">
        {(cases ?? []).slice().reverse().map((c: any) => (
          <div key={c.case_id} className="term-mono flex items-center gap-3 rounded-md bg-muted/40 px-3 py-2 text-xs">
            <span className="w-36 truncate text-muted-foreground">{short(c.case_id, 20)}</span>
            <span>{c.pattern_key}</span>
            <span className="text-[#e06a5e]/80">{c.outcome}</span>
            <span className="text-muted-foreground">loss {fmt(c.loss_usd)}</span>
            <Badge className="ml-auto rounded-full">{c.confidence}</Badge>
          </div>
        ))}
        {(cases ?? []).length === 0 && <div className="p-4 text-sm text-muted-foreground">No cases yet.</div>}
      </CardContent>
    </Card>
  );
}

type Proof = { pass_?: boolean; virgin_terms?: any; recalled_terms?: any; doctrine_version?: number; ts?: string; refusal?: string; naive?: any; governed?: any; reduction?: number };

function ProofCard({ title, note, run, kind }: { title: string; note: string; run: () => Promise<Proof>; kind: "cold" | "del" | "abl" }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Proof | null>(null);
  const runOnce = async () => {
    setBusy(true);
    setRes(null);
    try {
      const r = await run();
      setRes(r);
      toast.success(r.pass_ === false ? `${title}: PROOF FAIL` : `${title}: live proof recorded`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-border">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldCheck className="size-4 text-[#5fc9a8]" /> {title}
        </CardTitle>
        <CardDescription>{note}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <Button size="sm" onClick={runOnce} disabled={busy}><FlaskConical className={busy ? "animate-pulse" : ""} /> Run live</Button>
        {res && (
          <div className="term-mono rounded-lg border border-border bg-black/25 p-3 text-[11px] leading-relaxed">
            {res.pass_ !== undefined && (
              <div className={`mb-1 font-semibold ${res.pass_ ? "text-[#5fc9a8]" : "text-[#e06a5e]"}`}>
                {res.pass_ ? "PROOF PASS" : "PROOF FAIL"}
              </div>
            )}
            {kind === "cold" && (
              <>
                <div>virgin terms · doctrine v0 · bond {res.virgin_terms?.bond_usd}</div>
                <div>recalled terms · doctrine v{res.doctrine_version} · bond {res.recalled_terms?.bond_usd}</div>
                <div className="text-muted-foreground">a stranger's history changed the deal</div>
              </>
            )}
            {kind === "del" && (
              <div className="text-[#e06a5e]/90">{res.refusal ?? "??"}</div>
            )}
            {kind === "abl" && (
              <>
                <div>memoryless · upfront {res.naive?.upfront_usd} · bond {res.naive?.bond_usd}</div>
                <div>history-aware · upfront {res.governed?.upfront_usd} · bond {res.governed?.bond_usd}</div>
                <div>capital at risk reduced {Math.round((res.reduction ?? 0) * 100)}%</div>
              </>
            )}
            {res.ts && <div className="text-muted-foreground">ts {res.ts}</div>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function JudgeLab({ bump }: { bump: number }) {
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold tracking-[-0.03em]">Judge lab</h1>
      <p className="text-sm text-muted-foreground">
        Every button runs the real engine against real Sibyl memory. No canned output, no precomputed
        strings.
      </p>
      <div className="grid gap-4 lg:grid-cols-3">
        <ProofCard
          title="Cold start / fresh session"
          note="A brand-new process over the seeded Sibyl file recalls doctrine written earlier and returns different terms for the same request."
          kind="cold"
          run={() => api<Proof>("/api/judge/coldstart")}
        />
        <ProofCard
          title="Deletion test"
          note="The gate: remove Sibyl and the venue cannot construct authoritative terms. Refusal is the product."
          kind="del"
          run={() => api<Proof>("/api/judge/deletion")}
        />
        <ProofCard
          title="Ablation"
          note="History-aware vs memoryless CANON on identical work — measured capital delta."
          kind="abl"
          run={() => api<Proof>("/api/judge/ablation")}
        />
      </div>
      <p className="text-xs text-muted-foreground">
        Tip: run the full loop first — New transaction → lock escrow → provider failed → file claim.
        After five confirmed failures the doctrine bumps, and the cold-start proof returns a bond where
        there was none.
      </p>
    </div>
  );
}
