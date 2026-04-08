const normalizeText = (value) => {
  const text = String(value || "").trim();
  return text || null;
};

const formatLocation = (loc) => {
  if (!Array.isArray(loc) || !loc.length) {
    return null;
  }

  const parts = loc
    .map((item) => normalizeText(item))
    .filter(Boolean)
    .filter((item) => item !== "body" && item !== "query" && item !== "path");

  if (!parts.length) {
    return null;
  }

  return parts.join(".");
};

const formatDetailItem = (item) => {
  if (!item) {
    return null;
  }

  if (typeof item === "string") {
    return normalizeText(item);
  }

  if (typeof item === "object") {
    const message =
      normalizeText(item.msg) ||
      normalizeText(item.message) ||
      normalizeText(item.detail) ||
      normalizeText(item.error);
    const location = formatLocation(item.loc);

    if (location && message) {
      return `${location}: ${message}`;
    }

    if (message) {
      return message;
    }
  }

  return null;
};

export const formatApiError = (error, fallback = "Something went wrong.") => {
  const responseData = error?.response?.data;
  const detail = responseData?.detail;
  const message = responseData?.message;

  if (Array.isArray(detail)) {
    const formatted = detail.map(formatDetailItem).filter(Boolean);
    if (formatted.length) {
      return formatted.join("; ");
    }
  }

  if (detail && typeof detail === "object") {
    const formatted = formatDetailItem(detail);
    if (formatted) {
      return formatted;
    }
  }

  return (
    normalizeText(detail) ||
    normalizeText(message) ||
    normalizeText(error?.message) ||
    fallback
  );
};
