export type ReportKpi = {
  label: string;
  value: string;
  caption: string;
  tone: "blue" | "red" | "green" | "warning";
};

export type Report = {
  slug: string;
  title: string;
  subtitle: string;
  region: string;
  period: string;
  file: string;
  kpis: ReportKpi[];
  highlights: { tone: "red" | "green" | "blue"; label: string; body: string }[];
};

export const reports: Report[] = [
  {
    slug: "eu-outlook-sep-2025",
    title: "Commodity Intelligence: EU Outlook",
    subtitle: "Key cost drivers for food & catering",
    region: "European Union",
    period: "September 2025",
    file: "/reports/eu-outlook-sep-2025.html",
    kpis: [
      {
        label: "HICP Food Index (Sep)",
        value: "147.8",
        caption: "2015 = 100 base",
        tone: "blue",
      },
      {
        label: "YoY Overall Inflation",
        value: "+3.0%",
        caption: "vs. Sep 2024 (HICP)",
        tone: "red",
      },
      {
        label: "Highest MoM Price Hike",
        value: "Hazelnuts Turkey +34.3%",
        caption: "Immediate cost pressure",
        tone: "red",
      },
      {
        label: "MoM Overall Change",
        value: "-0.2%",
        caption: "vs. Aug 2025 (HICP)",
        tone: "green",
      },
    ],
    highlights: [
      {
        tone: "red",
        label: "Extreme price risk",
        body: "Hazelnuts Turkey +135.3% YoY; Beef EU +38.7% YoY.",
      },
      {
        tone: "green",
        label: "Major opportunity",
        body: "Potato processing EU -60.0% YoY; Orange Juice US -49.9% YoY.",
      },
      {
        tone: "blue",
        label: "Softs / beverage",
        body: "Robusta Coffee -18.1% YoY — watch forward curve.",
      },
    ],
  },
];

export function getReport(slug: string): Report | undefined {
  return reports.find((r) => r.slug === slug);
}
