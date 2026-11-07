// Export the member list of a Facebook group to CSV.
//
// Facebook has no export for group members and no longer has a Groups API, so this reads
// the member links from the group's People page in the browser.
//
// Usage:
//   1. As a group admin, open https://www.facebook.com/groups/<group>/members in a desktop
//      browser.
//   2. Open DevTools (F12), go to the Console tab, paste this whole file and press Enter.
//      Chrome may ask you to type "allow pasting" first.
//   3. Leave the tab in front. The script scrolls to the bottom repeatedly until no new
//      members load, then downloads fb_group_members.csv.
//   4. Compare the count it prints with the member count Facebook shows at the top of the
//      page. If it stopped short, raise PAUSE_MS or IDLE_ROUNDS and run it again.
//
// Output columns: name, facebook_id, profile_url
//
// Each member's link on the People page looks like /groups/<group id>/user/<user id>/.
// People can appear in more than one section (admins, new members, the full list), so rows
// are de-duplicated on the user id. If Facebook changes these links, the selector below is
// what needs updating.

(async () => {
  const PAUSE_MS = 2000;   // wait after each scroll for the next batch to load
  const IDLE_ROUNDS = 8;   // stop after this many scrolls with no new members

  const members = new Map();

  const collect = () => {
    for (const a of document.querySelectorAll('a[href*="/user/"]')) {
      const m = a.href.match(/\/groups\/[^/]+\/user\/(\d+)/);
      if (!m) continue;
      const id = m[1];
      // the avatar link has no text; the name link does
      const name = (a.innerText || a.getAttribute('aria-label') || '').split('\n')[0].trim();
      const prev = members.get(id);
      if (!prev) {
        members.set(id, { name, id, url: `https://www.facebook.com/profile.php?id=${id}` });
      } else if (!prev.name && name) {
        prev.name = name;
      }
    }
  };

  let idle = 0;
  let last = 0;
  while (idle < IDLE_ROUNDS) {
    collect();
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise((r) => setTimeout(r, PAUSE_MS));
    collect();
    if (members.size === last) {
      idle++;
    } else {
      idle = 0;
      last = members.size;
      console.log(`${members.size} members so far`);
    }
  }

  const q = (s) => `"${String(s).replace(/"/g, '""')}"`;
  const rows = [['name', 'facebook_id', 'profile_url']];
  for (const m of members.values()) rows.push([m.name, m.id, m.url]);
  const csv = rows.map((r) => r.map(q).join(',')).join('\r\n') + '\r\n';

  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  link.download = 'fb_group_members.csv';
  document.body.appendChild(link);
  link.click();
  link.remove();

  const noname = [...members.values()].filter((m) => !m.name).length;
  console.log(`done: ${members.size} members exported, ${noname} without a name`);
})();
