import styles from "./ResourceCard.module.css";

const LEVEL_STYLE = {
  beginner: styles.beginner,
  intermediate: styles.intermediate,
  advanced: styles.advanced,
};

const SOURCE_STYLE = {
  YouTube: styles.youtube,
  "OER Commons": styles.oer,
};

export default function ResourceCard({ resource, index }) {
  const level = resource.level || "intermediate";
  const source = resource.source || "Unknown";

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.rank}>#{index + 1}</span>
        <div className={styles.badges}>
          <span className={`${styles.badge} ${LEVEL_STYLE[level] || styles.intermediate}`}>
            {level.charAt(0).toUpperCase() + level.slice(1)}
          </span>
          <span className={`${styles.badge} ${SOURCE_STYLE[source] || styles.oer}`}>
            {source}
          </span>
        </div>
      </div>

      <a
        href={resource.url}
        target="_blank"
        rel="noopener noreferrer"
        className={styles.title}
      >
        {resource.title}
      </a>

      {resource.skill_addressed && (
        <p className={styles.skill}>
          Addresses: <strong>{resource.skill_addressed}</strong>
        </p>
      )}

      {resource.justification && (
        <p className={styles.justification}>{resource.justification}</p>
      )}

      <div className={styles.footer}>
        {resource.score != null && (
          <span className={styles.score}>
            Match quality:{" "}
            {resource.score >= 0.75 ? "High" : resource.score >= 0.60 ? "Medium" : "Low"}
          </span>
        )}
        <a
          href={resource.url}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.link}
        >
          Open resource →
        </a>
      </div>
    </div>
  );
}
