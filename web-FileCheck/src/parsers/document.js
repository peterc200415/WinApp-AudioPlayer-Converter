const mammoth = require("mammoth");
const { PdfReader } = require("pdfreader");

function splitParagraphs(text) {
  return String(text || "")
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function extractMarkdownSections(text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  const sections = [];
  let current = { heading: "Introduction", level: 0, content: [] };

  for (const line of lines) {
    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      if (current.content.length || current.heading) {
        sections.push({
          heading: current.heading,
          level: current.level,
          text: current.content.join("\n").trim(),
        });
      }
      current = {
        heading: headingMatch[2].trim(),
        level: headingMatch[1].length,
        content: [],
      };
      continue;
    }
    current.content.push(line);
  }

  if (current.content.length || current.heading) {
    sections.push({
      heading: current.heading,
      level: current.level,
      text: current.content.join("\n").trim(),
    });
  }

  return sections.filter((section) => section.heading || section.text);
}

function buildSections(extension, normalizedText) {
  if (extension === "md") {
    return extractMarkdownSections(normalizedText);
  }

  return [{ heading: "Document", level: 0, text: normalizedText }];
}

async function extractTextFromFile(file) {
  const extension = file.format.extension;

  if (extension === "txt" || extension === "md") {
    return {
      text: file.buffer.toString("utf8"),
      warnings: [],
    };
  }

  if (extension === "docx") {
    const result = await mammoth.extractRawText({ buffer: file.buffer });
    return {
      text: result.value || "",
      warnings: (result.messages || []).map((message) => message.message || String(message)),
    };
  }

  if (extension === "pdf") {
    const text = await extractPdfText(file.buffer);
    const warnings = [];
    if (!String(text || "").trim()) {
      warnings.push("No extractable text found in PDF. Scanned PDFs may require OCR.");
    }
    return { text, warnings };
  }

  throw new Error(`Unsupported document parser for .${extension}`);
}

function extractPdfText(buffer) {
  return new Promise((resolve, reject) => {
    const pages = [];
    let currentPage = new Map();

    new PdfReader().parseBuffer(buffer, (error, item) => {
      if (error) {
        reject(error);
        return;
      }

      if (!item) {
        if (currentPage.size > 0) {
          pages.push(currentPage);
        }

        const pageTexts = pages.map((pageMap) => {
          const rows = Array.from(pageMap.entries())
            .sort((a, b) => Number(a[0]) - Number(b[0]))
            .map(([, rowItems]) => rowItems.join(" ").trim())
            .filter(Boolean);
          return rows.join("\n");
        });

        resolve(pageTexts.filter(Boolean).join("\n\n"));
        return;
      }

      if (item.page) {
        if (currentPage.size > 0) {
          pages.push(currentPage);
        }
        currentPage = new Map();
        return;
      }

      if (item.text) {
        const key = item.y != null ? item.y.toFixed(2) : "0.00";
        const row = currentPage.get(key) || [];
        row.push(String(item.text));
        currentPage.set(key, row);
      }
    });
  });
}

async function parseDocumentFile(file) {
  const extension = file.format.extension;
  const extracted = await extractTextFromFile(file);
  const normalizedText = String(extracted.text || "").replace(/\r\n/g, "\n").trim();
  const paragraphs = splitParagraphs(normalizedText);
  const sections = buildSections(extension, normalizedText);

  return {
    contentType: "document",
    rawText: normalizedText,
    paragraphs,
    sections,
    warnings: extracted.warnings || [],
    metrics: {
      characters: normalizedText.length,
      lines: normalizedText ? normalizedText.split("\n").length : 0,
      paragraphs: paragraphs.length,
      sections: sections.length,
    },
  };
}

module.exports = {
  parseDocumentFile,
};
