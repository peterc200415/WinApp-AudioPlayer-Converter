const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");
const XLSX = require("xlsx");
const { Document, Packer, Paragraph } = require("docx");

const root = path.resolve(__dirname, "..");
const sampleA = path.join(root, "storage", "sample-a.txt");
const sampleB = path.join(root, "storage", "sample-b.txt");
const sampleSheetA = path.join(root, "storage", "sample-a.xlsx");
const sampleSheetB = path.join(root, "storage", "sample-b.xlsx");
const sampleDocA = path.join(root, "storage", "sample-a.docx");
const sampleDocB = path.join(root, "storage", "sample-b.docx");
const samplePdfA = path.join(root, "node_modules", "pdf-parse", "test", "data", "01-valid.pdf");
const samplePdfB = path.join(root, "node_modules", "pdf-parse", "test", "data", "02-valid.pdf");

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForServer(maxAttempts = 20) {
  let lastError = null;

  for (let index = 0; index < maxAttempts; index += 1) {
    try {
      const response = await request("GET", "/api/health");
      if (response.statusCode === 200) {
        return response;
      }
    } catch (error) {
      lastError = error;
    }

    await wait(500);
  }

  throw lastError || new Error("Server did not become ready in time.");
}

function buildMultipartBody(files) {
  const boundary = "----webfilecheckboundary";
  const chunks = [];

  for (const file of files) {
    chunks.push(Buffer.from(`--${boundary}\r\n`));
    chunks.push(Buffer.from(`Content-Disposition: form-data; name="${file.fieldName}"; filename="${file.filename}"\r\n`));
    chunks.push(Buffer.from(`Content-Type: ${file.contentType || "application/octet-stream"}\r\n\r\n`));
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

async function createDocxSample(targetPath, heading, bodyLine) {
  const doc = new Document({
    sections: [
      {
        properties: {},
        children: [
          new Paragraph({ text: heading, heading: "Heading1" }),
          new Paragraph(bodyLine),
          new Paragraph("Shared note"),
        ],
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(targetPath, buffer);
}

async function compareAndAssert(files, expectedMode) {
  const multipart = buildMultipartBody(files);
  const response = await request("POST", "/api/compare", multipart.body, {
    "Content-Type": `multipart/form-data; boundary=${multipart.boundary}`,
    "Content-Length": multipart.body.length,
  });

  if (response.statusCode !== 200) {
    throw new Error(`Compare failed: ${response.statusCode}\n${response.body}`);
  }

  const parsed = JSON.parse(response.body);
  if (!parsed.comparison || parsed.comparison.mode !== expectedMode) {
    throw new Error(`Comparison output missing ${expectedMode} mode.`);
  }

  return parsed;
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

  await createDocxSample(sampleDocA, "Title", "Line one");
  await createDocxSample(sampleDocB, "Title", "Line two");

  const server = spawn(process.execPath, ["src/server.js"], {
    cwd: root,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, PORT: "4000" },
  });

  try {
    const health = await waitForServer();
    if (health.statusCode !== 200) {
      throw new Error(`Health check failed: ${health.statusCode}`);
    }

    const markdownResult = await compareAndAssert(
      [
        { fieldName: "fileA", filename: "a.md", buffer: fs.readFileSync(sampleA), contentType: "text/markdown" },
        { fieldName: "fileB", filename: "b.md", buffer: fs.readFileSync(sampleB), contentType: "text/markdown" },
      ],
      "document"
    );

    const spreadsheetResult = await compareAndAssert(
      [
        { fieldName: "fileA", filename: "a.xlsx", buffer: fs.readFileSync(sampleSheetA), contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
        { fieldName: "fileB", filename: "b.xlsx", buffer: fs.readFileSync(sampleSheetB), contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
      ],
      "spreadsheet"
    );

    const docxResult = await compareAndAssert(
      [
        { fieldName: "fileA", filename: "a.docx", buffer: fs.readFileSync(sampleDocA), contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
        { fieldName: "fileB", filename: "b.docx", buffer: fs.readFileSync(sampleDocB), contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" },
      ],
      "document"
    );

    const pdfResult = await compareAndAssert(
      [
        { fieldName: "fileA", filename: "a.pdf", buffer: fs.readFileSync(samplePdfA), contentType: "application/pdf" },
        { fieldName: "fileB", filename: "b.pdf", buffer: fs.readFileSync(samplePdfB), contentType: "application/pdf" },
      ],
      "document"
    );

    console.log("Smoke test passed");
    console.log(JSON.stringify({
      markdown: markdownResult.comparison.summary,
      spreadsheet: spreadsheetResult.comparison.summary,
      docx: docxResult.comparison.summary,
      pdf: pdfResult.comparison.summary,
    }, null, 2));
  } finally {
    server.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
