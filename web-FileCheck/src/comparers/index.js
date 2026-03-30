const { compareDocuments } = require("./document");
const { compareSpreadsheets } = require("./spreadsheet");

function planComparison(fileA, fileB) {
  const categoryA = fileA?.format?.category || "unknown";
  const categoryB = fileB?.format?.category || "unknown";

  if (!fileA?.format?.supported || !fileB?.format?.supported) {
    return {
      mode: "unsupported",
      ready: false,
      message: "One or both files are not in the planned format list.",
    };
  }

  if (categoryA !== categoryB) {
    return {
      mode: "mixed",
      ready: false,
      message: "v1 should compare similar content types. Mixed spreadsheet/document comparisons are deferred.",
    };
  }

  if (categoryA === "spreadsheet") {
    return {
      mode: "spreadsheet",
      ready: true,
      outputs: [
        "row-level diff",
        "added/removed/changed counts",
        "duplicate key diagnostics",
      ],
    };
  }

  return {
    mode: "document",
    ready: true,
    outputs: [
      "section-aware diff",
      "paragraph additions/removals",
      "parser warnings",
    ],
  };
}

module.exports = {
  compareDocuments,
  compareSpreadsheets,
  planComparison,
};
