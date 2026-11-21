import { useEffect, type RefObject } from "react";

/** Copies each column header onto its cells as `data-label`, for every `table.grid`
 * inside `root`. On phones the CSS shows each row as a card and uses that attribute to
 * label every value ("Student: Daniela Torres"), so no page has to change its markup.
 * Tables render after their data loads, so the labels are refreshed on DOM changes. */
export function useTableLabels(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const element = root.current;
    if (!element) return;

    let frame = 0;
    const label = () => {
      frame = 0;
      element.querySelectorAll<HTMLTableElement>("table.grid").forEach((table) => {
        const headers = Array.from(table.querySelectorAll("thead th"), (th) => th.textContent?.trim() ?? "");
        table.querySelectorAll("tbody tr").forEach((row) => {
          let column = 0;
          Array.from(row.children).forEach((cell) => {
            const text = headers[column] ?? "";
            if (cell.getAttribute("data-label") !== text) cell.setAttribute("data-label", text);
            column += (cell as HTMLTableCellElement).colSpan || 1;
          });
        });
      });
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(label);
    };

    label();
    // Only structure and text are observed, so setting data-label does not loop.
    const observer = new MutationObserver(schedule);
    observer.observe(element, { childList: true, subtree: true, characterData: true });
    return () => {
      observer.disconnect();
      if (frame) cancelAnimationFrame(frame);
    };
  }, [root]);
}
