import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "../test/render";
import DataTable from "./DataTable";

interface TestRow extends Record<string, unknown> {
  id: string;
  name: string;
  count: number;
  status: string;
}

const columns = [
  { key: "name" as const, label: "Name" },
  { key: "count" as const, label: "Count" },
  { key: "status" as const, label: "Status" },
];

const data: TestRow[] = [
  { id: "1", name: "Alpha", count: 10, status: "Active" },
  { id: "2", name: "Beta", count: 5, status: "Closed" },
  { id: "3", name: "Charlie", count: 20, status: "Active" },
];

function getBodyRows() {
  const tbody = screen.getAllByRole("rowgroup")[1]; // tbody
  return within(tbody).getAllByRole("row");
}

function getCellTexts(colIndex: number) {
  return getBodyRows().map((row) => within(row).getAllByRole("cell")[colIndex].textContent);
}

describe("DataTable", () => {
  it("renders all rows", () => {
    render(<DataTable columns={columns} data={data} keyField="id" />);
    const rows = getBodyRows();
    expect(rows).toHaveLength(3);
  });

  it("sorts ascending by first column by default", () => {
    render(<DataTable columns={columns} data={data} keyField="id" />);
    expect(getCellTexts(0)).toEqual(["Alpha", "Beta", "Charlie"]);
  });

  it("toggles sort direction on header click", () => {
    render(<DataTable columns={columns} data={data} keyField="id" />);
    const nameHeader = screen.getByText(/^Name/);
    fireEvent.click(nameHeader); // now desc
    expect(getCellTexts(0)).toEqual(["Charlie", "Beta", "Alpha"]);
  });

  it("sorts by a different column when clicked", () => {
    render(<DataTable columns={columns} data={data} keyField="id" />);
    const countHeader = screen.getByText(/^Count/);
    fireEvent.click(countHeader);
    expect(getCellTexts(1)).toEqual(["5", "10", "20"]);
  });

  it("filters rows when a filter is selected", () => {
    render(<DataTable columns={columns} data={data} keyField="id" />);
    const selects = screen.getAllByRole("combobox");
    const statusSelect = selects[2];
    fireEvent.change(statusSelect, { target: { value: "Closed" } });
    const rows = getBodyRows();
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getAllByRole("cell")[0].textContent).toBe("Beta");
  });

  it("shows 'No data' when all rows are filtered out", () => {
    render(<DataTable columns={columns} data={[]} keyField="id" />);
    expect(screen.getByText("No data")).toBeInTheDocument();
  });

  it("calls onRowClick when a row is clicked", () => {
    const onClick = vi.fn();
    render(<DataTable columns={columns} data={data} keyField="id" onRowClick={onClick} />);
    const rows = getBodyRows();
    fireEvent.click(within(rows[0]).getAllByRole("cell")[0]);
    expect(onClick).toHaveBeenCalledWith(data[0]);
  });

  it("renders custom render functions", () => {
    const customColumns = [
      { key: "name" as const, label: "Name", render: (val: unknown) => `Custom: ${val}` },
    ];
    render(<DataTable columns={customColumns} data={data} keyField="id" />);
    const tbody = screen.getAllByRole("rowgroup")[1];
    expect(within(tbody).getByText("Custom: Alpha")).toBeInTheDocument();
  });
});
