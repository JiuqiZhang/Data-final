import { useState, useRef } from "react";
import { parseResumeFile } from "../api/client";
import styles from "./ResumeDropzone.module.css";

export default function ResumeDropzone({ onTextExtracted, disabled }) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | parsing | error
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef(null);

  async function handleFile(file) {
    if (!file) return;
    const name = file.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".docx") && !name.endsWith(".doc")) {
      setErrorMsg("Only PDF and DOCX files are supported.");
      setStatus("error");
      return;
    }
    setStatus("parsing");
    setErrorMsg("");
    try {
      const { text } = await parseResumeFile(file);
      onTextExtracted(text);
      setStatus("idle");
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || "Failed to parse file.");
      setStatus("error");
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    handleFile(file);
  }

  function onDragOver(e) {
    e.preventDefault();
    setDragging(true);
  }

  function onDragLeave() {
    setDragging(false);
  }

  function onFileChange(e) {
    handleFile(e.target.files?.[0]);
    e.target.value = "";
  }

  return (
    <div
      className={`${styles.zone} ${dragging ? styles.dragging : ""} ${disabled ? styles.zoneDisabled : ""}`}
      onDrop={disabled ? undefined : onDrop}
      onDragOver={disabled ? undefined : onDragOver}
      onDragLeave={disabled ? undefined : onDragLeave}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={disabled ? -1 : 0}
      onKeyDown={(e) => e.key === "Enter" && !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.doc"
        className={styles.hiddenInput}
        onChange={onFileChange}
        disabled={disabled}
      />

      {status === "parsing" ? (
        <span className={styles.parsing}>Extracting text…</span>
      ) : (
        <>
          <span className={styles.icon}>📄</span>
          <span className={styles.text}>
            Drop PDF or DOCX here, or <span className={styles.browse}>browse</span>
          </span>
          {status === "error" && (
            <span className={styles.error}>{errorMsg}</span>
          )}
        </>
      )}
    </div>
  );
}
