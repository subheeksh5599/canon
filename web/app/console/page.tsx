"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Copy, TerminalSquare } from "lucide-react";
import { engineConfigured } from "@/lib/api";
import { Sidebar, Overview, DealStudio, Transactions, type Section } from "@/components/console/panels";
import { AppealsView, CasesView, DoctrineView, JudgeLab } from "@/components/console/institution";
import { toast } from "sonner";

function ConnectGate() {
  const copy = async () => {
    const cmd = "cd canon && .venv/bin/uvicorn server.main:app --port 8000";
    try {
      await navigator.clipboard.writeText(cmd);
      toast.success("Command copied");
    } catch {
      toast.error("Clipboard unavailable");
    }
  };
  return (
    <main className="flex flex-1">
      <Sidebar current="overview" onNav={() => {}} />
      <div className="flex flex-1 items-center justify-center px-8 py-16">
        <div className="w-full max-w-xl">
          <div className="eyebrow mb-3 flex items-center gap-2">
            <span className="inline-block size-1.5 rounded-full bg-[#e06a5e]" />
            console · engine offline
          </div>
          <h1 className="text-3xl font-medium tracking-[-0.01em] sm:text-4xl">
            The engine lives where the memory lives.
          </h1>
          <p className="mt-4 leading-relaxed text-muted-foreground">
            CANON's terms are generated from a Sibyl memory file on the machine that runs the venue —
            that is what makes the memory load-bearing. The console drives that engine directly, so it
            runs from your machine with the backend beside it. No data leaves your process.
          </p>

          <div className="mt-8 space-y-3">
            <div className="border border-border bg-card rounded-sm px-5 py-4">
              <div className="eyebrow mb-2">Step 1 · start the venue</div>
              <div className="flex items-center justify-between gap-3">
                <code className="term-mono truncate text-[13px]">
                  .venv/bin/uvicorn server.main:app --port 8000
                </code>
                <button onClick={copy} className="shrink-0 text-muted-foreground hover:text-foreground">
                  <Copy className="size-4" />
                </button>
              </div>
            </div>
            <div className="border border-border bg-card rounded-sm px-5 py-4">
              <div className="eyebrow mb-2">Step 2 · open the console beside it</div>
              <code className="term-mono block truncate text-[13px]">
                cd web && npm run dev &nbsp;→&nbsp; http://localhost:3000/console
              </code>
            </div>
            <div className="border border-border bg-card rounded-sm px-5 py-4">
              <div className="flex items-start gap-3">
                <TerminalSquare className="mt-0.5 size-4 shrink-0" />
                <div className="text-sm text-muted-foreground">
                  Then run the judge lab: <span className="text-foreground">cold-start proof, deletion
                  test, ablation</span> — each button executes the real engine and prints its live
                  result. Full walkthrough in the repo README.
                </div>
              </div>
            </div>
          </div>

          <a
            href="https://github.com/subheeksh5599/canon"
            target="_blank"
            rel="noreferrer"
            className="mt-8 inline-flex items-center gap-2 text-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
          >
            github.com/subheeksh5599/canon <ArrowRight className="size-3.5" />
          </a>
        </div>
      </div>
    </main>
  );
}

export default function ConsolePage() {
  const [ready, setReady] = useState<boolean | null>(null);
  const [section, setSection] = useState<Section>("overview");
  const [bump, setBump] = useState(0);

  useEffect(() => {
    setReady(engineConfigured());
  }, []);

  const changed = () => setBump((n) => n + 1);

  if (ready === false) return <ConnectGate />;
  if (ready === null) return <div className="min-h-screen bg-background" />;

  return (
    <div className="flex min-h-screen">
      <Sidebar current={section} onNav={setSection} />
      <main className="flex-1">
        <div className="mx-auto max-w-6xl px-8 py-8">
          {section === "overview" && <Overview bump={bump} />}
          {section === "deal" && <DealStudio onDone={changed} />}
          {section === "transactions" && <Transactions bump={bump} />}
          {section === "institution" && (
            <div className="space-y-6">
              <DoctrineView bump={bump} />
              <AppealsView bump={bump} onChanged={changed} />
              <CasesView bump={bump} />
            </div>
          )}
          {section === "judge" && <JudgeLab bump={bump} />}
        </div>
      </main>
    </div>
  );
}
