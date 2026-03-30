const formatRegistry = {
  xls: { category: "spreadsheet", label: "Excel 97-2003", planned: true },
  xlsx: { category: "spreadsheet", label: "Excel Workbook", planned: true },
  txt: { category: "document", label: "Plain Text", planned: true },
  md: { category: "document", label: "Markdown", planned: true },
  docx: { category: "document", label: "Word Document", planned: true },
  pdf: { category: "document", label: "PDF (text-based)", planned: true },
};

function normalizeExtension(filename) {
  const match = String(filename || "").toLowerCase().match(/\.([a-z0-9]+)$/);
  return match ? match[1] : "";
}

function describeFormat(filename) {
  const extension = normalizeExtension(filename);
  const info = formatRegistry[extension];

  if (!info) {
    return {
      extension,
      supported: false,
      category: "unknown",
      label: "Unsupported format",
    };
  }

  return {
    extension,
    supported: true,
    category: info.category,
    label: info.label,
    planned: info.planned,
  };
}

module.exports = {
  formatRegistry,
  normalizeExtension,
  describeFormat,
};
