import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "@/app/providers";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Thesys",
  description: "Stateful strategic intelligence workspace for ambiguous work.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
