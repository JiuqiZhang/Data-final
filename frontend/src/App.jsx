import { useState } from "react";
import InputForm from "./components/InputForm";
import LoadingState from "./components/LoadingState";
import SkillGapSummary from "./components/SkillGapSummary";
import LearningPath from "./components/LearningPath";
import { useAnalysis } from "./hooks/useAnalysis";
import styles from "./App.module.css";

export default function App() {
  const { state, result, error, loadingMessage, run, reset } = useAnalysis();
  const [showHistory, setShowHistory] = useState(false);

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div>
            <h1 className={styles.title}>E-Learning Skill Architect</h1>
            <p className={styles.tagline}>
              Paste your resume + job description → get a personalized, ranked learning path.
            </p>
          </div>
          {state === "success" && (
            <button className={styles.resetBtn} onClick={reset}>
              New Analysis
            </button>
          )}
        </div>
      </header>

      <main className={styles.main}>
        {state === "idle" && (
          <InputForm onSubmit={run} disabled={false} />
        )}

        {state === "loading" && (
          <LoadingState message={loadingMessage} />
        )}

        {state === "error" && (
          <div className={styles.errorBox}>
            <p className={styles.errorTitle}>Something went wrong</p>
            <p className={styles.errorMsg}>{error}</p>
            <button className={styles.retryBtn} onClick={reset}>
              Try Again
            </button>
          </div>
        )}

        {state === "success" && result && (
          <div className={styles.results}>
            <div className={styles.meta}>
              <span className={styles.metaItem}>
                Analysis #{result.analysis_id}
              </span>
              <span className={styles.metaDot}>·</span>
              <span className={styles.metaItem}>
                {new Date(result.created_at).toLocaleString()}
              </span>
            </div>
            <SkillGapSummary skillGaps={result.skill_gaps} />
            <LearningPath learningPath={result.learning_path} />
          </div>
        )}
      </main>

      <footer className={styles.footer}>
        <p>E-Learning Skill Architect · Data Mining Final Project · Shuhua Fang &amp; Jiuqi Zhang</p>
      </footer>
    </div>
  );
}
