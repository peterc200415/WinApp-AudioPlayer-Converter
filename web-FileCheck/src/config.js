const path = require("path");

function resolvePath(value, fallback) {
  return path.resolve(process.cwd(), value || fallback);
}

const config = {
  appName: process.env.APP_NAME || "web-FileCheck",
  host: process.env.HOST || "0.0.0.0",
  port: Number.parseInt(process.env.PORT || "4000", 10),
  dataRoot: resolvePath(process.env.DATA_ROOT, "./storage"),
  paths: {
    uploads: resolvePath(process.env.UPLOADS_DIR, "./storage/uploads"),
    results: resolvePath(process.env.RESULTS_DIR, "./storage/results"),
    reports: resolvePath(process.env.REPORTS_DIR, "./storage/reports"),
  },
};

module.exports = config;
