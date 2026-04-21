import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        "primary-blue": "#60A5FA",
        "secondary-red": "#F87171",
        "accent-green": "#4ADE80",
        "text-warning": "#FACC15",
        "dark-bg": "#0F172A",
        "dark-card": "#1E293B",
        "dark-text": "#F8FAFC",
        "dark-muted": "#94A3B8",
      },
      boxShadow: {
        "xl-dark":
          "0 20px 25px -5px rgba(0,0,0,0.3), 0 8px 10px -6px rgba(0,0,0,0.3)",
        "3xl": "0 35px 60px -15px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
