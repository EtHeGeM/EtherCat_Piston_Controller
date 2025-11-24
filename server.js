/**
 * Simple static server: serves animated presentation and landing pages from web/
 * for localhost or LAN sharing.
 *
 * Run: HOST=0.0.0.0 PORT=3000 node server.js
 * Defaults: host 0.0.0.0, port 3000, root web/, default page presentation.html
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const url = require("url");

const ROOT = path.join(__dirname, "web");
const DEFAULT_FILE = "presentation.html";
const HOST = process.env.HOST || "0.0.0.0";
const PORT = parseInt(process.env.PORT || "3000", 10);

const MIME_MAP = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

function safeFilePath(requestPath) {
  const { pathname } = url.parse(requestPath);
  if (!pathname) return null;
  const decoded = decodeURIComponent(pathname);
  const target = decoded === "/" ? DEFAULT_FILE : decoded.replace(/^\//, "");
  const normalized = path.normalize(target);
  // Prevent path escape
  if (normalized.includes("..")) return null;
  return path.join(ROOT, normalized);
}

function serveFile(filePath, res) {
  fs.stat(filePath, (err, stat) => {
    if (err || !stat.isFile()) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("404 Not Found");
      return;
    }
    const ext = path.extname(filePath);
    const mime = MIME_MAP[ext] || "application/octet-stream";
    res.writeHead(200, {
      "Content-Type": mime,
      "Cache-Control": "public, max-age=3600",
    });
    fs.createReadStream(filePath).pipe(res);
  });
}

const server = http.createServer((req, res) => {
  const filePath = safeFilePath(req.url || "");
  if (!filePath) {
    res.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("400 Bad Request");
    return;
  }
  serveFile(filePath, res);
});

server.listen(PORT, HOST, () => {
  console.log(`Hydraulic HMI presentation served at http://${HOST}:${PORT}`);
  console.log(`- Default: / (presentation.html)`);
  console.log(`- Landing: /index.html`);
});
