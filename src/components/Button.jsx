import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

function ButtonContent({ children, variant }) {
  return (
    <>
      <span>{children}</span>
      {variant === "primary" && <ArrowUpRight aria-hidden="true" size={16} strokeWidth={1.8} />}
    </>
  );
}

export default function Button({ children, to, href, variant = "primary", className = "", ...props }) {
  const classes = `btn btn-${variant} ${className}`.trim();

  if (to) {
    return (
      <Link className={classes} to={to} {...props}>
        <ButtonContent variant={variant}>{children}</ButtonContent>
      </Link>
    );
  }

  if (href) {
    return (
      <a className={classes} href={href} {...props}>
        <ButtonContent variant={variant}>{children}</ButtonContent>
      </a>
    );
  }

  return (
    <button className={classes} {...props}>
      <ButtonContent variant={variant}>{children}</ButtonContent>
    </button>
  );
}
