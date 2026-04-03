const form = document.getElementById("compare-form");
const statusBox = document.getElementById("status");
const resultsPanel = document.getElementById("results-panel");
const resultsMeta = document.getElementById("results-meta");
const summaryGrid = document.getElementById("summary-grid");
const detailsContainer = document.getElementById("details");
const rawOutput = document.getElementById("output");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const inputA = document.getElementById("fileA");
  const inputB = document.getElementById("fileB");
  const fileA = inputA.files[0];
  const fileB = inputB.files[0];

  if (!fileA || !fileB) {
    statusBox.textContent = "請先選擇兩個檔案再開始比對。";
    return;
  }

  const payload = new FormData();
  payload.append("fileA", fileA);
  payload.append("fileB", fileB);

  statusBox.textContent = "上傳中，正在比對檔案...";
  resultsPanel.hidden = true;
  summaryGrid.innerHTML = "";
  detailsContainer.innerHTML = "";
  rawOutput.textContent = "";

  try {
    const response = await fetch("/api/compare", {
      method: "POST",
      body: payload,
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "比對失敗。");
    }

    statusBox.textContent = `比對完成，模式：${result.comparison.mode}，結果編號：${result.resultId}`;
    renderResult(result);
  } catch (error) {
    resultsPanel.hidden = true;
    statusBox.textContent = error.message || "比對失敗。";
  }
});

function renderResult(result) {
  const comparison = result.comparison || {};
  resultsPanel.hidden = false;
  resultsMeta.textContent = `${result.fileA.name} vs ${result.fileB.name} | mode: ${comparison.mode} | resultId: ${result.resultId}`;
  rawOutput.textContent = JSON.stringify(result, null, 2);

  renderSummary(comparison.summary || {});

  if (comparison.mode === "spreadsheet") {
    renderSpreadsheetDetails(comparison);
    return;
  }

  renderDocumentDetails(comparison);
}

function renderSummary(summary) {
  summaryGrid.innerHTML = "";
  const entries = Object.entries(summary);

  entries.forEach(([key, value]) => {
    const card = document.createElement("article");
    card.className = "metric-card";

    const label = document.createElement("div");
    label.className = "metric-label";
    label.textContent = humanizeKey(key);

    const metricValue = document.createElement("div");
    metricValue.className = "metric-value";
    metricValue.textContent = value;

    card.append(label, metricValue);
    summaryGrid.appendChild(card);
  });
}

function renderDocumentDetails(comparison) {
  addSection(
    "段落新增 Added Paragraphs",
    renderTextList(comparison.addedParagraphs, "沒有新增段落")
  );

  addSection(
    "段落移除 Removed Paragraphs",
    renderTextList(comparison.removedParagraphs, "沒有移除段落")
  );

  addSection(
    "章節差異 Section Diffs",
    renderSectionDiffs(comparison.sectionDiffs)
  );

  if (Array.isArray(comparison.warnings) && comparison.warnings.length) {
    addSection(
      "警告 Warnings",
      renderTextList(comparison.warnings, "沒有警告")
    );
  }
}

function renderSpreadsheetDetails(comparison) {
  addSection("新增資料 Added Rows", renderRowList(comparison.added, "沒有新增資料"));
  addSection("刪除資料 Removed Rows", renderRowList(comparison.removed, "沒有刪除資料"));
  addSection("修改資料 Changed Rows", renderChangedRows(comparison.changed));

  if (comparison.duplicateKeysA?.length || comparison.duplicateKeysB?.length) {
    const wrapper = document.createElement("div");
    wrapper.className = "stack";
    wrapper.appendChild(renderTextList((comparison.duplicateKeysA || []).map((item) => `A duplicate key: ${item.key} rows ${item.rows.join(", ")}`), "A 無重複 key"));
    wrapper.appendChild(renderTextList((comparison.duplicateKeysB || []).map((item) => `B duplicate key: ${item.key} rows ${item.rows.join(", ")}`), "B 無重複 key"));
    addSection("重複鍵 Duplicate Keys", wrapper);
  }

  if (comparison.missingKeysA?.length || comparison.missingKeysB?.length) {
    const wrapper = document.createElement("div");
    wrapper.className = "stack";
    wrapper.appendChild(renderTextList((comparison.missingKeysA || []).map((item) => `A row ${item.rowNumber}`), "A 無缺失 key"));
    wrapper.appendChild(renderTextList((comparison.missingKeysB || []).map((item) => `B row ${item.rowNumber}`), "B 無缺失 key"));
    addSection("缺失鍵 Missing Keys", wrapper);
  }
}

function renderTextList(items, emptyText) {
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    return empty;
  }

  const list = document.createElement("div");
  list.className = "stack";

  items.forEach((item) => {
    const block = document.createElement("article");
    block.className = "result-block";
    block.textContent = item;
    list.appendChild(block);
  });

  return list;
}

function renderSectionDiffs(items) {
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "沒有章節差異";
    return empty;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "stack";

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "diff-card";

    const title = document.createElement("h4");
    title.textContent = `${item.heading} | ${item.status}`;

    const columns = document.createElement("div");
    columns.className = "diff-columns";

    const left = document.createElement("pre");
    left.className = "diff-pane";
    left.textContent = item.textA || "(empty)";

    const right = document.createElement("pre");
    right.className = "diff-pane";
    right.textContent = item.textB || "(empty)";

    columns.append(left, right);
    card.append(title, columns);
    wrapper.appendChild(card);
  });

  return wrapper;
}

function renderRowList(items, emptyText) {
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = emptyText;
    return empty;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "stack";

  items.forEach((item) => {
    const block = document.createElement("article");
    block.className = "result-block";
    block.innerHTML = `<strong>${item.key}</strong><br>${escapeHtml(JSON.stringify(item.values, null, 2))}`;
    wrapper.appendChild(block);
  });

  return wrapper;
}

function renderChangedRows(items) {
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "沒有修改資料";
    return empty;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "stack";

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "diff-card";

    const title = document.createElement("h4");
    title.textContent = `${item.key} | A row ${item.rowA} / B row ${item.rowB}`;

    const list = document.createElement("ul");
    list.className = "change-list";

    item.changes.forEach((change) => {
      const li = document.createElement("li");
      li.textContent = `${change.column}: "${change.valueA}" -> "${change.valueB}"`;
      list.appendChild(li);
    });

    card.append(title, list);
    wrapper.appendChild(card);
  });

  return wrapper;
}

function addSection(titleText, contentNode) {
  const section = document.createElement("section");
  section.className = "detail-section";

  const title = document.createElement("h3");
  title.textContent = titleText;

  section.append(title, contentNode);
  detailsContainer.appendChild(section);
}

function humanizeKey(key) {
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
