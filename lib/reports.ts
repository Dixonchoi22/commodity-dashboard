import manifest from "@/data/manifest.json";
import aprMeta from "@/data/2026-04/meta.json";

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

const metaBySlug: Record<string, { subtitle?: string; kpis?: Kpi[]; highlights?: Highlight[] }> = {
  "2026-04": {
    subtitle: aprMeta.subtitle,
    kpis: aprMeta.kpis as Kpi[],
    highlights: aprMeta.highlights as Highlight[],
  },
  "2025-09": {
    subtitle: "Key cost drivers for food & catering",
    kpis: [
      { label: "HICP Food Index (Sep)", value: "147.8", caption: "2015 = 100 base", tone: "blue" },
      { label: "YoY Overall Inflation", value: "+3.0%", caption: "vs. Sep 2024 (HICP)", tone: "red" },
      { label: "Highest MoM Price Hike", value: "Hazelnuts Turkey +34.3%", caption: "Immediate cost pressure", tone: "red" },
      { label: "MoM Overall Change", value: "-0.2%", caption: "vs. Aug 2025 (HICP)", tone: "green" },
    ],
    highlights: [
      { tone: "red", label: "Extreme price risk", body: "Hazelnuts Turkey +135.3% YoY; Beef EU +38.7% YoY." },
      { tone: "green", label: "Major opportunity", body: "Potato processing EU -60.0% YoY; Orange Juice US -49.9% YoY." },
      { tone: "blue", label: "Softs / beverage", body: "Robusta Coffee -18.1% YoY — watch forward curve." },
    ],
  },
};

export const reports: Report[] = manifest.reports.map((r) => {
  const extras = metaBySlug[r.slug] ?? {};
  return {
    slug: r.slug,
    title: r.title,
    subtitle: extras.subtitle ?? "",
    region: r.region,
    period: r.period,
    html: r.html,
    kpis: extras.kpis ?? [],
    highlights: extras.highlights ?? [],
  };
});
