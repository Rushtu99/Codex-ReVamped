import { cn } from "@/lib/utils";

export type CodexLogoProps = {
  className?: string;
  size?: number;
};

export function CodexLogo({ className, size = 32 }: CodexLogoProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      fill="none"
      viewBox="0 0 32 32"
      className={cn("shrink-0", className)}
    >
      <path
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.2"
        d="M10.25 9.75h11.5M10.25 22.25h11.5M8.75 14.75l3 3-3 3M23.25 14.25l-3 3 3 3"
      />
      <path
        stroke="currentColor"
        strokeWidth="2.2"
        d="M30.1 16c0 7.786-6.314 14.1-14.1 14.1S1.9 23.786 1.9 16 8.214 1.9 16 1.9 30.1 8.214 30.1 16Z"
      />
    </svg>
  );
}
