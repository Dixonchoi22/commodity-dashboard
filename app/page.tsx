import Link from "next/link";
import { reports } from "@/lib/reports";

const toneRing: Record<string, string> = {
  blue: "ring-primary-blue/30",
  red: "ring-secondary-red/30",
  green: "ring-accent-green/30",
  warning: "ring-text-warning/30",
};

const toneText: Record<string, string> = {
  blue: "text-primary-blue",
  red: "text-secondary-red",
  green: "text-accent-green",
  warning: "text-text-warning",
};

const highlightBorder: Record<string, string> = {
  red: "border-secondary-red",
  green: "border-accent-green",
  blue: "border-primary-blue",
};

const highlightText: Record<string, string> = {
  red: "text-secondary-red",
  green: "text-accent-green",
  blue: "text-primary-blue",
};

export default function HomePage() {
  return (
    <main className="max-w-7xl mx-auto p-4 sm:p-8">
      <header className="mb-10">
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-primary-blue to-blue-300">
          Commodity Dashboard
        </h1>
        <p className="text-xl text-dark-muted mt-2">
          Monthly commodity intelligence reports for food &amp; catering procurement
        </p>
      </header>

      <section className="space-y-8">
        {reports.map((report) => (
          <article
            key={report.slug}
            className="bg-dark-card rounded-xl p-6 shadow-xl-dark"
          >
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-6">
              <div>
                <p className="text-xs uppercase tracking-wider text-dark-muted font-semibold">
                  {report.region} &middot; {report.period}
                </p>
                <h2 className="text-2xl font-bold text-dark-text mt-1">
                  {report.title}
                </h2>
                <p className="text-sm text-dark-muted mt-1">{report.subtitle}</p>
              </div>
              <Link
                href={report.html}
                target="_blank"
                className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-primary-blue/10 border border-primary-blue/30 text-primary-blue text-sm font-semibold hover:bg-primary-blue/20 transition"
              >
                Open full report &rarr;
              </Link>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {report.kpis.map((kpi) => (
                <div
                  key={kpi.label}
                  className={`bg-dark-bg/60 rounded-xl p-4 text-center ring-2 ${toneRing[kpi.tone]}`}
                >
                  <p className="text-xs font-medium text-dark-muted uppercase">
                    {kpi.label}
                  </p>
                  <p
                    className={`text-2xl font-extrabold mt-1 ${toneText[kpi.tone]}`}
                  >
                    {kpi.value}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">{kpi.caption}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {report.highlights.map((h) => (
                <div
                  key={h.label}
                  className={`p-3 bg-dark-bg/50 rounded-lg border-l-4 ${highlightBorder[h.tone]}`}
                >
                  <p className={`font-bold ${highlightText[h.tone]}`}>
                    {h.label}
                  </p>
                  <p className="text-sm text-gray-300 mt-1">{h.body}</p>
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      <footer className="mt-12 text-xs text-dark-muted">
        Add a new month: drop raw sources into <code>data/{"{YYYY-MM}"}/raw/</code>,
        run <code>python scripts/extract_april_2026.py</code> then{" "}
        <code>python scripts/build_html.py {"{YYYY-MM}"}</code>, and register it
        in <code>data/manifest.json</code>.
      </footer>
    </main>
  );
}
