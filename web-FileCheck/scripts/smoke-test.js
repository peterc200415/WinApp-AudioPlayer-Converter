const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");
const XLSX = require("xlsx");

const root = path.resolve(__dirname, "..");
const sampleA = path.join(root, "storage", "sample-a.txt");
const sampleB = path.join(root, "storage", "sample-b.txt");
const sampleSheetA = path.join(root, "storage", "sample-a.xlsx");
const sampleSheetB = path.join(root, "storage", "sample-b.xlsx");

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildMultipartBody(files) {
  const boundary = "----webfilecheckboundary";
  const chunks = [];

  for (const file of files) {
    chunks.push(Buffer.from(`--${boundary}\r\n`));
    chunks.push(Buffer.from(`Content-Disposition: form-data; name="${file.fieldName}"; filename="${file.filename}"\r\n`));
    chunks.push(Buffer.from("Content-Type: text/plain\r\n\r\n"));
    chunks.push(file.buffer);
    chunks.push(Buffer.from("\r\n"));
  }

  chunks.push(Buffer.from(`--${boundary}--\r\n`));

  return {
    boundary,
    body: Buffer.concat(chunks),
  };
}

function request(method, pathname, body, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: "127.0.0.1",
        port: 4000,
        path: pathname,
        method,
        headers,
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          resolve({
            statusCode: res.statusCode,
            body: Buffer.concat(chunks).toString("utf8"),
          });
        });
      }
    );

    req.on("error", reject);
    if (body) {
      req.write(body);
    }
    req.end();
  });
}

async function main() {
  fs.writeFileSync(sampleA, "# Title\n\nLine one\n\nShared note");
  fs.writeFileSync(sampleB, "# Title\n\nLine two\n\nShared note");
  const wbA = XLSX.utils.book_new();
  const wsA = XLSX.utils.aoa_to_sheet([
    ["Material", "Qty", "Remark"],
    ["ABC-001", "1", "Old"],
    ["ABC-002", "2", "Same"],
  ]);
  XLSX.utils.book_append_sheet(wbA, wsA, "BOM");
  XLSX.writeFile(wbA, sampleSheetA);

  const wbB = XLSX.utils.book_new();
  const wsB = XLSX.utils.aoa_to_sheet([
    ["Material", "Qty", "Remark"],
    ["ABC-001", "3", "New"],
    ["ABC-003", "5", "Added"],
  ]);
  XLSX.utils.book_append_sheet(wbB, wsB, "BOM");
  XLSX.writeFile(wbB, sampleSheetB);

  const server = spawn(process.execPath, ["src/server.js"], {
    cwd: root,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, PORT: "4000" },
  });

  try {
    await wait(1200);

    const health = await request("GET", "/api/health");
    if (health.statusCode !== 200) {
      throw new Error(`Health check failed: ${health.statusCode}`);
    }

    const multipart = buildMultipartBody([
      { fieldName: "fileA", filename: "a.md", buffer: fs.readFileSync(sampleA) },
      { fieldName: "fileB", filename: "b.md", buffer: fs.readFileSync(sampleB) },
    ]);

    const compare = await request("POST", "/api/compare", multipart.body, {
      "Content-Type": `multipart/form-data; boundary=${multipart.boundary}`,
      "Content-Length": multipart.body.length,
    });

    if (compare.statusCode !== 200) {
      throw new Error(`Compare failed: ${compare.statusCode}\n${compare.body}`);
    }

    const parsed = JSON.parse(compare.body);
    if (!parsed.comparison || parsed.comparison.mode !== "document") {
      throw new Error("Comparison output missing document mode.");
    }

    const spreadsheetMultipart = buildMultipartBody([
      { fieldName: "fileA", filename: "a.xlsx", buffer: fs.readFileSync(sampleSheetA) },
      { fieldName: "fileB", filename: "b.xlsx", buffer: fs.readFileSync(sampleSheetB) },
    ]);

    const spreadsheetCompare = await request("POST", "/api/compare", spreadsheetMultipart.body, {
      "Content-Type": `multipart/form-data; boundary=${spreadsheetMultipart.boundary}`,
      "Content-Length": spreadsheetMultipart.body.length,
    });

    if (spreadsheetCompare.statusCode !== 200) {
      throw new Error(`Spreadsheet compare failed: ${spreadsheetCompare.statusCode}\n${spreadsheetCompare.body}`);
    }

    const spreadsheetParsed = JSON.parse(spreadsheetCompare.body);
    if (!spreadsheetParsed.comparison || spreadsheetParsed.comparison.mode !== "spreadsheet") {
      throw new Error("Comparison output missing spreadsheet mode.");
    }

    console.log("Smoke test passed");
    console.log(compare.body);
    console.log(spreadsheetCompare.body);
  } finally {
    server.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
