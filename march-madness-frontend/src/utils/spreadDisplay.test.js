import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  isPickEm,
  formatSpreadFavorite,
  formatSpreadSideSuffix,
  formatMatchupWithHomeLine,
} from "./spreadDisplay.js";

describe("isPickEm", () => {
  it("treats numeric zero variants as pick'em", () => {
    assert.equal(isPickEm(0), true);
    assert.equal(isPickEm(-0), true);
    assert.equal(isPickEm(0.0), true);
    assert.equal(isPickEm("0"), true);
    assert.equal(isPickEm(1e-12), true);
  });

  it("rejects non-zero and non-numeric values", () => {
    assert.equal(isPickEm(3), false);
    assert.equal(isPickEm(-3), false);
    assert.equal(isPickEm(0.5), false);
    assert.equal(isPickEm(undefined), false);
    assert.equal(isPickEm(NaN), false);
    assert.equal(isPickEm("abc"), false);
  });
});

describe("formatSpreadFavorite", () => {
  it("returns Pick'em instead of ±0", () => {
    assert.equal(formatSpreadFavorite(0, "Chiefs", "Bills"), "Pick'em");
    assert.equal(formatSpreadFavorite(-0, "Chiefs", "Bills"), "Pick'em");
    assert.doesNotMatch(formatSpreadFavorite(0, "Chiefs", "Bills"), /±|-[0]|-0|\+0/);
  });

  it("leaves non-zero favorite lines unchanged", () => {
    assert.equal(formatSpreadFavorite(3, "Chiefs", "Bills"), "Chiefs -3");
    assert.equal(formatSpreadFavorite(-7, "Chiefs", "Bills"), "Bills -7");
    assert.equal(formatSpreadFavorite(3.5, "Home", "Away"), "Home -3.5");
  });
});

describe("formatSpreadSideSuffix", () => {
  it("returns empty suffix for pick'em (no ±0)", () => {
    assert.equal(formatSpreadSideSuffix(0, "home"), "");
    assert.equal(formatSpreadSideSuffix(0, "away"), "");
    assert.equal(formatSpreadSideSuffix(-0, "home"), "");
  });

  it("keeps existing home-favorite suffixes", () => {
    assert.equal(formatSpreadSideSuffix(3, "home"), " -3");
    assert.equal(formatSpreadSideSuffix(3, "away"), " +3");
  });

  it("keeps existing away-favorite suffixes", () => {
    assert.equal(formatSpreadSideSuffix(-7, "home"), " +7");
    assert.equal(formatSpreadSideSuffix(-7, "away"), " -7");
  });
});

describe("formatMatchupWithHomeLine", () => {
  it("names pick'em instead of Away @ Home -0", () => {
    assert.equal(
      formatMatchupWithHomeLine(0, "Chiefs", "Bills"),
      "Bills @ Chiefs Pick'em"
    );
    assert.doesNotMatch(formatMatchupWithHomeLine(0, "Chiefs", "Bills"), /-0|\+0|±0/);
  });

  it("leaves non-zero home-line format unchanged", () => {
    assert.equal(
      formatMatchupWithHomeLine(3, "Chiefs", "Bills"),
      "Bills @ Chiefs -3"
    );
    assert.equal(
      formatMatchupWithHomeLine(-7, "Chiefs", "Bills"),
      "Bills @ Chiefs +7"
    );
  });
});
