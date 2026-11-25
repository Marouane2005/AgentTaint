import { describe, expect, it } from "vitest";
import { friendlyError } from "./errors";

describe("friendlyError", () => {
  it("maps statuses and network failures to actionable text", () => {
    expect(friendlyError(new Error("401 /x: no"))).toMatch(/token was rejected/);
    expect(friendlyError(new Error("503 /x: down"))).toMatch(/API hit an error/);
    expect(friendlyError(new TypeError("Failed to fetch"))).toMatch(/Cannot reach/);
    expect(friendlyError("odd")).toBe("odd");
  });
});
