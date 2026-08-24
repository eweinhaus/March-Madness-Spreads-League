import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  createLabeledTask,
  formatFailedLabels,
  collectFailedLabels,
  buildSubmitFeedback,
} from "./submitFeedback.js";

describe("createLabeledTask", () => {
  it("turns a sync throw into an allSettled rejection with a label", async () => {
    const results = await Promise.allSettled([
      createLabeledTask("Bills @ Chiefs", () => {
        throw new Error("No pick found for game 1");
      }),
      createLabeledTask("Cowboys @ Eagles", async () => ({ ok: true })),
    ]);

    assert.equal(results[0].status, "rejected");
    assert.equal(results[0].reason.message, "No pick found for game 1");
    assert.equal(results[0].reason.label, "Bills @ Chiefs");
    assert.equal(results[1].status, "fulfilled");
    assert.deepEqual(results[1].value, { ok: true });
  });

  it("attaches label to async failures without aborting siblings", async () => {
    const results = await Promise.allSettled([
      createLabeledTask("TB: total points", async () => {
        throw Object.assign(new Error("server"), { response: { status: 500 } });
      }),
      createLabeledTask("Jets @ Patriots", async () => "saved"),
    ]);

    assert.equal(results[0].status, "rejected");
    assert.equal(results[0].reason.label, "TB: total points");
    assert.equal(results[1].status, "fulfilled");
  });
});

describe("formatFailedLabels", () => {
  it("joins up to five labels then and N more", () => {
    assert.equal(formatFailedLabels(["A"]), "A");
    assert.equal(formatFailedLabels(["A", "B", "C"]), "A, B, C");
    assert.equal(
      formatFailedLabels(["A", "B", "C", "D", "E", "F", "G"]),
      "A, B, C, D, E, and 2 more"
    );
  });
});

describe("collectFailedLabels + buildSubmitFeedback", () => {
  it("names failed matchups and uses warning when some succeed", async () => {
    const settled = await Promise.allSettled([
      createLabeledTask("Bills @ Chiefs", () => {
        throw new Error("missing");
      }),
      Promise.resolve("ok"),
    ]);

    const failedLabels = collectFailedLabels(settled);
    const feedback = buildSubmitFeedback({
      savedGames: 1,
      failedGames: 1,
      failedLabels,
    });

    assert.deepEqual(failedLabels, ["Bills @ Chiefs"]);
    assert.equal(feedback.variant, "warning");
    assert.equal(feedback.message, "Saved 1 pick, 1 failed");
    assert.deepEqual(feedback.failedLabels, ["Bills @ Chiefs"]);
  });

  it("uses danger when nothing saved", () => {
    const feedback = buildSubmitFeedback({
      failedGames: 2,
      failedTBs: 1,
      failedLabels: ["A", "B", "Q1"],
    });
    assert.equal(feedback.variant, "danger");
    assert.match(feedback.message, /Failed to save 2 picks/);
    assert.match(feedback.message, /Failed to save 1 tiebreaker/);
  });

  it("uses success when everything saved", () => {
    const feedback = buildSubmitFeedback({ savedGames: 3, savedTBs: 1 });
    assert.equal(feedback.variant, "success");
    assert.equal(feedback.message, "Saved 3 picks; Saved 1 tiebreaker");
    assert.deepEqual(feedback.failedLabels, []);
  });
});
