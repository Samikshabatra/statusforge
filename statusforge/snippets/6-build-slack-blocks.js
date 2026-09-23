// Node 6 — Code: "Build Slack Blocks"  (Mode: Run Once for All Items)
// Counts come from Validate + Count (deterministic); prose from the validated LLM output.
// Adds: Airtable deep-links, owner @-mentions on blocked items, and a "changes since
// yesterday" delta section.

const digest = $input.first().json;
const counts = $('Validate + Count').first().json;

// ---- CONFIG (hardcoded here for the demo; in production these belong in n8n Static
//      Data or environment variables, not the Code node). Base/table id are the
//      appXXXX/tblXXXX parts of the Airtable URL. -----------------------------------
const AIRTABLE_BASE = 'appeluaViGRDZJKDQ';
const AIRTABLE_TABLE = 'tbl5oMK0fmzpVHCtW';
// Owner -> Slack member id. In production this is a lookup table (Static Data / a Config
// node). The sample roadmap's owners are fictional, so one is mapped to a real member id
// for the demo; unmapped owners fall back to their plain name.
const OWNER_SLACK_IDS = {
  'Ravi T': 'U0BEYUAAAHG',
};

const byId = {};
for (const r of counts.records) byId[r.itemId] = r;

const linkable = AIRTABLE_BASE.startsWith('app') && !AIRTABLE_BASE.includes('XXXX');
function link(itemId, feature) {
  const rec = byId[itemId];
  return linkable && rec && rec.recordId
    ? `<https://airtable.com/${AIRTABLE_BASE}/${AIRTABLE_TABLE}/${rec.recordId}|${feature}>`
    : feature;
}
function ownerTag(owner) {
  return OWNER_SLACK_IDS[owner] ? `<@${OWNER_SLACK_IDS[owner]}>` : (owner || '—');
}

const blocks = [];
blocks.push({ type: 'header', text: { type: 'plain_text', text: '📋 Daily Roadmap Digest', emoji: true } });
blocks.push({
  type: 'context',
  elements: [{
    type: 'mrkdwn',
    text: `*${counts.recordCount}* items  •  🔥 *${counts.highCount}* High priority  •  ⛔ *${counts.blockedCount}* Blocked  •  🕒 *${counts.staleCount}* stale`,
  }],
});
blocks.push({ type: 'divider' });

blocks.push({ type: 'section', text: { type: 'mrkdwn', text: `*Executive Summary*\n${digest.executive_summary}` } });

// High priority
blocks.push({ type: 'divider' });
blocks.push({ type: 'section', text: { type: 'mrkdwn', text: `*🔥 High Priority (${counts.highCount})*` } });
digest.high_priority_items.forEach((it, i) => {
  const rec = byId[it.item_id];
  const staleFlag = rec && rec.stale ? '  🕒 _stale_' : '';
  blocks.push({
    type: 'section',
    text: {
      type: 'mrkdwn',
      text: `*${i + 1}. ${link(it.item_id, it.feature)}*  (\`${it.item_id}\` • ${it.owner || '—'} • ${it.target_quarter || '—'})${staleFlag}\n${it.why_it_matters}`,
    },
  });
});

// Blocked — @-mention the actual owner (accountability, not just broadcast)
if (digest.blocked_items.length > 0) {
  blocks.push({ type: 'divider' });
  blocks.push({ type: 'section', text: { type: 'mrkdwn', text: `*⛔ Blocked (${counts.blockedCount})*` } });
  digest.blocked_items.forEach((it) => {
    blocks.push({
      type: 'section',
      text: {
        type: 'mrkdwn',
        text: `*${link(it.item_id, it.feature)}*  (\`${it.item_id}\` • ${ownerTag(it.owner)})\nBlocker: ${it.blocker}\n➡️ ${it.suggested_action}`,
      },
    });
  });
}

// Recommendations
blocks.push({ type: 'divider' });
blocks.push({
  type: 'section',
  text: { type: 'mrkdwn', text: `*✅ Recommendations*\n${digest.recommendations.map((r) => `•  ${r}`).join('\n')}` },
});

// Footer
const dist = Object.entries(counts.statusDistribution).map(([k, v]) => `${k}: *${v}*`).join('   |   ');
let footer = `Generated ${counts.runTimestamp}`;
if (counts.skippedCount > 0) footer += `  •  ⚠️ ${counts.skippedCount} invalid record(s) skipped`;
blocks.push({ type: 'divider' });
blocks.push({ type: 'context', elements: [
  { type: 'mrkdwn', text: `Status — ${dist}` },
  { type: 'mrkdwn', text: footer },
] });

return [{
  json: {
    blocks,
    blocksJson: JSON.stringify({ blocks }),
    highCount: counts.highCount,
    blockedCount: counts.blockedCount,
    notificationText: `Daily Roadmap Digest — ${counts.highCount} High priority, ${counts.blockedCount} Blocked`,
  },
}];
