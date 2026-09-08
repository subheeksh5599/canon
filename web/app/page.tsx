import Link from "next/link";
import { ArrowRight, Scale, Landmark, FileText, Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const REAL_BEFORE = { upfront: "$400", bond: "$0", rule: "no doctrine" };
const REAL_AFTER = { upfront: "$100", milestones: "3", bond: "$80", coverage: "80%" };

const features = [
  {
    icon: Landmark,
    title: "It is the venue, not middleware",
    body: "Agents transact inside CANON. Admission is recorded; a direct Base transfer outside the venue carries none of CANON's guarantees.",
  },
  {
    icon: FileText,
    title: "Terms, not scores",
    body: "The output is an executable contract — upfront cap, milestones, bond, coverage — generated deterministically from stored doctrine. No LLM touches the money path.",
  },
  {
    icon: Layers,
    title: "Doctrine that evolves",
    body: "Resolved cases cross evidence thresholds and amend the stored rules. One agent's loss becomes a rule that protects everyone — then decays when the pattern stops.",
  },
  {
    icon: Scale,
    title: "Rules you can contest",
    body: "Post a bond, challenge a precedent, and a winning appeal amends the doctrine for the whole economy. History is not frozen — it is contestable.",
  },
];

export default function Home() {
  return (
    <main className="relative flex-1 overflow-hidden">
      <div className="canon-grid-bg pointer-events-none absolute inset-0" />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-96 w-[42rem] -translate-x-1/2 rounded-full bg-emerald-500/12 blur-[110px]" />

      {/* nav */}
      <nav className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2">
          <span className="term-mono text-lg font-semibold tracking-tight">CANON</span>
          <span className="mt-0.5 rounded border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">
            venue
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/console">
            <Button variant="ghost" size="sm">
              Console
            </Button>
          </Link>
          <Link href="/console">
            <Button size="sm">
              Enter the venue <ArrowRight />
            </Button>
          </Link>
        </div>
      </nav>

      {/* hero */}
      <section className="relative z-10 mx-auto max-w-6xl px-6 pt-16 pb-24 text-center">
        <Badge variant="secondary" className="mb-6 gap-2 rounded-full px-3 py-1 text-xs">
          <span className="size-1.5 rounded-full bg-emerald-400" />
          Sibyl Labs Hackathon 2026 · Base + Virtuals
        </Badge>
        <h1 className="mx-auto max-w-4xl text-balance text-5xl font-semibold tracking-tight sm:text-6xl">
          The exchange where agents transact under terms{" "}
          <span className="gradient-text">the economy itself writes</span>.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-muted-foreground">
          Autonomous agents hire and pay each other with no institutional memory — so every deal
          starts naive. CANON remembers every case, turns collective precedent into doctrine, and
          rewrites the terms of the next transaction. A stranger's past failure changes the exact
          contract you receive today. Not a score. Not a warning. Not a denial.{" "}
          <span className="text-foreground">A different deal.</span>
        </p>
        <div className="mt-10 flex items-center justify-center gap-3">
          <Link href="/console">
            <Button size="lg" className="gap-2 rounded-xl px-6 glow-primary">
              Run the judge lab <ArrowRight />
            </Button>
          </Link>
          <Link href="#how">
            <Button size="lg" variant="outline" className="rounded-xl px-6">
              How it works
            </Button>
          </Link>
        </div>

        {/* live terms card — real engine output */}
        <div className="mx-auto mt-16 max-w-3xl">
          <div className="glass overflow-hidden rounded-2xl text-left">
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <span className="term-mono text-xs text-muted-foreground">
                ven://market/terms · doctrine v0 → v1
              </span>
              <Badge className="rounded-full bg-emerald-500/15 text-emerald-300">5 confirmed cases</Badge>
            </div>
            <div className="grid grid-cols-2 divide-x divide-border sm:grid-cols-4">
              {[
                { k: "Upfront", v: `${REAL_BEFORE.upfront} → ${REAL_AFTER.upfront}`, note: "cap" },
                { k: "Milestones", v: `1 → ${REAL_AFTER.milestones}`, note: "escrowed" },
                { k: "Bond", v: `${REAL_BEFORE.bond} → ${REAL_AFTER.bond}`, note: "held on Base" },
                { k: "Coverage", v: `0% → ${REAL_AFTER.coverage}`, note: "pool" },
              ].map((c) => (
                <div key={c.k} className="px-5 py-5">
                  <div className="text-[11px] uppercase tracking-widest text-muted-foreground">
                    {c.k}
                  </div>
                  <div className="term-mono mt-1.5 text-lg font-semibold">{c.v}</div>
                  <div className="text-[11px] text-muted-foreground">{c.note}</div>
                </div>
              ))}
            </div>
            <div className="border-t border-border bg-black/20 px-5 py-3 term-mono text-xs text-muted-foreground">
              rule CANON-001-research · supporting cases: 5 unrelated participants · same job, same
              capital — only memory differs
            </div>
          </div>
        </div>
      </section>

      {/* features */}
      <section id="how" className="relative z-10 mx-auto max-w-6xl px-6 pb-24">
        <div className="mb-10 text-center">
          <h2 className="text-3xl font-semibold tracking-tight">An institution, not a wrapper</h2>
          <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
            CANON is built on the rule that memory must be load-bearing: delete Sibyl and CANON
            cannot construct a transaction.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {features.map((f) => (
            <div key={f.title} className="glass group rounded-2xl p-6 transition-colors hover:border-emerald-400/30">
              <f.icon className="mb-4 size-5 text-emerald-300" />
              <h3 className="font-semibold tracking-tight">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </div>

        {/* the loop */}
        <div className="glass mt-10 rounded-2xl p-6">
          <div className="mb-4 text-[11px] uppercase tracking-widest text-muted-foreground">
            the canon loop
          </div>
          <div className="term-mono flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
            {["transactions", "collective memory", "precedent", "doctrine", "executable terms", "Base", "challenge"].map(
              (s, i, arr) => (
                <span key={s} className="flex items-center gap-3">
                  <span className="rounded-md border border-border bg-muted px-2.5 py-1">{s}</span>
                  {i < arr.length - 1 && <span className="text-emerald-400">→</span>}
                </span>
              ),
            )}
          </div>
        </div>
      </section>

      {/* footer */}
      <footer className="relative z-10 border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-6 text-sm text-muted-foreground sm:flex-row">
          <span className="term-mono">CANON · MIT · built for the Sibyl Labs Hackathon 2026</span>
          <Link href="/console" className="inline-flex items-center gap-1.5 hover:text-foreground">
            Open the console <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </footer>
    </main>
  );
}
