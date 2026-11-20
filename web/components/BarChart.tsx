import Link from "next/link";

export type Bar = { key: string; label: string; value: number; previous?: number; href?: string };

/** Single-series horizontal bars: one hue, a direct value label per bar, a hover/focus tooltip, a table view. */
export function BarChart({ title, bars, max, unit = "مادة", previousLabel = "الشهر السابق" }:
  { title: string; bars: Bar[]; max?: number; unit?: string; previousLabel?: string }) {
  const top = Math.max(1, max ?? Math.max(...bars.map((b) => b.value), 0));
  if (!bars.length) return null;
  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <ul className="bars">
        {bars.map((b) => {
          const tip = `${b.label}: ${b.value} ${unit}${b.previous !== undefined ? `، ${previousLabel}: ${b.previous}` : ""}`;
          const name = b.href ? <Link href={b.href}>{b.label}</Link> : b.label;
          return (
            <li key={b.key} className="bar-row" tabIndex={0} data-tip={tip} aria-label={tip}>
              <span className="bar-label">{name}</span>
              <span className="bar-track">
                <span className="bar" style={{ width: `${(b.value / top) * 100}%` }} />
                <span className="bar-value">{b.value}</span>
              </span>
            </li>
          );
        })}
      </ul>
      <details className="chart-table">
        <summary className="ui">عرض الأرقام جدولاً</summary>
        <table className="glossary-table">
          <thead><tr><th scope="col">البند</th><th scope="col">العدد</th>{bars.some((b) => b.previous !== undefined) && <th scope="col">{previousLabel}</th>}</tr></thead>
          <tbody>{bars.map((b) => <tr key={b.key}><td>{b.label}</td><td>{b.value}</td>{b.previous !== undefined && <td>{b.previous}</td>}</tr>)}</tbody>
        </table>
      </details>
    </figure>
  );
}
