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

const metaBySlug: Record<string, {
  subtitle: string;
  kpis: Kpi[];
  highlights: Highlight[];
}> = {
  "2026-04": {
    subtitle: aprMeta.subtitle,
    kpis: aprMeta.kpis as Kpi[],
    highlights: aprMeta.highlights as Highlight[],
  },
  "2025-09": {
    subtitle: sepMeta.subtitle,
    kpis: sepMeta.kpis as Kpi[],
    highlights: sepMeta.highlights as Highlight[],
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
