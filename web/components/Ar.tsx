import { Fragment } from "react";

// Latin runs (optionally in parentheses) inside Arabic text are isolated so that the bidi algorithm
// keeps brackets and word order intact, e.g. "الردع بالمنع (deterrence by denial)".
const LATIN_RUN = /([A-Za-z][A-Za-z0-9 .,'’&/\-]*[A-Za-z0-9.](?: \([A-Za-z0-9 .\-]+\))?|[A-Za-z])/g;

export function Ar({ text }: { text: string }) {
  const parts = text.split(LATIN_RUN);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1
          // Short glosses never wrap: a term split across lines scrambles its brackets in RTL text.
          ? <bdi key={i} dir="ltr" lang="en" style={part.length <= 40 ? { whiteSpace: "nowrap" } : undefined}>{part}</bdi>
          : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}
