import { useTheme } from "./ThemeProvider.jsx";
import { Moon, Sun } from "lucide-react";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
    >
      <Sun aria-hidden="true" size={15} />
      <Moon aria-hidden="true" size={15} />
      <span className="toggle-dot" />
    </button>
  );
}
