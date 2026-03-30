const XLSX = require("xlsx");

function normalizeCell(value) {
  if (value === undefined || value === null) {
    return "";
  }
  return String(value).trim();
}

function pickHeaderRow(rows) {
  let bestIndex = 0;
  let bestScore = -1;

  rows.slice(0, 10).forEach((row, index) => {
    const populated = row.filter((cell) => normalizeCell(cell)).length;
    if (populated > bestScore) {
      bestScore = populated;
      bestIndex = index;
    }
  });

  return bestIndex;
}

function makeColumnName(index) {
  return `Column ${index + 1}`;
}

function buildRowObject(headers, row) {
  const output = {};
  headers.forEach((header, index) => {
    output[header] = normalizeCell(row[index]);
  });
  return output;
}

function resolveKeyColumns(headers) {
  const preferredNames = [
    "material",
    "material number",
    "part number",
    "pn",
    "item",
    "part no",
  ];

  const normalizedHeaders = headers.map((header) => normalizeCell(header).toLowerCase());
  const exactMatch = preferredNames.find((name) => normalizedHeaders.includes(name));
  if (exactMatch) {
    return [headers[normalizedHeaders.indexOf(exactMatch)]];
  }

  return headers.slice(0, 1);
}

function parseSpreadsheetFile(file) {
  const workbook = XLSX.read(file.buffer, { type: "buffer" });
  const firstSheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[firstSheetName];
  const rawRows = XLSX.utils.sheet_to_json(worksheet, {
    header: 1,
    blankrows: false,
    defval: "",
    raw: false,
  });

  const headerRowIndex = pickHeaderRow(rawRows);
  const headerRow = rawRows[headerRowIndex] || [];
  const headers = headerRow.map((header, index) => normalizeCell(header) || makeColumnName(index));
  const bodyRows = rawRows.slice(headerRowIndex + 1).filter((row) =>
    row.some((cell) => normalizeCell(cell))
  );
  const records = bodyRows.map((row, index) => ({
    rowNumber: headerRowIndex + index + 2,
    values: buildRowObject(headers, row),
  }));
  const keyColumns = resolveKeyColumns(headers);

  return {
    contentType: "spreadsheet",
    sheetName: firstSheetName,
    headers,
    keyColumns,
    records,
    warnings: [],
    metrics: {
      rows: records.length,
      columns: headers.length,
    },
  };
}

module.exports = {
  parseSpreadsheetFile,
};
