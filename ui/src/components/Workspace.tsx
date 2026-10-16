"use client";

import Link from "next/link";
import { BrandMark } from "./Brand";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/></>,
    shield: <><path d="M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7z"/><path d="m8 12 3 3 5-6"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    activity: <path d="M2 12h5l3-8 4 16 3-8h5"/>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/></>,
    alert: <><path d="m12 3 10 18H2z"/><path d="M12 9v5m0 3v.1"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] ?? paths.file}</svg>;
}

const navigation = [
  { href: "/dashboard", label: "Overview", icon: "grid", caption: "Your portfolio at a glance" },
  { href: "/decisions", label: "Decisions", icon: "file", caption: "Every decision, in one place" },
  { href: "/investigator", label: "Review queue", icon: "shield", caption: "Cases that need a closer look" },
  { href: "/new-claim", label: "New claim", icon: "plus", caption: "From intake to informed action" },
];

export default function Workspace({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/") return <>{children}</>;
  const current = navigation.find(item => pathname.startsWith(item.href)) ?? navigation[0];
  return <div className="workspace">
    <a className="skip-link" href="#content">Skip to content</a>
    <aside className="sidebar">
      <Link href="/" className="brand" aria-label="Trinetra home"><BrandMark className="brand-symbol"/><span className="brand-wordmark">TRINETRA<small>CLAIMS INTELLIGENCE</small></span></Link>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="primary-nav" aria-label="Main navigation">{navigation.map(item => <Link key={item.href} href={item.href} aria-label={item.label} title={item.label} aria-current={pathname.startsWith(item.href) ? "page" : undefined} className={pathname.startsWith(item.href) ? "nav-item active" : "nav-item"}><Icon name={item.icon}/><span>{item.label}</span>{pathname.startsWith(item.href) && <span className="nav-active-dot"/>}</Link>)}</nav>
      <div className="sidebar-note"><span className="eyebrow">A CLEARER PICTURE</span><h3>Clarity before action.</h3><p>An informed perspective on every claim.</p><Link href="/new-claim">Evaluate a claim <Icon name="arrow" size={16}/></Link></div>
      <div className="sidebar-footer"><span className="avatar"><BrandMark/></span><div><strong>Claims workspace</strong><small>Trinetra · Prototype</small></div></div>
    </aside>
    <div className="workspace-body"><header className="topbar"><div><span className="topbar-parent">Workspace</span><span className="breadcrumb-divider">/</span><strong>{current.label}</strong></div><span className="topbar-caption">{current.caption}</span></header><main id="content" className="page-content">{children}</main><footer className="workspace-footer"><span>Trinetra <span className="muted">/</span> Claims intelligence</span><span>Built for informed decisions.</span></footer></div>
  </div>;
}

export function PageHeader({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: ReactNode }) {
  return <header className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line"/>{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{children && <div className="page-actions">{children}</div>}</header>;
}

export function StatusBadge({ action }: { action?: string }) {
  const labels: Record<string, string> = { AUTO_APPROVE: "Auto-approved", ROUTE_TO_REVIEW: "Needs review", BLOCK: "Blocked" };
  return <span className={`status-badge ${action === "AUTO_APPROVE" ? "success" : action === "BLOCK" ? "danger" : "warning"}`}><span/>{labels[action ?? ""] ?? action ?? "Unknown"}</span>;
}

export function EmptyState({ title, description, icon = "file", children }: { title: string; description: string; icon?: string; children?: ReactNode }) {
  return <div className="empty-state"><span className="empty-icon"><Icon name={icon} size={26}/></span><h3>{title}</h3><p>{description}</p>{children}</div>;
}

export function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) {
  return <div role="alert" className="error-notice"><Icon name="alert"/><div><strong>We couldn’t load this information.</strong><p>{message}</p></div>{retry && <button className="button secondary small" onClick={retry}>Try again</button>}</div>;
}

export function formatDate(value?: string) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
