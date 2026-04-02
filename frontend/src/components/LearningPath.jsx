import ResourceCard from "./ResourceCard";
import styles from "./LearningPath.module.css";

const LEVELS = ["beginner", "intermediate", "advanced"];
const LEVEL_LABELS = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

export default function LearningPath({ learningPath }) {
  if (!learningPath?.length) return null;

  // Group by level
  const grouped = { beginner: [], intermediate: [], advanced: [] };
  for (const r of learningPath) {
    const lvl = r.level || "intermediate";
    (grouped[lvl] || grouped.intermediate).push(r);
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.title}>Your Personalized Learning Path</h2>
      <p className={styles.subtitle}>
        {learningPath.length} resource{learningPath.length !== 1 ? "s" : ""} curated and ranked for you, organized from foundational to advanced.
      </p>

      {LEVELS.map((level) =>
        grouped[level].length > 0 ? (
          <div key={level} className={styles.tier}>
            <div className={`${styles.tierHeader} ${styles[level]}`}>
              <span className={styles.tierLabel}>{LEVEL_LABELS[level]}</span>
              <span className={styles.tierCount}>
                {grouped[level].length} resource{grouped[level].length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className={styles.cards}>
              {grouped[level].map((r, i) => (
                <ResourceCard key={`${r.source}-${r.url}-${i}`} resource={r} index={r.rank - 1} />
              ))}
            </div>
          </div>
        ) : null
      )}
    </section>
  );
}
