const { describeFormat, formatRegistry } = require("./formats");
const { parseDocumentFile } = require("./document");
const { parseSpreadsheetFile } = require("./spreadsheet");

function planParsing(file) {
  const format = describeFormat(file && file.name);

  return {
    filename: (file && file.name) || "",
    size: (file && file.size) || null,
    format,
    nextStep: format.supported
      ? `Implement parser for ${format.label}`
      : "Reject file before upload and ask for a supported format",
  };
}

module.exports = {
  formatRegistry,
  planParsing,
  parseDocumentFile,
  parseSpreadsheetFile,
};
