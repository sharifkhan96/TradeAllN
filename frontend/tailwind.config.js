/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        panel: v("panel"),
        panel2: v("panel-2"),
        line: v("line"),
        fg: v("fg"),
        muted: v("muted"),
        faint: v("faint"),
        up: v("up"),
        down: v("down"),
        accent: v("accent"),
        ai: v("ai"),
        warn: v("warn"),
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: { "2xs": ["0.6875rem", "1rem"] },
      boxShadow: {
        pop: "0 12px 40px -12px rgb(0 0 0 / 0.45), 0 0 0 1px rgb(var(--line) / 1)",
      },
      keyframes: {
        flashUp: { "0%": { color: "rgb(var(--up))", backgroundColor: "rgb(var(--up) / 0.12)" }, "100%": { backgroundColor: "transparent" } },
        flashDown: { "0%": { color: "rgb(var(--down))", backgroundColor: "rgb(var(--down) / 0.12)" }, "100%": { backgroundColor: "transparent" } },
        marquee: { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        fadeIn: { "0%": { opacity: 0, transform: "translateY(4px)" }, "100%": { opacity: 1, transform: "none" } },
        pulseDot: { "0%,100%": { opacity: 1 }, "50%": { opacity: 0.35 } },
      },
      animation: {
        flashUp: "flashUp 700ms ease-out",
        flashDown: "flashDown 700ms ease-out",
        marquee: "marquee 70s linear infinite",
        fadeIn: "fadeIn 220ms ease-out",
        pulseDot: "pulseDot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
