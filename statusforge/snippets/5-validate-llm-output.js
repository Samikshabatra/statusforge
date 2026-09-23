// Node 5 — Code: "Validate LLM Output"  (Mode: Run Once for All Items)
// Belt-and-braces check after the Structured Output Parser, plus a cross-check
// that the LLM listed exactly the items the deterministic counts say exist.
// Throws → workflow fails → error workflow alerts admin. Never post broken content.

const first = $input.first().json;

function fail(msg) {
  throw new Error('LLM output validation failed: ' + msg);
}

// The Structured Output Parser is bypassed (n8n bug #29903 throws "Failed to parse
// agent steps" even on valid output), so the chain returns the model's raw JSON text.
// Strip any markdown fences and parse it here. A parse failure is a hard failure that
// routes to the error workflow instead of posting garbage.
let out = first.output ?? first.text ?? first;
if (typeof out === 'string') {
  const cleaned = out.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim();
  try {
    out = JSON.parse(cleaned);
  } catch (e) {
    fail('model did not return valid JSON: ' + e.message);
  }
}

if (typeof out !== 'object' || out === null) fail('output is not an object');
if (typeof out.executive_summary !== 'string' || out.executive_summary.trim() === '')
  fail('executive_summary missing or empty');
if (!Array.isArray(out.high_priority_items)) fail('high_priority_items is not an array');
if (!Array.isArray(out.blocked_items)) fail('blocked_items is not an array');
if (!Array.isArray(out.recommendations) || out.recommendations.length === 0)
  fail('recommendations missing or empty');

for (const it of out.high_priority_items) {
  if (!it.item_id || !it.feature || !it.why_it_matters)
    fail('a high_priority_item is missing item_id/feature/why_it_matters');
}
for (const it of out.blocked_items) {
  if (!it.item_id || !it.feature || !it.blocker || !it.suggested_action)
    fail('a blocked_item is missing item_id/feature/blocker/suggested_action');
}

// Cross-check against deterministic counts — the LLM must not add or drop items
const counts = $('Validate + Count').first().json;
if (out.high_priority_items.length !== counts.highCount)
  fail(`LLM listed ${out.high_priority_items.length} high items, deterministic count is ${counts.highCount}`);
if (out.blocked_items.length !== counts.blockedCount)
  fail(`LLM listed ${out.blocked_items.length} blocked items, deterministic count is ${counts.blockedCount}`);

return [{ json: out }];
