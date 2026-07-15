import { useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

export default function PasswordField({
  autoComplete,
  label,
  minLength,
  name,
  required = false,
}) {
  const inputId = useId();
  const [isVisible, setIsVisible] = useState(false);
  const ToggleIcon = isVisible ? EyeOff : Eye;

  return (
    <div className="auth-password-field">
      <label htmlFor={inputId}>{label}</label>
      <div className="auth-password-control">
        <input
          id={inputId}
          name={name}
          type={isVisible ? "text" : "password"}
          autoComplete={autoComplete}
          minLength={minLength}
          required={required}
        />
        <button
          className="auth-password-toggle"
          type="button"
          aria-label={`${isVisible ? "Hide" : "Show"} ${label.toLowerCase()}`}
          aria-pressed={isVisible}
          onClick={() => setIsVisible((visible) => !visible)}
        >
          <ToggleIcon aria-hidden="true" size={18} strokeWidth={1.7} />
        </button>
      </div>
    </div>
  );
}
