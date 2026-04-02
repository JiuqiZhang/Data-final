import { useState, useRef, useEffect } from "react";
import { analyzeResume } from "../api/client";

const LOADING_MESSAGES = [
  "Analyzing your resume...",
  "Extracting skills from job description...",
  "Identifying skill gaps with Gemini...",
  "Searching YouTube for tutorials...",
  "Querying OER Commons for courses...",
  "Ranking resources by relevance...",
  "Building your learning path...",
];

export function useAnalysis() {
  const [state, setState] = useState("idle"); // idle | loading | success | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loadingMessage, setLoadingMessage] = useState(LOADING_MESSAGES[0]);
  const msgIndexRef = useRef(0);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (state === "loading") {
      msgIndexRef.current = 0;
      setLoadingMessage(LOADING_MESSAGES[0]);
      intervalRef.current = setInterval(() => {
        msgIndexRef.current = (msgIndexRef.current + 1) % LOADING_MESSAGES.length;
        setLoadingMessage(LOADING_MESSAGES[msgIndexRef.current]);
      }, 3000);
    } else {
      clearInterval(intervalRef.current);
    }
    return () => clearInterval(intervalRef.current);
  }, [state]);

  async function run(resumeText, jobDescription) {
    setState("loading");
    setError(null);
    setResult(null);

    try {
      const data = await analyzeResume(resumeText, jobDescription);
      setResult(data);
      setState("success");
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        "Something went wrong. Please try again.";
      setError(msg);
      setState("error");
    }
  }

  function reset() {
    setState("idle");
    setResult(null);
    setError(null);
  }

  return { state, result, error, loadingMessage, run, reset };
}
