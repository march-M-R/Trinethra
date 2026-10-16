import Image from "next/image";

/** Display the background-removed Trinetra artwork. */
export function BrandMark({ className = "", decorative = true }: { className?: string; decorative?: boolean }) {
  return (
    <span className={`brand-image ${className}`} aria-hidden={decorative || undefined}>
      <Image src="/brand/trinetra-transparent.png" alt={decorative ? "" : "Trinetra — The third eye of claim automation"} fill sizes="(max-width: 760px) 250px, 350px" priority/>
    </span>
  );
}
