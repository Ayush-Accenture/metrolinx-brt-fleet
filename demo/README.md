# PDS Agentic Operations — Dashboard (Demo)

A self-contained, static **mock UI** for the PDS Agentic Operations
*Fleet Information Management* pipeline. It visualizes the automated nightly
DVA (Device Vehicle Allocation) processing flow and its **human-in-the-loop
(HITL)** approval gates.

> This is a front-end demo only — there is no backend. All data is mock data
> defined in [`js/data.js`](js/data.js). The HITL approval buttons animate the
> pipeline forward to demonstrate the end-to-end flow.

## Project structure

```
demo/
├── index.html                 # Markup + page shell
├── css/
│   └── styles.css             # All styles (design-token based, light SaaS theme)
├── js/
│   ├── data.js                # Pipeline stages, detail cards, HITL panel content
│   └── app.js                 # UI logic (render, scroll, HITL flow, a11y)
├── package.json               # Local dev-server script
├── staticwebapp.config.json   # Azure Static Web Apps config (routing/headers)
├── .gitignore
└── README.md
```

## Run locally

It's a static site, so you can open `index.html` directly in a browser —
**or** serve it (recommended, avoids any `file://` quirks):

```bash
# from the demo/ folder
npm start
# → serves at http://localhost:5173
```

Any static file server works equally well, e.g.:

```bash
python -m http.server 5173      # Python 3
npx --yes serve -l 5173 .       # Node
```

## Deploy

The site is 100% static — no build step. Point any static host at the
`demo/` folder.

| Host | How |
|------|-----|
| **Azure Static Web Apps** | App location: `demo` · Output location: *(leave blank)* · No build command. `staticwebapp.config.json` is already included. |
| **Netlify** | Publish directory: `demo` · Build command: *(none)* |
| **Vercel** | Root directory: `demo` · Framework preset: *Other* · No build. |
| **GitHub Pages** | Push `demo/` contents to the Pages branch/root. |

### Notes
- The **Inter** font loads from Google Fonts; offline it falls back to
  Segoe UI / system fonts gracefully.
- The favicon is an inline SVG data-URI (no extra request).
- Responsive down to mobile; the HITL panel goes full-width on small screens.
- Honors `prefers-reduced-motion` and supports keyboard use
  (Esc closes the panel, visible focus rings).

## Customizing the data

Edit [`js/data.js`](js/data.js):
- `STEPS` — the 12 pipeline stages (icon, label, state, HITL flag).
- `DETAILS` — the card shown when a stage is clicked.
- `PANELS` — the HITL slide-over content for gates HITL-2/3/4.
