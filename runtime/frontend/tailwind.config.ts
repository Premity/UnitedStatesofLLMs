import type { Config } from "tailwindcss";

// The palette is deliberately two-register: a warm, saturated courtroom for the
// live debate, and a sober parchment/ink register for the dissent log. Whimsy in
// the presentation, sobriety in the record.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        court: {
          bg: "#1a1229",        // deep courtroom dusk
          panel: "#241a3a",
          rail: "#3b2a5c",
          gold: "#e8b84b",      // brass fittings, the judge's bench
          crimson: "#c2384a",   // objection!
          ink: "#0f0a1a",
        },
        bench: {
          presenter: "#3d7ea6",   // defence blue
          doctrinal: "#c2384a",   // prosecution crimson
          evidentiary: "#d4763a", // prosecution amber
          judge: "#e8b84b",       // the bench
        },
        record: {
          paper: "#f7f3e9",
          ink: "#1f1a14",
          rule: "#d9d0bd",
          margin: "#8a7a5c",
        },
      },
      fontFamily: {
        display: ["Georgia", "Cambria", "serif"],
        record: ["Georgia", "Times New Roman", "serif"],
        ui: ["Inter", "system-ui", "sans-serif"],
      },
      keyframes: {
        // Sprites bob gently while their model is generating.
        bob: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        // The objection flourish: slam in, overshoot, settle.
        slam: {
          "0%": { transform: "scale(0.3) rotate(-12deg)", opacity: "0" },
          "60%": { transform: "scale(1.15) rotate(3deg)", opacity: "1" },
          "80%": { transform: "scale(0.95) rotate(-1deg)" },
          "100%": { transform: "scale(1) rotate(0deg)", opacity: "1" },
        },
        shake: {
          "0%, 100%": { transform: "translateX(0)" },
          "20%": { transform: "translateX(-8px)" },
          "40%": { transform: "translateX(8px)" },
          "60%": { transform: "translateX(-4px)" },
          "80%": { transform: "translateX(4px)" },
        },
        // Speech bubbles arrive with a small pop.
        pop: {
          "0%": { transform: "scale(0.9) translateY(8px)", opacity: "0" },
          "100%": { transform: "scale(1) translateY(0)", opacity: "1" },
        },
        gavel: {
          "0%": { transform: "rotate(-35deg)" },
          "50%": { transform: "rotate(8deg)" },
          "100%": { transform: "rotate(0deg)" },
        },
      },
      animation: {
        bob: "bob 2.2s ease-in-out infinite",
        slam: "slam 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards",
        shake: "shake 0.4s ease-in-out",
        pop: "pop 0.25s ease-out forwards",
        gavel: "gavel 0.5s ease-out forwards",
      },
    },
  },
  plugins: [],
} satisfies Config;
