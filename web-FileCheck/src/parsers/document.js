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

function parseDocumentFile(file) {
  const extension = file.format.extension;
  const text = file.buffer.toString("utf8");
  const normalizedText = text.replace(/\r\n/g, "\n").trim();
  const paragraphs = splitParagraphs(normalizedText);
  const sections = extension === "md"
    ? extractMarkdownSections(normalizedText)
    : [{ heading: "Document", level: 0, text: normalizedText }];

  return {
    contentType: "document",
    rawText: normalizedText,
    paragraphs,
    sections,
    warnings: [],
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
