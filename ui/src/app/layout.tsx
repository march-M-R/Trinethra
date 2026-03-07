import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "Trinetra Dashboard",
  description: "Insurance risk decisioning + monitoring",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="border-b">
            <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
              <div className="font-bold text-lg">Trinetra</div>
              <nav className="flex gap-4 text-sm">
                <Link className="hover:underline" href="/dashboard">
                  Dashboard
                </Link>
                <Link className="hover:underline" href="/decisions">
                  Decisions
                </Link>
              </nav>
            </div>
          </header>

          <main className="max-w-6xl mx-auto px-6 py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}