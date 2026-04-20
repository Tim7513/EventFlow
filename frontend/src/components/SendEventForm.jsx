/**
 * Form for posting a new event to POST /event.
 * Calls onSuccess() so the parent can trigger a stats/recent refresh.
 */
import { useState } from "react";
import { postEvent } from "../api/client";

const PRESET_TYPES = ["purchase", "view", "click", "signup", "refund", "error"];

export default function SendEventForm({ onSuccess, addToast }) {
  const [type, setType] = useState("");
  const [customType, setCustomType] = useState("");
  const [value, setValue] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const effectiveType = type === "__custom__" ? customType.trim() : type;

  const handleSubmit = async (e) => {
    e.preventDefault();

    const numValue = parseFloat(value);
    if (!effectiveType) {
      addToast("Event type is required.", "error");
      return;
    }
    if (isNaN(numValue)) {
      addToast("Value must be a number.", "error");
      return;
    }

    setSubmitting(true);
    try {
      const res = await postEvent(effectiveType, numValue);
      addToast(`Event queued! ID: ${res.event_id.slice(0, 8)}…`, "success");
      onSuccess();
      // Reset form
      setType("");
      setCustomType("");
      setValue("");
    } catch (err) {
      addToast(err.message || "Failed to send event.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card form-card">
      <h2 className="card-title">Send Event</h2>
      <form onSubmit={handleSubmit} className="event-form" noValidate>
        <div className="field">
          <label htmlFor="event-type">Event Type</label>
          <select
            id="event-type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            required
          >
            <option value="" disabled>Select a type…</option>
            {PRESET_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
            <option value="__custom__">Custom…</option>
          </select>
        </div>

        {type === "__custom__" && (
          <div className="field">
            <label htmlFor="custom-type">Custom Type</label>
            <input
              id="custom-type"
              type="text"
              placeholder="e.g. checkout_started"
              value={customType}
              onChange={(e) => setCustomType(e.target.value)}
              maxLength={64}
              required
            />
          </div>
        )}

        <div className="field">
          <label htmlFor="event-value">Value</label>
          <input
            id="event-value"
            type="number"
            step="any"
            placeholder="e.g. 49.99"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
          />
        </div>

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? (
            <span className="btn-spinner" aria-label="Sending…" />
          ) : (
            "Send →"
          )}
        </button>
      </form>

      <div className="form-hint">
        Events are queued via SQS and processed asynchronously.
        Stats update after ~5–15 seconds.
      </div>
    </div>
  );
}
