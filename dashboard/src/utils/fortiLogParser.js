const FIELD_START = /(?:^|\s)([A-Za-z][A-Za-z0-9_]*)=/g;

function decodeMessage(value = "") {
  try {
    return decodeURIComponent(String(value).replace(/\+/g, "%20"));
  } catch {
    return String(value);
  }
}

/** Parse FortiAnalyzer key=value logs while preserving values that contain spaces. */
export function parseFortiAnalyzerLog(raw, index = 0) {
  const text = String(raw ?? "").trim();
  const matches = [...text.matchAll(FIELD_START)];
  const fields = {};

  matches.forEach((match, matchIndex) => {
    const valueStart = match.index + match[0].length;
    const valueEnd = matches[matchIndex + 1]?.index ?? text.length;
    let value = text.slice(valueStart, valueEnd).trim();

    // Some FortiAnalyzer values are quoted; remove only the surrounding pair.
    if (
      value.length >= 2 &&
      ((value.startsWith("'") && value.endsWith("'")) ||
        (value.startsWith('"') && value.endsWith('"')))
    ) {
      value = value.slice(1, -1);
    }

    fields[match[1]] = value;
  });

  const message = decodeMessage(fields.msg ?? "");
  const operation = fields.operation ?? "";
  const isPerformance =
    operation.toLowerCase().includes("perf") ||
    message.toLowerCase().includes("system performance status");
  const isAdminLogin =
    operation.toLowerCase() === "login" ||
    /user\s+'.+'\s+with profile/i.test(message);

  const perf = (pattern) => {
    const result = message.match(pattern);
    return result ? Number(result[1]) : null;
  };

  const date = fields.itime ?? fields.dtime ?? fields.date ?? null;

  return {
    id: fields.id ?? fields.log_id ?? `FAZ-${index + 1}`,
    fields,
    raw: text,
    message,
    date,
    device: fields.devname ?? fields.devid ?? "FortiAnalyzer",
    level: fields.level ?? "unknown",
    operation: operation || "Événement système",
    category: isPerformance
      ? "Performance système"
      : isAdminLogin
        ? "Connexion administrateur"
        : fields.subtype ?? fields.type ?? "Autre log",
    kind: isPerformance ? "performance" : isAdminLogin ? "admin" : "generic",
    metrics: isPerformance
      ? {
          logRate: perf(/log\s*rate\s*low\s*\(([\d.]+)%\)/i),
          logsPerSecond: perf(/lograte=([\d.]+)\/sec/i),
          cpu: perf(/CPU\s+usage\s*\(([\d.]+)%\)/i),
          memory: perf(/Memory\s+usage\s*\(([\d.]+)%\)/i),
          disk: perf(/Disk\s+usage\s*\(([\d.]+)%\)/i),
          insertRate: perf(/insertrate=([\d.]+)\/sec/i),
          messageRate: perf(/msgrate=([\d.]+)\/sec/i),
        }
      : null,
  };
}
