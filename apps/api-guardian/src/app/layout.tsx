import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "API Guardian",
  description: "Autonomous reliability for third-party API integrations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
