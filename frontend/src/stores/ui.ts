import { create } from "zustand";

type Theme = "dark" | "light";

type UIState = {
  theme: Theme;
  paletteOpen: boolean;
  paletteText: string;
  askOpen: boolean;
  toggleTheme: () => void;
  openPalette: (text?: string) => void;
  closePalette: () => void;
  setAsk: (open: boolean) => void;
};

const initialTheme = (): Theme => {
  try {
    return (localStorage.getItem("theme") as Theme) || "dark";
  } catch {
    return "dark";
  }
};

export const useUI = create<UIState>((set, get) => ({
  theme: initialTheme(),
  paletteOpen: false,
  paletteText: "",
  askOpen: false,
  toggleTheme: () => {
    const theme = get().theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* private mode */
    }
    set({ theme });
  },
  openPalette: (text = "") => set({ paletteOpen: true, paletteText: text }),
  closePalette: () => set({ paletteOpen: false, paletteText: "" }),
  setAsk: (askOpen) => set({ askOpen }),
}));
