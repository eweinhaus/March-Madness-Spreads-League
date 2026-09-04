import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { isLockOnlyIncomplete, lockOnlyWarningCopy } from "./incompleteSubmit.js";

const games = [
  { game_id: "1" },
  { game_id: "2" },
  { game_id: "3" },
];

describe("isLockOnlyIncomplete", () => {
  it("is true when lock UI is on, games are missing, and an open game is locked", () => {
    assert.equal(
      isLockOnlyIncomplete({
        showLockUI: true,
        warnings: { missingGames: [{ gid: "2" }, { gid: "3" }] },
        availableGames: games,
        locks: { 1: true },
        existingLocks: {},
      }),
      true
    );
  });

  it("counts an existing saved lock when locks map has no override", () => {
    assert.equal(
      isLockOnlyIncomplete({
        showLockUI: true,
        warnings: { missingGames: [{ gid: "2" }] },
        availableGames: games,
        locks: {},
        existingLocks: { 1: true },
      }),
      true
    );
  });

  it("is false when the user has no lock on the open slate", () => {
    assert.equal(
      isLockOnlyIncomplete({
        showLockUI: true,
        warnings: { missingGames: [{ gid: "1" }] },
        availableGames: games,
        locks: {},
        existingLocks: {},
      }),
      false
    );
  });

  it("is false when a lock override turns the existing lock off", () => {
    assert.equal(
      isLockOnlyIncomplete({
        showLockUI: true,
        warnings: { missingGames: [{ gid: "2" }] },
        availableGames: games,
        locks: { 1: false },
        existingLocks: { 1: true },
      }),
      false
    );
  });

  it("is false when lock UI is off", () => {
    assert.equal(
      isLockOnlyIncomplete({
        showLockUI: false,
        warnings: { missingGames: [{ gid: "2" }] },
        availableGames: games,
        locks: { 1: true },
      }),
      false
    );
  });

  it("is false when every open game has a pick", () => {
    assert.equal(
      isLockOnlyIncomplete({
        showLockUI: true,
        warnings: { missingGames: [] },
        availableGames: games,
        locks: { 1: true },
      }),
      false
    );
  });
});

describe("lockOnlyWarningCopy", () => {
  it("includes lockLabel and picked/open/missing counts", () => {
    assert.equal(
      lockOnlyWarningCopy({
        lockLabel: "lock of the week",
        pickedCount: 1,
        openCount: 12,
        missingCount: 11,
      }),
      "You're saving your lock of the week but only 1 of 12 open games have a pick. 11 game(s) will stay blank."
    );
  });
});
