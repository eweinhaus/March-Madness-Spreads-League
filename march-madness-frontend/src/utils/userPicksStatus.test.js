import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { formatUserPicksStatus } from "./userPicksStatus.js";

describe("formatUserPicksStatus", () => {
  it("shows no games remaining without a lock fragment when unlocked", () => {
    assert.deepEqual(
      formatUserPicksStatus({
        picks_made: 0,
        total_games: 0,
        is_complete: true,
        has_current_period_lock: false,
      }),
      { text: "No games remaining", variant: "secondary" }
    );
  });

  it("appends lock set when no games remain but a lock is set", () => {
    assert.deepEqual(
      formatUserPicksStatus({
        picks_made: 0,
        total_games: 0,
        has_current_period_lock: true,
      }),
      { text: "No games remaining · lock set", variant: "secondary" }
    );
  });

  it("shows complete with lock as success N/M · lock set", () => {
    assert.deepEqual(
      formatUserPicksStatus({
        picks_made: 12,
        total_games: 12,
        is_complete: true,
        has_current_period_lock: true,
      }),
      { text: "12/12 · lock set", variant: "success" }
    );
  });

  it("warns when complete but missing an expected lock", () => {
    assert.deepEqual(
      formatUserPicksStatus({
        picks_made: 12,
        total_games: 12,
        is_complete: true,
        has_current_period_lock: false,
      }),
      { text: "12/12 · no lock", variant: "warning" }
    );
  });

  it("uses success for complete + no lock when a lock is not expected", () => {
    assert.deepEqual(
      formatUserPicksStatus(
        {
          picks_made: 12,
          total_games: 12,
          is_complete: true,
          has_current_period_lock: false,
        },
        { expectsLock: false }
      ),
      { text: "12/12 · no lock", variant: "success" }
    );
  });

  it("warns for incomplete with a lock set (Blair-shaped row)", () => {
    assert.deepEqual(
      formatUserPicksStatus({
        picks_made: 0,
        total_games: 12,
        is_complete: false,
        has_current_period_lock: true,
      }),
      { text: "0/12 · lock set", variant: "warning" }
    );
  });

  it("uses danger for incomplete with no lock", () => {
    assert.deepEqual(
      formatUserPicksStatus({
        picks_made: 3,
        total_games: 12,
        is_complete: false,
        has_current_period_lock: false,
      }),
      { text: "3/12 · no lock", variant: "danger" }
    );
  });
});
