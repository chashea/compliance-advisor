import { useState } from "react";

interface Column<T> {
  key: keyof T & string;
  label: string;
  render?: (val: T[keyof T], row: T) => React.ReactNode;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  keyField: keyof T & string;
}

export default function DataTable<T extends Record<string, unknown>>({ columns, data, keyField }: Props<T>) {
  const [sortKey, setSortKey] = useState<string>(columns[0]?.key ?? "");
  const [sortAsc, setSortAsc] = useState(true);
  const [filters, setFilters] = useState<Record<string, string>>({});

  const filtered = data.filter((row) =>
    Object.entries(filters).every(([key, val]) => {
      if (!val) return true;
      return String(row[key] ?? "").toLowerCase().includes(val.toLowerCase());
    }),
  );

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av == null) return 1;
    if (bv == null) return -1;
    const cmp = typeof av === "number" ? av - (bv as number) : String(av).localeCompare(String(bv));
    return sortAsc ? cmp : -cmp;
  });

  function toggleSort(key: string) {
    if (sortKey === key) setSortAsc(!sortAsc);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500">
          <tr className="border-b border-slate-200">
            {columns.map((c) => (
              <th
                key={c.key}
                className="cursor-pointer px-4 py-3 hover:text-slate-700"
                onClick={() => toggleSort(c.key)}
              >
                {c.label} {sortKey === c.key ? (sortAsc ? "\u25B2" : "\u25BC") : ""}
              </th>
            ))}
          </tr>
          <tr className="border-b border-slate-200">
            {columns.map((c) => (
              <th key={`filter-${c.key}`} className="px-4 py-1.5">
                <input
                  type="text"
                  placeholder="Filter..."
                  value={filters[c.key] ?? ""}
                  onChange={(e) => setFilters((f) => ({ ...f, [c.key]: e.target.value }))}
                  className="w-full rounded border border-slate-200 px-2 py-1 text-xs font-normal normal-case text-slate-700 placeholder:text-slate-300 focus:border-blue-400 focus:outline-none"
                />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((row) => (
            <tr key={String(row[keyField])} className="hover:bg-slate-50">
              {columns.map((c) => (
                <td key={c.key} className="px-4 py-2.5 text-slate-700">
                  {c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-slate-400">
                No data
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
