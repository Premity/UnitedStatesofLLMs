import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QuestionForm } from "@/components/layout/QuestionForm";
import type { PublicCase } from "@/types";

/**
 * The prepared-case picker fills the question and facts, and is absent when
 * the API offers nothing — the form must still work then.
 */

const CASES: PublicCase[] = [
  {
    id: "icty_galic_terror",
    title: "Prosecutor v. Galić",
    court: "ICTY",
    year: 2003,
    question: "Were the attacks on civilians lawful?",
    facts: "Shells struck a market.",
    difficulty: "medium",
  },
  {
    id: "icc_bemba_command",
    title: "Prosecutor v. Bemba",
    court: "ICC",
    year: 2016,
    question: "Did the commander fail to prevent the crimes?",
    facts: "Troops acted in another country.",
    difficulty: "contested",
  },
];

function mockCases(body: unknown, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({ ok, json: async () => body });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("case picker", () => {
  it("fills the question and facts from the chosen case", async () => {
    mockCases(CASES);
    render(<QuestionForm />);

    const picker = await screen.findByTestId("case-picker");
    await userEvent.selectOptions(picker, "icc_bemba_command");

    expect(screen.getByPlaceholderText(/Article 8/)).toHaveValue(CASES[1].question);
    expect(screen.getByPlaceholderText(/factual predicate/)).toHaveValue(CASES[1].facts);
  });

  it("leaves the boxes editable after a case is chosen", async () => {
    mockCases(CASES);
    render(<QuestionForm />);

    await userEvent.selectOptions(await screen.findByTestId("case-picker"), "icty_galic_terror");
    const question = screen.getByPlaceholderText(/Article 8/);
    await userEvent.type(question, " Explain.");

    expect(question).toHaveValue(`${CASES[0].question} Explain.`);
  });

  it("offers every case plus a way back to typing your own", async () => {
    mockCases(CASES);
    render(<QuestionForm />);

    const picker = await screen.findByTestId("case-picker");

    expect(Array.from(picker.querySelectorAll("option")).map((o) => o.textContent)).toEqual([
      "Write your own",
      "Prosecutor v. Galić (ICTY, 2003)",
      "Prosecutor v. Bemba (ICC, 2016)",
    ]);
  });

  it("shows no picker when the API has no cases", async () => {
    const fetchMock = mockCases([]);
    render(<QuestionForm />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/cases"));
    expect(screen.queryByTestId("case-picker")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Article 8/)).toBeInTheDocument();
  });

  it("shows no picker, and no crash, when the request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    render(<QuestionForm />);

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    expect(screen.queryByTestId("case-picker")).not.toBeInTheDocument();
  });

  it("never asks for, or renders, ground truth", async () => {
    // A server that wrongly sent the holding would still not show it: the
    // picker only reads question and facts.
    mockCases([{ ...CASES[0], holding: "SENTINEL-HOLDING", outcome: "affirmed" }]);
    const { container } = render(<QuestionForm />);

    await userEvent.selectOptions(await screen.findByTestId("case-picker"), "icty_galic_terror");

    expect(container.textContent).not.toContain("SENTINEL-HOLDING");
    expect(container.innerHTML).not.toContain("affirmed");
  });
});
