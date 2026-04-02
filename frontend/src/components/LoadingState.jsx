import styles from "./LoadingState.module.css";

export default function LoadingState({ message }) {
  return (
    <div className={styles.container}>
      <div className={styles.spinner} />
      <p className={styles.message}>{message}</p>
      <p className={styles.sub}>This may take 15–30 seconds</p>
    </div>
  );
}
