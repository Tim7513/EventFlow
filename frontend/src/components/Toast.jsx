/**
 * Toast notification system.
 *
 * Usage:
 *   const { toasts, addToast } = useToasts();
 *   <ToastContainer toasts={toasts} />
 *   addToast("Saved!", "success");
 */
import { useState, useCallback, useEffect } from "react";

export function useToasts() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = "info") => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev, { id, message, type }]);
    // Auto-dismiss after 4s
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  return { toasts, addToast };
}

export function ToastContainer({ toasts }) {
  if (!toasts.length) return null;
  return (
    <div className="toast-container" aria-live="polite">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} />
      ))}
    </div>
  );
}

function Toast({ toast }) {
  const icons = { success: "✓", error: "✕", info: "ℹ" };
  return (
    <div className={`toast toast-${toast.type}`} role="alert">
      <span className="toast-icon">{icons[toast.type] ?? icons.info}</span>
      <span className="toast-message">{toast.message}</span>
    </div>
  );
}
