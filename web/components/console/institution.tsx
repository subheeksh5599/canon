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
          No doctrine yet — the venue is not founded. A venue must be chartered
          before it can construct terms; after that, only real resolved cases and bonded appeals move it.
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
          challenger: "0x31eafd3fe36d6c891ea5b369a876166dffabf320",
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

