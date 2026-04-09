import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Zaftech brand palette
        navy: "#1a202c",
        teal: {
          DEFAULT: "#14B8A6",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
        },
        electric: {
          DEFAULT: "#2563EB",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
        },
        grape: {
          DEFAULT: "#9333ea",
          400: "#c084fc",
          500: "#a855f7",
          600: "#9333ea",
        },
      },
      fontFamily: {
        heading: ["system-ui", "sans-serif"],
        sans: ["system-ui", "sans-serif"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "float": "float 6s ease-in-out infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
      },
      backgroundImage: {
        "hero-gradient": "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)",
        "card-gradient": "linear-gradient(135deg, rgba(20,184,166,0.08) 0%, rgba(37,99,235,0.08) 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
