function createLookup(items, selector) {
  const map = new Map();
  for (const item of items) {
    const key = selector(item);
    if (!key) {
      continue;
    }
    map.set(key, item);
  }
  return map;
}

function compareParagraphs(paragraphsA, paragraphsB) {
  const mapA = createLookup(paragraphsA, (item) => item);
  const mapB = createLookup(paragraphsB, (item) => item);
  const added = [];
  const removed = [];

  for (const paragraph of paragraphsB) {
    if (!mapA.has(paragraph)) {
      added.push(paragraph);
    }
  }

  for (const paragraph of paragraphsA) {
    if (!mapB.has(paragraph)) {
      removed.push(paragraph);
    }
  }

  return { added, removed };
}

function compareSections(sectionsA, sectionsB) {
  const indexedA = createLookup(sectionsA, (section) => `${section.level}:${section.heading}`);
  const indexedB = createLookup(sectionsB, (section) => `${section.level}:${section.heading}`);
  const keys = new Set([...indexedA.keys(), ...indexedB.keys()]);
  const changed = [];

  for (const key of keys) {
    const sectionA = indexedA.get(key);
    const sectionB = indexedB.get(key);

    if (!sectionA || !sectionB) {
      changed.push({
        key,
        heading: sectionA?.heading || sectionB?.heading || "Untitled",
        status: sectionA ? "removed" : "added",
        textA: sectionA?.text || "",
        textB: sectionB?.text || "",
      });
      continue;
    }

    if (sectionA.text !== sectionB.text) {
      changed.push({
        key,
        heading: sectionA.heading,
        status: "changed",
        textA: sectionA.text,
        textB: sectionB.text,
      });
    }
  }

  return changed;
}

function compareDocuments(parsedA, parsedB) {
  const paragraphDiff = compareParagraphs(parsedA.paragraphs, parsedB.paragraphs);
  const sectionDiffs = compareSections(parsedA.sections, parsedB.sections);

  return {
    mode: "document",
    summary: {
      paragraphsA: parsedA.paragraphs.length,
      paragraphsB: parsedB.paragraphs.length,
      sectionsA: parsedA.sections.length,
      sectionsB: parsedB.sections.length,
      addedParagraphs: paragraphDiff.added.length,
      removedParagraphs: paragraphDiff.removed.length,
      changedSections: sectionDiffs.length,
    },
    addedParagraphs: paragraphDiff.added,
    removedParagraphs: paragraphDiff.removed,
    sectionDiffs,
    warnings: [...parsedA.warnings, ...parsedB.warnings],
  };
}

module.exports = {
  compareDocuments,
};
