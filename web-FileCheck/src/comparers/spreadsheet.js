function normalizeRecordForHash(record, headers) {
  return headers.map((header) => `${header}=${record.values[header] || ""}`).join("|");
}

function buildKey(record, keyColumns) {
  return keyColumns.map((column) => record.values[column] || "").join("||").trim();
}

function indexRecords(records, keyColumns) {
  const keyed = new Map();
  const missingKeys = [];
  const duplicateKeys = [];

  for (const record of records) {
    const key = buildKey(record, keyColumns);
    if (!key) {
      missingKeys.push(record);
      continue;
    }

    if (keyed.has(key)) {
      duplicateKeys.push({
        key,
        rows: [keyed.get(key).rowNumber, record.rowNumber],
      });
      continue;
    }

    keyed.set(key, record);
  }

  return { keyed, missingKeys, duplicateKeys };
}

function compareRecordValues(recordA, recordB, headers) {
  const changes = [];
  for (const header of headers) {
    const valueA = recordA.values[header] || "";
    const valueB = recordB.values[header] || "";
    if (valueA !== valueB) {
      changes.push({
        column: header,
        valueA,
        valueB,
      });
    }
  }
  return changes;
}

function compareSpreadsheets(parsedA, parsedB) {
  const headers = Array.from(new Set([...parsedA.headers, ...parsedB.headers]));
  const keyColumns = parsedA.keyColumns.length ? parsedA.keyColumns : parsedB.keyColumns;
  const indexedA = indexRecords(parsedA.records, keyColumns);
  const indexedB = indexRecords(parsedB.records, keyColumns);
  const allKeys = new Set([...indexedA.keyed.keys(), ...indexedB.keyed.keys()]);

  const added = [];
  const removed = [];
  const changed = [];
  const identical = [];

  for (const key of allKeys) {
    const recordA = indexedA.keyed.get(key);
    const recordB = indexedB.keyed.get(key);

    if (!recordA) {
      added.push({ key, rowB: recordB.rowNumber, values: recordB.values });
      continue;
    }

    if (!recordB) {
      removed.push({ key, rowA: recordA.rowNumber, values: recordA.values });
      continue;
    }

    const hashA = normalizeRecordForHash(recordA, headers);
    const hashB = normalizeRecordForHash(recordB, headers);
    if (hashA === hashB) {
      identical.push({ key, rowA: recordA.rowNumber, rowB: recordB.rowNumber });
      continue;
    }

    changed.push({
      key,
      rowA: recordA.rowNumber,
      rowB: recordB.rowNumber,
      changes: compareRecordValues(recordA, recordB, headers),
    });
  }

  return {
    mode: "spreadsheet",
    keyColumns,
    headers,
    summary: {
      rowsA: parsedA.records.length,
      rowsB: parsedB.records.length,
      added: added.length,
      removed: removed.length,
      changed: changed.length,
      identical: identical.length,
      missingKeysA: indexedA.missingKeys.length,
      missingKeysB: indexedB.missingKeys.length,
      duplicateKeysA: indexedA.duplicateKeys.length,
      duplicateKeysB: indexedB.duplicateKeys.length,
    },
    added,
    removed,
    changed,
    identical,
    missingKeysA: indexedA.missingKeys,
    missingKeysB: indexedB.missingKeys,
    duplicateKeysA: indexedA.duplicateKeys,
    duplicateKeysB: indexedB.duplicateKeys,
    warnings: [...parsedA.warnings, ...parsedB.warnings],
  };
}

module.exports = {
  compareSpreadsheets,
};
