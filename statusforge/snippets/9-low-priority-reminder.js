// Optional workflow "Roadmap Low-Priority Reminder" — Code: "Build Low-Priority Reminder"
// Mode: Run Once for All Items. Reads the Airtable Search records output directly.
//
// DETERMINISTIC BY DESIGN: a backlog list is pure data formatting, so there is NO LLM
// call here. We only spend a model call when we need narrative/ranking (the daily
// digest). Listing Low-priority items is code's job — cheaper, and it can't hallucinate
// a task that isn't on the roadmap. Runs on its own WEEKLY schedule to avoid the daily
// notification fatigue a slow-changing backlog list would create.

const REQUIRED = ['Feature', 'Priority', 'Owner'];
const items = $input.all();

const low = [];
for (const item of items) {
  const f = item.json.fields ?? item.json; // Airtable v1 nests under "fields", v2 flattens
  const missing = REQUIRED.filter(
    (k) => f[k] === undefined || f[k] === null || String(f[k]).trim() === ''
  );
  if (missing.length === 0 && f['Priority'] === 'Low') {
    low.push({
      itemId: f['Item ID'] ?? item.json.id,
      feature: f['Feature'],
      owner: f['Owner'],
      targetQuarter: f['Target Quarter'] ?? '',
    });
  }
}

let text;
if (low.length === 0) {
  text = '⏰ *Low-priority backlog reminder* — nothing on the back burner this week. 🎉';
} else {
  const lines = low
    .map((r) => `•  ${r.feature}  (\`${r.itemId}\` • ${r.owner}${r.targetQuarter ? ' • ' + r.targetQuarter : ''})`)
    .join('\n');
  text = `⏰ *Low-priority backlog reminder* — ${low.length} item(s) on the back burner:\n${lines}`;
}

return [{ json: { lowCount: low.length, lowItems: low, text } }];
