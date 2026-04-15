import React from "react";

interface Column<T> {
  key: keyof T | string;
  header: string;
  align?: "left" | "right" | "center";
  render?: (row: T, i: number) => React.ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  onDelete?: (i: number) => void;
}

function DataTable<T extends Record<string, any>>(
  { columns, rows, onDelete }: DataTableProps<T>,
) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-gray-400 border-b border-gray-800">
          {columns.map((c) => (
            <th key={String(c.key)}
                className={"px-2 py-1 font-medium text-" + (c.align || "left")}>
              {c.header}
            </th>
          ))}
          {onDelete && <th className="w-6" />}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-gray-900 hover:bg-gray-900/40">
            {columns.map((c) => (
              <td key={String(c.key)}
                  className={"px-2 py-1 text-" + (c.align || "left")}>
                {c.render
                  ? c.render(row, i)
                  : String(row[c.key as keyof T] ?? "")}
              </td>
            ))}
            {onDelete && (
              <td>
                <button
                  onClick={() => onDelete(i)}
                  className="text-op3-danger hover:text-red-400 text-xs"
                >×</button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default DataTable;
