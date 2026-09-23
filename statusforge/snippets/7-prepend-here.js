// Node 8 (true branch only) — Code: "Prepend @here"  (Mode: Run Once for All Items)
// Slack gotcha: the literal token <!here> triggers the notification.
// The plain string "@here" posts as inert text and notifies nobody.

const j = $input.first().json;

const blocks = [
  {
    type: 'section',
    text: {
      type: 'mrkdwn',
      text: `<!here> *${j.highCount} items are High priority — attention needed.*`,
    },
  },
  ...j.blocks,
];

return [
  {
    json: {
      ...j,
      blocks,
      blocksJson: JSON.stringify({ blocks }),
      notificationText: `@here ${j.notificationText}`,
    },
  },
];
