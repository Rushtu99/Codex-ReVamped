import { Eye, EyeOff, LogOut, Menu } from "lucide-react";
import { useState } from "react";
import { NavLink } from "react-router-dom";

import { CodexLogo } from "@/components/brand/codex-logo";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { usePrivacyStore } from "@/hooks/use-privacy";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/omx", label: "OMX" },
  { to: "/local-models", label: "Local Models" },
  { to: "/accounts", label: "Accounts" },
  { to: "/settings", label: "Settings" },
] as const;

export type AppHeaderProps = {
  onLogout: () => void;
  showLogout?: boolean;
  className?: string;
};

export function AppHeader({
  onLogout,
  showLogout = true,
  className,
}: AppHeaderProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const blurred = usePrivacyStore((s) => s.blurred);
  const togglePrivacy = usePrivacyStore((s) => s.toggle);
  const PrivacyIcon = blurred ? EyeOff : Eye;

  return (
    <header
      className={cn(
        "sticky top-0 z-20 border-b bg-background/95 px-4 py-2.5 supports-[backdrop-filter]:bg-background/88 supports-[backdrop-filter]:backdrop-blur",
        className,
      )}
    >
      <div className="mx-auto flex w-full max-w-[1500px] items-center justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
            <CodexLogo size={18} className="text-current" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight">CodexLB ReVamped</p>
            <p className="truncate text-[11px] text-muted-foreground">Local balance control for your account pool</p>
          </div>
        </div>

        <nav className="hidden items-center gap-1 sm:flex">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "relative inline-flex h-8 items-center rounded-md border px-3.5 text-xs leading-none font-medium transition-colors duration-150",
                  isActive
                    ? "border-primary/35 bg-primary/12 text-foreground"
                    : "border-transparent text-muted-foreground hover:border-border hover:bg-muted/70 hover:text-foreground",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex flex-1 items-center justify-end gap-1.5">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={togglePrivacy}
            aria-label={blurred ? "Show emails" : "Hide emails"}
            className="press-scale hidden h-8 w-8 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground sm:inline-flex"
          >
            <PrivacyIcon className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
          {showLogout && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onLogout}
              className="press-scale hidden h-8 gap-1.5 rounded-md text-xs text-muted-foreground hover:bg-muted hover:text-foreground sm:inline-flex"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
              Logout
            </Button>
          )}

          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button type="button" size="icon" variant="ghost" aria-label="Open menu" className="h-8 w-8 rounded-md sm:hidden">
                <Menu className="h-4 w-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-72">
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2.5">
                  <div className="flex h-7 w-7 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary">
                    <CodexLogo size={16} className="text-current" />
                  </div>
                  <span className="text-sm font-semibold">CodexLB ReVamped</span>
                </SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-0.5 px-4 pt-2">
                {NAV_ITEMS.map((item) => (
                  <NavLink key={item.to} to={item.to} onClick={() => setMobileOpen(false)}>
                    {({ isActive }) => (
                      <span
                        className={cn(
                          "block w-full rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors",
                          isActive
                            ? "bg-primary/10 text-primary"
                            : "text-muted-foreground hover:bg-muted hover:text-foreground",
                        )}
                      >
                        {item.label}
                      </span>
                    )}
                  </NavLink>
                ))}
                <div className="my-2 h-px bg-border" />
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  onClick={togglePrivacy}
                >
                  <PrivacyIcon className="h-3.5 w-3.5" aria-hidden="true" />
                  {blurred ? "Show Emails" : "Hide Emails"}
                </button>
                {showLogout && (
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                    onClick={() => {
                      setMobileOpen(false);
                      onLogout();
                    }}
                  >
                    <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                    Logout
                  </button>
                )}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
