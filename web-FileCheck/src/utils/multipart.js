const { Buffer } = require("buffer");

function parseHeaders(rawHeaders) {
  const headers = {};
  for (const line of rawHeaders.split("\r\n")) {
    const separatorIndex = line.indexOf(":");
    if (separatorIndex === -1) {
      continue;
    }
    const key = line.slice(0, separatorIndex).trim().toLowerCase();
    const value = line.slice(separatorIndex + 1).trim();
    headers[key] = value;
  }
  return headers;
}

function parseContentDisposition(value) {
  const output = {};
  const segments = String(value || "").split(";").map((segment) => segment.trim());
  output.type = segments.shift() || "";

  for (const segment of segments) {
    const eqIndex = segment.indexOf("=");
    if (eqIndex === -1) {
      continue;
    }
    const key = segment.slice(0, eqIndex).trim();
    const rawValue = segment.slice(eqIndex + 1).trim();
    output[key] = rawValue.replace(/^"|"$/g, "");
  }

  return output;
}

async function readRequestBuffer(req, maxBytes) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let total = 0;

    req.on("data", (chunk) => {
      total += chunk.length;
      if (total > maxBytes) {
        reject(new Error("PAYLOAD_TOO_LARGE"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });

    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

async function parseMultipart(req, maxBytes = 25 * 1024 * 1024) {
  const contentType = String(req.headers["content-type"] || "");
  const match = contentType.match(/boundary=(?:"([^"]+)"|([^;]+))/i);
  if (!match) {
    throw new Error("MISSING_MULTIPART_BOUNDARY");
  }

  const boundary = Buffer.from(`--${match[1] || match[2]}`);
  const body = await readRequestBuffer(req, maxBytes);
  const segments = [];
  let cursor = 0;

  while (cursor < body.length) {
    const boundaryIndex = body.indexOf(boundary, cursor);
    if (boundaryIndex === -1) {
      break;
    }

    const nextStart = boundaryIndex + boundary.length;
    const nextTwo = body.subarray(nextStart, nextStart + 2).toString("utf8");
    if (nextTwo === "--") {
      break;
    }

    const partStart = nextStart + 2;
    const nextBoundaryIndex = body.indexOf(boundary, partStart);
    if (nextBoundaryIndex === -1) {
      break;
    }

    const partBuffer = body.subarray(partStart, nextBoundaryIndex - 2);
    segments.push(partBuffer);
    cursor = nextBoundaryIndex;
  }

  const files = {};
  const fields = {};

  for (const partBuffer of segments) {
    const headerEnd = partBuffer.indexOf(Buffer.from("\r\n\r\n"));
    if (headerEnd === -1) {
      continue;
    }

    const headerText = partBuffer.subarray(0, headerEnd).toString("utf8");
    const content = partBuffer.subarray(headerEnd + 4);
    const headers = parseHeaders(headerText);
    const disposition = parseContentDisposition(headers["content-disposition"]);
    const fieldName = disposition.name;

    if (!fieldName) {
      continue;
    }

    if (disposition.filename) {
      files[fieldName] = {
        fieldName,
        filename: disposition.filename,
        contentType: headers["content-type"] || "application/octet-stream",
        buffer: content,
        size: content.length,
      };
      continue;
    }

    fields[fieldName] = content.toString("utf8");
  }

  return { files, fields };
}

module.exports = {
  parseMultipart,
};
