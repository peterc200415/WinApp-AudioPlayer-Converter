const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

function createId() {
  return crypto.randomBytes(8).toString("hex");
}

function sanitizeFilename(name) {
  return String(name || "file")
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
    .replace(/\s+/g, " ")
    .trim() || "file";
}

function buildStoredFilename(originalName) {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `${stamp}-${createId()}-${sanitizeFilename(originalName)}`;
}

async function writeBufferToFile(targetPath, buffer) {
  await fs.promises.mkdir(path.dirname(targetPath), { recursive: true });
  await fs.promises.writeFile(targetPath, buffer);
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

module.exports = {
  buildStoredFilename,
  createId,
  sanitizeFilename,
  sha256,
  writeBufferToFile,
};
