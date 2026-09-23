// Node 3 — Code: "Validate + Count"  (Mode: Run Once for All Items)
// Deterministic validation + counting + staleness + change-detection. No LLM — this is
// the source of truth for every number and decision downstream.

const REQUIRED = ['Feature', 'Priority', 'Status', 'Owner'];
const KNOWN_PRIORITIES = ['high', 'medium', 'low'];
const KNOWN_STATUSES = ['in progress', 'not started', 'blocked'];
const STALE_DAYS = 14; // not updated in this many days => "stale"

const items = $input.all();
if (items.length === 0) {
  throw new Error('Airtable returned 0 records — aborting digest run.');
}

const now = new Date();

// Robust date parsing: accepts YYYY-MM-DD (Airtable/ISO) and DD-MM-YYYY / DD/MM/YYYY.
function daysSince(dateStr) {
  if (!dateStr) return null;
  const s = String(dateStr).trim();
  let d;
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    d = new Date(s);
  } else {
    const m = s.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
    d = m ? new Date(`${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`) : new Date(s);
  }
  return isNaN(d) ? null : Math.floor((now - d) / 86400000);
}

const valid = [];
const skipped = [];

for (const item of items) {
  const raw = item.json;
  const f = raw.fields ?? raw; // Airtable v1 nests under "fields", v2 flattens

  const missing = REQUIRED.filter(
    (k) => f[k] === undefined || f[k] === null || String(f[k]).trim() === ''
  );
  if (missing.length > 0) {
    skipped.push({ itemId: f['Item ID'] ?? raw.id ?? 'unknown', reason: 'missing: ' + missing.join(', ') });
    continue;
  }

  // Normalize once, validate against known enums — tolerant of case/whitespace typos.
  const priorityKey = String(f['Priority']).trim().toLowerCase();
  const statusKey = String(f['Status']).trim().toLowerCase();
  if (!KNOWN_PRIORITIES.includes(priorityKey)) {
    skipped.push({ itemId: f['Item ID'] ?? raw.id, reason: `unknown priority "${f['Priority']}"` });
    continue;
  }
  if (!KNOWN_STATUSES.includes(statusKey)) {
    skipped.push({ itemId: f['Item ID'] ?? raw.id, reason: `unknown status "${f['Status']}"` });
    continue;
  }

  const lastUpdated = f['Last Updated'] ?? '';
  const days = daysSince(lastUpdated);
  valid.push({
    itemId: f['Item ID'] ?? raw.id,
    recordId: raw.id ?? '', // Airtable rec... id, for deep links in Build Slack Blocks
    feature: f['Feature'],
    status: f['Status'], // original casing for display
    statusKey, // normalized for logic
    priority: f['Priority'],
    priorityKey, // normalized for logic
    owner: f['Owner'],
    targetQuarter: f['Target Quarter'] ?? '',
    description: f['Description'] ?? '',
    lastUpdated,
    daysSinceUpdate: days,
    stale: days !== null && days > STALE_DAYS,
  });
}

if (valid.length === 0) {
  throw new Error('All records failed field validation — aborting digest run.');
}

const highItems = valid.filter((r) => r.priorityKey === 'high');
const blockedItems = valid.filter((r) => r.statusKey === 'blocked');
const staleItems = valid.filter((r) => r.stale);
const highCount = highItems.length;

const statusDistribution = {};
for (const r of valid) statusDistribution[r.status] = (statusDistribution[r.status] ?? 0) + 1;

return [
  {
    json: {
      records: valid,
      recordCount: valid.length,
      skippedCount: skipped.length,
      skipped,
      highCount,
      blockedCount: blockedItems.length,
      blockedIds: blockedItems.map((r) => r.itemId),
      staleCount: staleItems.length,
      staleIds: staleItems.map((r) => r.itemId),
      statusDistribution,
      mentionHere: highCount > 5, // deterministic @here decision
      runTimestamp: now.toISOString(),
    },
  },
];
