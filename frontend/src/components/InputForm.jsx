import { useState, useEffect } from "react";
import styles from "./InputForm.module.css";
import { getResumes } from "../api/client";
import ResumeDropzone from "./ResumeDropzone";

export default function InputForm({ onSubmit, disabled }) {
  const [resume, setResume] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [savedResumes, setSavedResumes] = useState([]);

  useEffect(() => {
    getResumes()
      .then((data) => setSavedResumes(data.resumes || []))
      .catch(() => {});
  }, []);

  function handleResumeSelect(e) {
    const id = parseInt(e.target.value, 10);
    if (!id) return;
    const found = savedResumes.find((r) => r.analysis_id === id);
    if (found) setResume(found.full_text);
    e.target.value = "";
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!resume.trim() || !jobDesc.trim()) return;
    onSubmit(resume, jobDesc);
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.inputGroup}>
        <div className={styles.labelRow}>
          <label className={styles.label} htmlFor="resume">
            Your Resume
            <span className={styles.hint}>Paste the full text of your resume</span>
          </label>
          <select
            className={styles.dropdown}
            defaultValue=""
            onChange={handleResumeSelect}
            disabled={disabled || savedResumes.length === 0}
            title={savedResumes.length === 0 ? "No saved resumes yet" : "Load a previously used resume"}
          >
            <option value="" disabled>
              {savedResumes.length === 0 ? "No saved resumes yet" : "Load previous resume…"}
            </option>
            {savedResumes.map((r) => (
              <option key={r.analysis_id} value={r.analysis_id}>
                {r.snippet || `Resume #${r.analysis_id}`}
              </option>
            ))}
          </select>
        </div>
        <ResumeDropzone onTextExtracted={setResume} disabled={disabled} />
        <textarea
          id="resume"
          className={styles.textarea}
          placeholder="Paste your resume here, or drop a file above…"
          value={resume}
          onChange={(e) => setResume(e.target.value)}
          rows={10}
          disabled={disabled}
          required
        />
      </div>

      <div className={styles.inputGroup}>
        <label className={styles.label} htmlFor="jobDesc">
          Job Description
          <span className={styles.hint}>Paste the job posting or describe the target role</span>
        </label>
        <textarea
          id="jobDesc"
          className={styles.textarea}
          placeholder="Paste the job description here..."
          value={jobDesc}
          onChange={(e) => setJobDesc(e.target.value)}
          rows={12}
          disabled={disabled}
          required
        />
      </div>

      <button
        type="submit"
        className={styles.button}
        disabled={disabled || !resume.trim() || !jobDesc.trim()}
      >
        Analyze Skill Gaps &amp; Build Learning Path
      </button>
    </form>
  );
}
