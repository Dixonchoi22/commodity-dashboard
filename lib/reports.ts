import manifest from "@/data/manifest.json";
import aprMeta from "@/data/2026-04/meta.json";
import sepMeta from "@/data/2025-09/meta.json";

export type Kpi = {
  label: string;
  value: string;
  caption: string;
  tone: "blue" | "red" | "green" | "warning";
};

export type Highlight = {
  tone: "red" | "green" | "blue";
  label: string;
  body: string;
};

export type Report = {
  slug: string;
  title: string;
  subtitle: string;
  region: string;
  period: string;
  html: string;
  kpis: Kpi[];
  highlights: Highlight[];
};

// Per-slug overrides for the home-page card. KPI values are intentionally
// optional here — for periods built by scripts/build_html.py, the KPI cards
// are auto-computed from the underlying JSON at HTML build time, so we
// don't repeat them here. Sep 2025 is a legacy snapshot whose kpis live in
// meta.json, so we still surface them.
type MetaWithExtras = {
  subtitle?: string;
  kpis?: Kpi[];
  highlights?: Highlight[];
};

const metaBySlug: Record<string, MetaWithExtras> = {
  "2026-04": {
    subtitle: (aprMeta as unknown as MetaWithExtras).subtitle,
    kpis: (aprMeta as unknown as MetaWithExtras).kpis,
    highlights: (aprMeta as unknown as MetaWithExtras).highlights,
  },
  "2025-09": {
    subtitle: (sepMeta as unknown as MetaWithExtras).subtitle,
    kpis: (sepMeta as unknown as MetaWithExtras).kpis,
    highlights: (sepMeta as unknown as MetaWithExtras).highlights,
  },
};

export const reports: Report[] = manifest.reports.map((r) => {
  const extras = metaBySlug[r.slug];
  return {
    slug: r.slug,
    title: r.title,
    subtitle: extras?.subtitle ?? "",
    region: r.region,
    period: r.period,
    html: r.html,
    kpis: extras?.kpis ?? [],
    highlights: extras?.highlights ?? [],
  };
});
