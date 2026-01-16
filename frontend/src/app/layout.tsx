import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";

const inter = Inter({
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Captain's Log",
  description: "Personal Activity Tracking Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.className} bg-slate-950 text-white antialiased`} suppressHydrationWarning>
        <Sidebar />
        <main className="pl-64 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
