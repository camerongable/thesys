import type { AnchorHTMLAttributes, ReactNode } from "react";

import { safeExternalUrl } from "@/lib/safe-external-url";

type SafeExternalLinkProps = Omit<
  AnchorHTMLAttributes<HTMLAnchorElement>,
  "href" | "rel" | "target"
> & {
  children: ReactNode;
  href: string | null | undefined;
};

export function SafeExternalLink({ children, href, ...props }: SafeExternalLinkProps) {
  const destination = safeExternalUrl(href);
  if (!destination) {
    return <span className={props.className}>{children}</span>;
  }
  return (
    <a {...props} href={destination} rel="noopener noreferrer" target="_blank">
      {children}
    </a>
  );
}
