/**
 * Pure sentiment-description logic, extracted from ArticleCard so it is
 * unit-testable and free of Svelte concerns.
 *
 * The richer description consumes more of what the NLP pipeline computes than a
 * label + |score| bucket can:
 *  - `magnitude` (GCP NL "emotional intensity", 0..∞) disambiguates a
 *    near-zero score: high magnitude = mixed / polarizing (strong feeling both
 *    ways), low magnitude = factual / unemotional. A score alone can't tell
 *    these apart.
 *  - `topEntities` (already salience-sorted) names what the coverage centres on.
 *
 * `magnitude` is null for VADER-only articles; every branch degrades gracefully
 * to the score-only description when it's absent.
 */

export type SentimentInput = {
  label?: string | null;
  score?: number | null; // -1..1
  magnitude?: number | null; // 0..∞ (GCP NL); null when unavailable
  topEntities?: string[]; // already salience-sorted names
};

// Calibrated from the production corpus (2026-06-09) — `magnitude` is unbounded
// and grows with document length, so the low/high cut-points are the 33rd/66th
// percentiles of OUR data, not guessed values:
//
//   SELECT percentile_cont(0.33) WITHIN GROUP (ORDER BY magnitude),  -- 7.8
//          percentile_cont(0.66) WITHIN GROUP (ORDER BY magnitude)   -- 15.4
//   FROM sentiment_analyses WHERE magnitude IS NOT NULL;  -- n=8786, min 0.2 max 196.1
//
// Re-run and adjust if the corpus shifts substantially.
const MAG_LOW = 7.8;
const MAG_HIGH = 15.4;

const cap = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1);

export function describeSentiment({
  label,
  score,
  magnitude,
  topEntities = [],
}: SentimentInput): string {
  if (!label || score === null || score === undefined) return "";
  const l = label.toLowerCase();
  const abs = Math.abs(score);
  const intensity = abs > 0.6 ? "strongly" : abs > 0.25 ? "moderately" : "slightly";

  if (l === "neutral") {
    if (magnitude != null && magnitude >= MAG_HIGH)
      return "Mixed tone — strong feeling on both sides, not truly neutral";
    if (magnitude != null && magnitude < MAG_LOW)
      return "Largely factual, with little emotional language";
    return "Balanced, neutral tone";
  }

  const dir = l === "positive" ? "positive" : "negative";
  const focus = topEntities.length
    ? `, centred on ${topEntities.slice(0, 2).join(" and ")}`
    : "";
  let out = `${cap(intensity)} ${dir} (${score.toFixed(2)})${focus}`;
  if (magnitude != null && magnitude >= MAG_HIGH) out += " — emotionally charged";
  return out;
}

/**
 * A coarse three-bucket label for the magnitude meter in the detail panel.
 * Returns null when magnitude is unavailable (VADER-only) so the UI can hide
 * the meter rather than show a misleading "low".
 */
export function magnitudeTier(
  magnitude?: number | null,
): "low" | "medium" | "high" | null {
  if (magnitude == null) return null;
  if (magnitude >= MAG_HIGH) return "high";
  if (magnitude < MAG_LOW) return "low";
  return "medium";
}
