import styles from "./SkillGapSummary.module.css";

const PRIORITY_STYLE = {
  high: styles.high,
  medium: styles.medium,
  low: styles.low,
};

const PRIORITY_LABEL = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export default function SkillGapSummary({ skillGaps }) {
  if (!skillGaps?.length) return null;

  const grouped = { high: [], medium: [], low: [] };
  for (const gap of skillGaps) {
    const p = gap.priority || "medium";
    (grouped[p] || grouped.medium).push(gap);
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.title}>Identified Skill Gaps</h2>
      <p className={styles.subtitle}>
        {skillGaps.length} gap{skillGaps.length !== 1 ? "s" : ""} found — your personalized learning path covers all of them.
      </p>

      {["high", "medium", "low"].map(
        (priority) =>
          grouped[priority].length > 0 && (
            <div key={priority} className={styles.group}>
              <span className={`${styles.priorityLabel} ${PRIORITY_STYLE[priority]}`}>
                {PRIORITY_LABEL[priority]} Priority
              </span>
              <div className={styles.chips}>
                {grouped[priority].map((gap) => (
                  <span key={gap.skill} className={`${styles.chip} ${PRIORITY_STYLE[priority]}`}>
                    {gap.skill}
                    {gap.category && (
                      <span className={styles.category}>{gap.category}</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )
      )}
    </section>
  );
}
