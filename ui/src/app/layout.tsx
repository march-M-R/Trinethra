import "./globals.css";
import Workspace from "@/components/Workspace";

export const metadata = {
  title: "Trinetra · Claims Intelligence",
  icons: { icon: "/brand/trinetra-transparent.png", apple: "/brand/trinetra-transparent.png" },
  description: "A clearer view of insurance claims, risk, and review decisions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><Workspace>{children}</Workspace></body></html>;
}
