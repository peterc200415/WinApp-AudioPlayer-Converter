const fs = require("fs");
const http = require("http");
const path = require("path");
const config = require("./config");
const { sendJson, sendText, readJsonBody } = require("./utils/http");
const { parseMultipart } = require("./utils/multipart");
const { buildStoredFilename, createId, sha256, writeBufferToFile } = require("./utils/files");
const { formatRegistry, planParsing, parseDocumentFile, parseSpreadsheetFile } = require("./parsers");
const { planComparison, compareDocuments, compareSpreadsheets } = require("./comparers");

const publicDir = path.resolve(process.cwd(), "public");

async function ensureDirectories() {
  await fs.promises.mkdir(config.dataRoot, { recursive: true });
  await fs.promises.mkdir(config.paths.uploads, { recursive: true });
  await fs.promises.mkdir(config.paths.results, { recursive: true });
  await fs.promises.mkdir(config.paths.reports, { recursive: true });
}

function getMimeType(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  const mimeTypes = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
  };
  return mimeTypes[extension] || "application/octet-stream";
}

async function serveStatic(req, res) {
  const requestUrl = new URL(req.url, "http://localhost");
  const relativePath = requestUrl.pathname === "/" ? "index.html" : requestUrl.pathname.replace(/^\/+/, "");
  const absolutePath = path.normalize(path.join(publicDir, relativePath));

  if (!absolutePath.startsWith(publicDir)) {
    sendText(res, 404, "Not Found");
    return;
  }

  try {
    const content = await fs.promises.readFile(absolutePath);
    res.writeHead(200, {
      "Content-Type": getMimeType(absolutePath),
      "Content-Length": content.length,
      "Cache-Control": "no-store",
    });
    res.end(content);
  } catch (error) {
    sendText(res, 404, "Not Found");
  }
}

function buildCapabilities() {
  return {
    appName: config.appName,
    deploymentTarget: "10.10.10.30:4000",
    supportedFormats: Object.entries(formatRegistry).map(([extension, info]) => ({
      extension,
      category: info.category,
      label: info.label,
    })),
    storage: {
      uploads: config.paths.uploads,
      results: config.paths.results,
      reports: config.paths.reports,
    },
    workingToday: ["txt", "md"],
    plannedNext: ["xls", "xlsx", "docx", "pdf"],
  };
}

async function saveComparisonResult(record) {
  const targetPath = path.join(config.paths.results, `${record.id}.json`);
  await writeBufferToFile(targetPath, Buffer.from(JSON.stringify(record, null, 2)));
}

async function handleComparePlan(req, res) {
  try {
    const body = await readJsonBody(req);
    const fileA = planParsing(body.fileA || {});
    const fileB = planParsing(body.fileB || {});
    const comparison = planComparison(fileA, fileB);

    sendJson(res, 200, {
      ok: true,
      fileA,
      fileB,
      comparison,
      note: "This endpoint currently plans the comparison flow. Real uploads and parsing are the next implementation step.",
    });
  } catch (error) {
    sendJson(res, 400, {
      ok: false,
      error: "Invalid JSON request body.",
    });
  }
}

async function handleCompare(req, res) {
  try {
    const { files } = await parseMultipart(req);
    const uploadA = files.fileA;
    const uploadB = files.fileB;

    if (!uploadA || !uploadB) {
      sendJson(res, 400, {
        ok: false,
        error: "Please upload both fileA and fileB.",
      });
      return;
    }

    const fileA = planParsing({ name: uploadA.filename, size: uploadA.size });
    const fileB = planParsing({ name: uploadB.filename, size: uploadB.size });
    const comparisonPlan = planComparison(fileA, fileB);

    if (!fileA.format.supported || !fileB.format.supported) {
      sendJson(res, 400, {
        ok: false,
        error: "Unsupported format. Planned formats are xls, xlsx, txt, md, docx, and pdf.",
        fileA,
        fileB,
      });
      return;
    }

    if (!comparisonPlan.ready) {
      sendJson(res, 400, {
        ok: false,
        error: comparisonPlan.message,
        fileA,
        fileB,
        comparison: comparisonPlan,
      });
      return;
    }

    const documentFormats = ["txt", "md"];
    const spreadsheetFormats = ["xls", "xlsx"];

    if (
      comparisonPlan.mode === "document" &&
      !documentFormats.includes(fileA.format.extension)
    ) {
      sendJson(res, 501, {
        ok: false,
        error: "Document comparison for this format is planned but not implemented yet.",
        fileA,
        fileB,
        comparison: comparisonPlan,
      });
      return;
    }

    if (
      comparisonPlan.mode === "spreadsheet" &&
      !spreadsheetFormats.includes(fileA.format.extension)
    ) {
      sendJson(res, 501, {
        ok: false,
        error: "Spreadsheet comparison for this format is planned but not implemented yet.",
        fileA,
        fileB,
        comparison: comparisonPlan,
      });
      return;
    }

    if (!["document", "spreadsheet"].includes(comparisonPlan.mode)) {
      sendJson(res, 501, {
        ok: false,
        error: `${comparisonPlan.mode} comparison for these formats is planned but not implemented yet.`,
        fileA,
        fileB,
        comparison: comparisonPlan,
      });
      return;
    }

    const storedNameA = buildStoredFilename(uploadA.filename);
    const storedNameB = buildStoredFilename(uploadB.filename);
    await writeBufferToFile(path.join(config.paths.uploads, storedNameA), uploadA.buffer);
    await writeBufferToFile(path.join(config.paths.uploads, storedNameB), uploadB.buffer);

    const enrichedFileA = {
      ...fileA,
      buffer: uploadA.buffer,
      filename: uploadA.filename,
      storedFilename: storedNameA,
      sha256: sha256(uploadA.buffer),
    };
    const enrichedFileB = {
      ...fileB,
      buffer: uploadB.buffer,
      filename: uploadB.filename,
      storedFilename: storedNameB,
      sha256: sha256(uploadB.buffer),
    };

    const comparison = comparisonPlan.mode === "spreadsheet"
      ? compareSpreadsheets(parseSpreadsheetFile(enrichedFileA), parseSpreadsheetFile(enrichedFileB))
      : compareDocuments(parseDocumentFile(enrichedFileA), parseDocumentFile(enrichedFileB));

    const resultRecord = {
      id: createId(),
      createdAt: new Date().toISOString(),
      fileA: {
        name: enrichedFileA.filename,
        storedFilename: storedNameA,
        extension: enrichedFileA.format.extension,
        size: uploadA.size,
        sha256: enrichedFileA.sha256,
      },
      fileB: {
        name: enrichedFileB.filename,
        storedFilename: storedNameB,
        extension: enrichedFileB.format.extension,
        size: uploadB.size,
        sha256: enrichedFileB.sha256,
      },
      comparison,
    };

    await saveComparisonResult(resultRecord);

    sendJson(res, 200, {
      ok: true,
      resultId: resultRecord.id,
      fileA: resultRecord.fileA,
      fileB: resultRecord.fileB,
      comparison,
    });
  } catch (error) {
    sendJson(res, error.message === "PAYLOAD_TOO_LARGE" ? 413 : 400, {
      ok: false,
      error: error.message === "PAYLOAD_TOO_LARGE" ? "Upload is too large." : "Failed to process upload.",
    });
  }
}

async function handleGetComparison(req, res, id) {
  try {
    const targetPath = path.join(config.paths.results, `${id}.json`);
    const content = await fs.promises.readFile(targetPath, "utf8");
    sendJson(res, 200, JSON.parse(content));
  } catch (error) {
    sendJson(res, 404, {
      ok: false,
      error: "Comparison result not found.",
    });
  }
}

async function start() {
  await ensureDirectories();

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");

    if (req.method === "GET" && url.pathname === "/api/health") {
      sendJson(res, 200, {
        ok: true,
        service: config.appName,
        port: config.port,
      });
      return;
    }

    if (req.method === "GET" && url.pathname === "/api/capabilities") {
      sendJson(res, 200, buildCapabilities());
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/compare-plan") {
      await handleComparePlan(req, res);
      return;
    }

    if (req.method === "POST" && url.pathname === "/api/compare") {
      await handleCompare(req, res);
      return;
    }

    if (req.method === "GET" && url.pathname.startsWith("/api/compare/")) {
      const id = url.pathname.split("/").pop();
      await handleGetComparison(req, res, id);
      return;
    }

    if (req.method === "GET") {
      await serveStatic(req, res);
      return;
    }

    sendText(res, 404, "Not Found");
  });

  server.listen(config.port, config.host, () => {
    console.log(`${config.appName} listening on http://${config.host}:${config.port}`);
  });
}

start().catch((error) => {
  console.error("Failed to start server", error);
  process.exitCode = 1;
});
