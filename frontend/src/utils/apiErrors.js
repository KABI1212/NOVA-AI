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

const formatStatusFallback = (error, fallback) => {
  const status = error?.response?.status;
  const requestUrl = String(error?.config?.url || "").trim();
  const isAuthRequest =
    requestUrl.includes("/auth/login") ||
    requestUrl.includes("/auth/signup") ||
    requestUrl.includes("/auth/login/otp") ||
    requestUrl.includes("/auth/password/forgot") ||
    requestUrl.includes("/auth/password/reset");

  if (status === 404 && isAuthRequest) {
    return "Auth API route was not found. Check that VITE_API_URL points to your backend service and that the backend deployment is live.";
  }

  if (status === 401 && requestUrl.includes("/auth/login")) {
    return "Login failed. Check the email and password, or complete OTP verification if the account was just created.";
  }

  if (status === 503) {
    if (isAuthRequest) {
      return "The backend could not send the verification email right now. Check your Render SMTP settings and backend logs.";
    }

    return "The server is temporarily unavailable. Please try again in a moment.";
  }

  return fallback;
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
    formatStatusFallback(error, null) ||
    normalizeText(error?.message) ||
    fallback
  );
};
