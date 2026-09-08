"use client";

import { useEffect, useState } from "react";
import { Sidebar, Overview, DealStudio, Transactions, type Section } from "@/components/console/panels";
import { AppealsView, CasesView, DoctrineView, JudgeLab } from "@/components/console/institution";

export default function ConsolePage() {
  const [section, setSection] = useState<Section>("overview");
  const [bump, setBump] = useState(0);
  const [reachable, setReachable] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_CANON_API ?? "http://localhost:8000"}/api/health`, { cache: "no-store" })
      .then((r) => setReachable(r.ok))
      .catch(() => setReachable(false));
  }, [bump]);

  const changed = () => setBump((n) => n + 1);

  return (
    <div className="flex min-h-screen">
      <Sidebar current={section} onNav={setSection} />
      <main className="relative flex-1 overflow-y-auto">
        <div className="canon-grid-bg pointer-events-none absolute inset-0" />
        <div className="pointer-events-none absolute -top-24 right-0 h-64 w-96 rounded-full bg-emerald-500/10 blur-[100px]" />
        <div className="relative mx-auto max-w-6xl px-8 py-8">
          {reachable === false && (
            <div className="mb-6 rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              Backend unreachable on port 8000. Start it from the repo root:{" "}
              <span className="term-mono">.venv/bin/uvicorn server.main:app --port 8000</span>
            </div>
          )}
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
