/** Run fn as a promise so sync throws become allSettled rejections, with a display label. */
export function createLabeledTask(label, fn) {
  return Promise.resolve().then(async () => {
    try {
      return await fn();
    } catch (err) {
      if (err && typeof err === "object") {
        err.label = label;
        throw err;
      }
      const wrapped = new Error(String(err));
      wrapped.label = label;
      throw wrapped;
    }
  });
}

export function formatFailedLabels(labels, max = 5) {
  if (!labels?.length) return "";
  const shown = labels.slice(0, max);
  const extra = labels.length - shown.length;
  const list = shown.join(", ");
  return extra > 0 ? `${list}, and ${extra} more` : list;
}

export function collectFailedLabels(settledResults) {
  return settledResults
    .filter((r) => r.status === "rejected")
    .map((r) => r.reason?.label)
    .filter(Boolean);
}

export function buildSubmitFeedback({
  savedGames = 0,
  failedGames = 0,
  savedTBs = 0,
  failedTBs = 0,
  failedLabels = [],
} = {}) {
  const parts = [];
  const totalGames = savedGames + failedGames;
  const totalTBs = savedTBs + failedTBs;

  if (totalGames > 0) {
    if (failedGames === 0) {
      parts.push(`Saved ${savedGames} pick${savedGames !== 1 ? "s" : ""}`);
    } else if (savedGames === 0) {
      parts.push(`Failed to save ${failedGames} pick${failedGames !== 1 ? "s" : ""}`);
    } else {
      parts.push(`Saved ${savedGames} pick${savedGames !== 1 ? "s" : ""}, ${failedGames} failed`);
    }
  }

  if (totalTBs > 0) {
    if (failedTBs === 0) {
      parts.push(`Saved ${savedTBs} tiebreaker${savedTBs !== 1 ? "s" : ""}`);
    } else if (savedTBs === 0) {
      parts.push(`Failed to save ${failedTBs} tiebreaker${failedTBs !== 1 ? "s" : ""}`);
    } else {
      parts.push(`Saved ${savedTBs} tiebreaker${savedTBs !== 1 ? "s" : ""}, ${failedTBs} failed`);
    }
  }

  const anyFail = failedGames > 0 || failedTBs > 0;
  const anySave = savedGames > 0 || savedTBs > 0;
  const variant = anyFail ? (anySave ? "warning" : "danger") : "success";

  return {
    variant,
    message: parts.join("; "),
    failedLabels: [...failedLabels],
  };
}
