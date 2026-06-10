import { describe, it, expect } from "vitest";
import { describeSentiment, magnitudeTier } from "./sentiment";

// The magnitude cut-points are calibrated production percentiles (33rd = 7.8,
// 66th = 15.4). The tests pin the boundary behaviour so a future re-calibration
// is a deliberate, visible change rather than a silent drift.
const MAG_LOW = 7.8;
const MAG_HIGH = 15.4;

describe("describeSentiment", () => {
  describe("missing / unanalyzed input degrades to empty string", () => {
    it("returns '' when label is absent", () => {
      expect(describeSentiment({ score: 0.5 })).toBe("");
    });

    it("returns '' when score is null", () => {
      expect(describeSentiment({ label: "positive", score: null })).toBe("");
    });

    it("returns '' when score is undefined", () => {
      expect(describeSentiment({ label: "positive" })).toBe("");
    });

    it("treats score 0 as present (not missing)", () => {
      // 0 is a valid neutral score and must NOT be coerced to "no data".
      expect(describeSentiment({ label: "neutral", score: 0 })).toBe(
        "Balanced, neutral tone",
      );
    });
  });

  describe("neutral label uses magnitude to disambiguate", () => {
    it("high magnitude → mixed/polarizing, not truly neutral", () => {
      expect(
        describeSentiment({ label: "neutral", score: 0, magnitude: MAG_HIGH }),
      ).toBe("Mixed tone — strong feeling on both sides, not truly neutral");
    });

    it("low magnitude → largely factual", () => {
      expect(
        describeSentiment({ label: "neutral", score: 0, magnitude: 1.0 }),
      ).toBe("Largely factual, with little emotional language");
    });

    it("mid magnitude → balanced", () => {
      expect(
        describeSentiment({ label: "neutral", score: 0, magnitude: 10 }),
      ).toBe("Balanced, neutral tone");
    });

    it("null magnitude (VADER) → balanced, no crash", () => {
      expect(
        describeSentiment({ label: "neutral", score: 0, magnitude: null }),
      ).toBe("Balanced, neutral tone");
    });

    it("MAG_LOW is inclusive of medium (not 'factual') at the boundary", () => {
      // branch is `magnitude < MAG_LOW` → exactly MAG_LOW is medium → balanced
      expect(
        describeSentiment({ label: "neutral", score: 0, magnitude: MAG_LOW }),
      ).toBe("Balanced, neutral tone");
    });
  });

  describe("intensity buckets (|score|)", () => {
    it("|score| > 0.6 → strongly", () => {
      expect(describeSentiment({ label: "positive", score: 0.8 })).toBe(
        "Strongly positive (0.80)",
      );
    });

    it("|score| == 0.6 → moderately (boundary is exclusive)", () => {
      expect(describeSentiment({ label: "positive", score: 0.6 })).toBe(
        "Moderately positive (0.60)",
      );
    });

    it("0.25 < |score| <= 0.6 → moderately", () => {
      expect(describeSentiment({ label: "negative", score: -0.4 })).toBe(
        "Moderately negative (-0.40)",
      );
    });

    it("|score| == 0.25 → slightly (boundary is exclusive)", () => {
      expect(describeSentiment({ label: "positive", score: 0.25 })).toBe(
        "Slightly positive (0.25)",
      );
    });

    it("|score| < 0.25 → slightly", () => {
      expect(describeSentiment({ label: "negative", score: -0.1 })).toBe(
        "Slightly negative (-0.10)",
      );
    });
  });

  describe("direction, formatting, entities and emotional-charge suffix", () => {
    it("label is case-insensitive", () => {
      expect(describeSentiment({ label: "POSITIVE", score: 0.8 })).toBe(
        "Strongly positive (0.80)",
      );
    });

    it("score is always rendered to 2 decimals", () => {
      expect(describeSentiment({ label: "positive", score: 0.5 })).toContain(
        "(0.50)",
      );
    });

    it("appends the top two entities, salience-ordered", () => {
      expect(
        describeSentiment({
          label: "negative",
          score: -0.5,
          topEntities: ["Ukraine", "NATO"],
        }),
      ).toBe("Moderately negative (-0.50), centred on Ukraine and NATO");
    });

    it("caps the entity focus at two even when more are supplied", () => {
      const out = describeSentiment({
        label: "positive",
        score: 0.7,
        topEntities: ["A", "B", "C", "D"],
      });
      expect(out).toContain("centred on A and B");
      expect(out).not.toContain("C");
    });

    it("omits the focus clause when no entities are present", () => {
      expect(describeSentiment({ label: "positive", score: 0.7 })).not.toContain(
        "centred on",
      );
    });

    it("appends '— emotionally charged' when magnitude is high", () => {
      expect(
        describeSentiment({
          label: "positive",
          score: 0.7,
          magnitude: MAG_HIGH,
        }),
      ).toBe("Strongly positive (0.70) — emotionally charged");
    });

    it("does NOT append the charge suffix when magnitude is null (VADER)", () => {
      expect(
        describeSentiment({ label: "positive", score: 0.7, magnitude: null }),
      ).not.toContain("emotionally charged");
    });

    it("combines entity focus and the charge suffix", () => {
      expect(
        describeSentiment({
          label: "negative",
          score: -0.9,
          magnitude: 30,
          topEntities: ["Gaza"],
        }),
      ).toBe("Strongly negative (-0.90), centred on Gaza — emotionally charged");
    });
  });
});

describe("magnitudeTier", () => {
  it("returns null when magnitude is unavailable (VADER-only)", () => {
    expect(magnitudeTier(null)).toBeNull();
    expect(magnitudeTier(undefined)).toBeNull();
  });

  it("classifies high (>= MAG_HIGH, inclusive)", () => {
    expect(magnitudeTier(MAG_HIGH)).toBe("high");
    expect(magnitudeTier(196.1)).toBe("high");
  });

  it("classifies low (< MAG_LOW, exclusive)", () => {
    expect(magnitudeTier(0)).toBe("low");
    expect(magnitudeTier(7.79)).toBe("low");
  });

  it("classifies medium in between (MAG_LOW inclusive, MAG_HIGH exclusive)", () => {
    expect(magnitudeTier(MAG_LOW)).toBe("medium");
    expect(magnitudeTier(10)).toBe("medium");
    expect(magnitudeTier(15.39)).toBe("medium");
  });
});
