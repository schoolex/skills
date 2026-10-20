# Explorer features

Reference for step 3 of [SKILL.md](SKILL.md). The worked example is `prototypes/posthog-event-graph.html` on the tcs-ui `prototypes` branch: an event graph with 119 nodes and 115 links. When in doubt, copy its structure.

## Non-negotiables

1. **One file, no network.** Inline CSS and JS, no CDN, no framework. It must open by double-click from the branch years from now.
2. **Data untouched.** The data block is sliced from the source, and the app reads it as it is. Validate it on load (for example, warn on edges that point at unknown nodes).
3. **Full-viewport app layout.** CSS grid: top bar (title, live counts, search, theme) / left sidebar (filters, legend, shortcuts) / canvas / right detail drawer that slides in. No page scroll; the canvas pans.
4. **Surface the state.** A live count in the header ("92 of 119 events · 69 links · 3 match") that updates on every filter, search or selection.
5. **Readable by default.** Start at "fit to width, top-aligned", not "fit everything". Offer fit-all as a second action (Shift+F).

## Canvas (SVG graphs and diagrams)

- Pan and zoom by setting a `transform` on one `<g>` world group, not by changing the scroll position. Zoom around the cursor. Plain scroll pans; pinch or Ctrl/Cmd+scroll zooms. Drag to pan, with a 3px threshold so a click is never treated as a drag.
- Floating zoom controls (+, −, fit, a percentage readout) in the bottom-right corner.
- A minimap in the bottom-left corner, sized from the content's aspect ratio and capped at about 180px tall, showing a viewport rectangle; click it to jump. Check the screenshot to make sure it doesn't cover content.
- `centerOn(id)` and `focusArea(id)` that ease the camera over about 280ms.
- Hover tooltip: the name, a one-line description, and counts.

## Finding things

- Search with a results dropdown: arrow keys move, Enter selects, Esc clears. Matches by name rank above matches in properties or text. Picking a result clears the query, so the selection drives the highlight.
- `/` focuses the search box. Don't intercept keys while an input has focus.
- Filter chips (source, kind) with counts; a chip that's off is dimmed and struck through.
- An area list in the sidebar: click an area to zoom to it, and use a show/hide control to remove it from the layout (re-run the layout, don't just hide it).

## Selection

- Selecting an item dims everything outside its neighbourhood. A depth control offers 1 hop, 2 hops and full path, walking upstream and downstream separately so "full path" shows the journey, not the whole graph. Animate the highlighted edges with a moving dash.
- Detail drawer: the name, source badge, area, the description, a properties table, and incoming and outgoing links as clickable jumps. A jump to a hidden item un-hides its area and filter first.
- Copy actions in the drawer: the name, and a query for the item in the data's query language (for PostHog, HogQL: `SELECT timestamp, distinct_id, properties.<each prop> FROM events WHERE event = '<id>'`).

## Shareability

- Keep filters, hidden areas and the selection in the URL hash (`#e=<id>&hide=a,b&src=1,2`), and restore them on load. A link to the file opens on the same view.
- Light and dark themes with CSS variables, a `T` shortcut, and the choice kept in `localStorage` (wrapped in try/catch, since `file://` can throw).
- Shortcuts: `/` search, `Esc` clear, `F` fit, `+`/`−` zoom, `T` theme. List them in the sidebar.

## Tabular or list data (no canvas)

Keep the same layout. Swap the canvas for a virtualised or grouped list with sticky group headers. The search, chips, drawer, hash state and live counts stay the same.
