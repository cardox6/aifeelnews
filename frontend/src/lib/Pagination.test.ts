import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/svelte";
import Pagination from "./Pagination.svelte";

// A focused component test: proves Svelte render harness works end-to-end
// and pins the component's derived logic (page number, prev/next enablement),
// which is the only real logic Pagination owns.
describe("Pagination", () => {
  const prev = () => screen.getByRole("button", { name: "Previous page" });
  const next = () => screen.getByRole("button", { name: "Next page" });

  it("shows page 1 and disables Prev at the start of the feed", () => {
    render(Pagination, { current: 0, pageSize: 20, hasMore: true });
    expect(screen.getByText("Page 1")).toBeInTheDocument();
    expect(prev()).toBeDisabled();
    expect(next()).toBeEnabled();
  });

  it("computes the page number from skip/pageSize", () => {
    render(Pagination, { current: 40, pageSize: 20, hasMore: true });
    expect(screen.getByText("Page 3")).toBeInTheDocument();
    expect(prev()).toBeEnabled();
    expect(next()).toBeEnabled();
  });

  it("disables Next when there are no more results", () => {
    render(Pagination, { current: 40, pageSize: 20, hasMore: false });
    expect(next()).toBeDisabled();
    expect(prev()).toBeEnabled();
  });

  it("uses pageSize as the divisor (page 2 at one full page in)", () => {
    render(Pagination, { current: 10, pageSize: 10, hasMore: false });
    expect(screen.getByText("Page 2")).toBeInTheDocument();
  });
});
