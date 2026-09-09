import Link from "next/link";

/* Deterministic seeded starfield — stable across renders (mulberry32). */
function seededStars(count: number, seed = 42) {
  let s = seed >>> 0;
  const rnd = () => {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return Array.from({ length: count }, (_, i) => ({
    id: i,
    left: rnd() * 100,
    top: rnd() * 100,
    size: rnd() > 0.88 ? 2 : 1,
    tw: 4 + rnd() * 7,
    td: rnd() * 9,
  }));
}

const STARS = seededStars(110);

const SPEC_ROWS = [
  { lvl: "L1 · Market", name: "No memory", desc: "Every session starts blind. The same bad actor gets the same naive terms forever: 100% upfront, no bond, no recourse." },
  { lvl: "L2 · Venue", name: "CANON", desc: "Agents transact inside the venue. Admission is recorded; every case becomes part of the venue's institutional memory." },
  { lvl: "L3 · Doctrine", name: "Terms, generated", desc: "Resolved cases refresh the governing rule's evidence; rules decay without support; a bonded appeal amends the doctrine for everyone." },
  { lvl: "L4 · Appeal", name: "Contestable", desc: "Post a bond and challenge a precedent. A winning appeal amends the doctrine for every future transaction." },
];

const MECH = ["transactions", "collective memory", "precedent", "doctrine", "executable terms", "base"];

const NAIVE = ["no memory between sessions", "100% upfront every time", "no bond, no escrow, no recourse", "one failure teaches nothing"];
const CANON = ["terms from doctrine stored in memory", "bond + milestones where the charter requires", "rules amended only by real bonded appeals", "real resolved cases keep the rule alive — or let it decay"];

const RECEIPT = [
  { k: "Upfront", before: "$400", after: "$100" },
  { k: "Milestones", before: "1", after: "3" },
  { k: "Bond", before: "$0", after: "$80" },
  { k: "Coverage", before: "0%", after: "80%" },
];

export default function Home() {
  return (
    <main className="relative">
      {/* night sky */}
      <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
        {STARS.map((st) => (
          <span
            key={st.id}
            className="star"
            style={{
              left: `${st.left}%`,
              top: `${st.top}%`,
              width: st.size,
              height: st.size,
              ["--tw" as string]: `${st.tw}s`,
              ["--td" as string]: `${st.td}s`,
            }}
          />
        ))}
      </div>

      {/* nav */}
      <header className="fixed inset-x-0 top-0 z-40 border-b border-border bg-[#070b13]/85 backdrop-blur-md">
        <div className="mx-auto flex w-full max-w-[1120px] items-center justify-between px-6 py-4">
          <span className="display text-xl font-semibold">Canon</span>
          <Link href="/console" className="mono-label text-[#8b94a7] transition-colors hover:text-[#5fc9a8]">
            Console →
          </Link>
        </div>
      </header>

      {/* hero */}
      <section className="relative mx-auto w-full max-w-[1120px] px-6 pt-44 pb-32">
        <div className="mono-label mb-8 text-[#55607a]">The venue layer for autonomous agents</div>
        <h1
          className="display max-w-4xl font-medium"
          style={{ fontSize: "clamp(2.75rem, 7.5vw, 6rem)" }}
        >
          Agents hire in the dark.
          <br />
          <span style={{ color: "#5fc9a8" }}>The venue writes the terms.</span>
        </h1>
        <p className="mt-8 max-w-xl text-[17px] leading-relaxed text-[#8b94a7]">
          The terms of every deal come from doctrine stored in the venue's memory — founded by a
          declared charter, amended only by real bonded appeals, kept alive by real resolved cases.
          Not a score. Not a warning. Not a denial. A different deal — executed in USDC on Base.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Link href="/console" className="btn-mint data px-5 py-2.5 text-sm">
            Open the console
          </Link>
          <Link href="#fig-02" className="btn-ghost data px-5 py-2.5 text-sm text-[#e9ecf3]">
            See the mechanism
          </Link>
        </div>
      </section>

      {/* FIG 01 — spec sheet */}
      <section id="fig-01" className="relative border-t border-border bg-[#0a101c] py-[140px]">
        <div className="mx-auto w-full max-w-[1120px] px-6">
          <div className="fig mb-14">
            <span className="mono-label text-[#55607a]">Fig 01 — The missing layer</span>
          </div>
          <div>
            {SPEC_ROWS.map((r) => (
              <div key={r.name} className="sheet-row">
                <span className="mono-label text-[#55607a]">{r.lvl}</span>
                <span className="text-lg font-medium text-[#e9ecf3]">{r.name}</span>
                <span className="text-[15px] leading-relaxed text-[#8b94a7]">{r.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FIG 02 — mechanism */}
      <section id="fig-02" className="relative border-t border-border py-[140px]">
        <div className="mx-auto w-full max-w-[1120px] px-6">
          <div className="fig mb-6">
            <span className="mono-label text-[#55607a]">Fig 02 — The canon loop</span>
          </div>
          <p className="mb-14 max-w-md text-[15px] leading-relaxed text-[#8b94a7]">
            Each outcome feeds the memory that generated it. The loop is the product.
          </p>
          <div className="flex flex-wrap items-center gap-x-0 gap-y-4">
            {MECH.map((m, i) => (
              <div key={m} className="flex items-center">
                <span className="data rounded-sm border border-[rgba(233,236,243,0.16)] bg-[#0d1424] px-4 py-2 text-sm text-[#e9ecf3]">
                  {m}
                </span>
                {i < MECH.length - 1 && <span className="mech-link mx-4 block h-px w-14" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FIG 03 — comparison */}
      <section id="fig-03" className="relative border-t border-border bg-[#0a101c] py-[140px]">
        <div className="mx-auto w-full max-w-[1120px] px-6">
          <div className="fig mb-14">
            <span className="mono-label text-[#55607a]">Fig 03 — Same job, different terms</span>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            {/* today */}
            <div className="border border-[rgba(224,106,94,0.35)] bg-[#0d1424] p-7">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-[#e9ecf3]">Outside the venue</h2>
                <span className="chip-bad data px-2 py-1 text-[10px]">no memory</span>
              </div>
              <ul className="mt-6 space-y-3">
                {NAIVE.map((t) => (
                  <li key={t} className="flex items-start gap-3 text-[15px] text-[#8b94a7]">
                    <span className="mt-0.5 text-[#e06a5e]">✕</span> {t}
                  </li>
                ))}
              </ul>
              <div className="mt-8 border-t border-[rgba(233,236,243,0.08)] pt-5">
                <div className="data text-[13px] text-[#8b94a7]">offer today</div>
                <div className="display mt-1 text-3xl font-semibold text-[#e9ecf3]">$400 upfront · $0 bond</div>
              </div>
            </div>

            {/* canon */}
            <div className="border border-[rgba(95,201,168,0.45)] bg-[#0d1424] p-7">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-[#e9ecf3]">Inside Canon</h2>
                <span className="chip-ok data px-2 py-1 text-[10px]">charter-governed</span>
              </div>
              <ul className="mt-6 space-y-3">
                {CANON.map((t) => (
                  <li key={t} className="flex items-start gap-3 text-[15px] text-[#8b94a7]">
                    <span className="mt-0.5 text-[#5fc9a8]">✓</span> {t}
                  </li>
                ))}
              </ul>
              <div className="mt-8 border-t border-[rgba(233,236,243,0.08)] pt-5">
                <div className="data text-[13px] text-[#8b94a7]">offer today — recalled from memory</div>
                <div className="display mt-1 text-3xl font-semibold" style={{ color: "#5fc9a8" }}>
                  $100 upfront · $80 bond
                </div>
                <div className="data mt-2 text-[11px] text-[#55607a]">
                  doctrine v1 · rule CANON-001-research · founded by charter
                </div>
              </div>
            </div>
          </div>

          {/* receipt strip */}
          <div className="mt-6 border border-[rgba(233,236,243,0.12)] bg-[#0d1424]">
            <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-5">
              {RECEIPT.map((r) => (
                <div key={r.k}>
                  <div className="mono-label text-[#55607a]">{r.k}</div>
                  <div className="data mt-1 text-lg text-[#e9ecf3]">
                    {r.before} <span className="text-[#55607a]">→</span>{" "}
                    <span style={{ color: "#5fc9a8" }}>{r.after}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* closing claim */}
      <section className="relative border-t border-border py-32">
        <div className="mx-auto flex w-full max-w-[1120px] flex-col items-start justify-between gap-10 px-6 md:flex-row md:items-center">
          <div>
            <p className="display text-3xl font-medium md:text-5xl">
              Delete the memory.
              <br />
              The venue stops.
            </p>
            <p className="mt-3 max-w-md text-[15px] text-[#8b94a7]">
              That is the design, not a failure mode. The claim is testable — the verification console runs
              the deletion proof against the live engine.
            </p>
          </div>
          <Link href="/console" className="btn-mint data shrink-0 px-6 py-3 text-sm">
            Open the console
          </Link>
        </div>
      </section>

      {/* footer */}
      <footer className="border-t border-border">
        <div className="mx-auto flex w-full max-w-[1120px] flex-wrap items-center justify-between gap-3 px-6 py-6">
          <span className="mono-label text-[#55607a]">Canon · MIT</span>
          <Link href="/console" className="mono-label text-[#55607a] transition-colors hover:text-[#5fc9a8]">
            console →
          </Link>
        </div>
      </footer>
    </main>
  );
}
