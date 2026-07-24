import { statusBgColor, statusColor } from "../../utils/format";
import type { StatusBadgeProps } from "../../types/api";

export function StatusBadge({
  status,
  size = "sm",
  animated = false,
  className = "",
}: StatusBadgeProps) {
  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-1 text-sm",
    lg: "px-3 py-1.5 text-base",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium capitalize
        ${statusBgColor(status)}
        ${statusColor(status)}
        ${sizeClasses[size]}
        ${animated && (status === "running" || status === "busy") ? "animate-pulse-glow" : ""}
        ${className}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${statusColor(status).replace("text-", "bg-")}
          ${animated && (status === "running" || status === "busy") ? "animate-pulse" : ""}`}
      />
      {status}
    </span>
  );
}
