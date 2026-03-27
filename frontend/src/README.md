# ArthAI — React Frontend Dashboard

A lightweight, real-time trading dashboard built with **React 18 + Vite**, connected to the ArthAI FastAPI backend. It provides live P&L, AI signal display, portfolio positions, an AI chat panel, and risk metrics — all auto-refreshing every 30 seconds.

> **Note:** The React frontend is an alternative to the Streamlit dashboard (`dashboard/`). Both connect to the same FastAPI backend (`server.py`). Use **Streamlit** for rapid local use; use **React** if you want a deployable, branded web app.

---

## Tech Stack

| Layer | Library | Version |
|-------|---------|---------|
| UI framework | React | 18.2 |
| Build tool | Vite | 5.1 |
| Charts | Recharts | 2.10 |
| HTTP client | Axios | 1.6 |
| Icons | Lucide React | 0.383 |
| CSS utilities | Tailwind CSS | 3.4 |
| Dev server proxy | Vite built-in | — |

---

## Project Structure

```
frontend/
├── index.html          ← HTML shell — mounts React into #root
├── vite.config.js      ← Vite config + dev proxy to FastAPI :8000
├── package.json        ← Dependencies and npm scripts
└── src/
    ├── main.jsx        ← React entry point — renders <App />
    ├── App.jsx         ← Full application — all pages, components, API calls
    └── index.css       ← Global styles — layout, cards, chat bubbles, tables
```

> All application code lives in `App.jsx` (single-file architecture). Split into separate component files as the project grows.

---

## Prerequisites

- **Node.js** 18+ — [nodejs.org](https://nodejs.org)
- **npm** 9+ (comes with Node)
- ArthAI **FastAPI backend** running on `http://localhost:8000`

---

## Quick Start

```bash
# 1. Navigate to the frontend directory
cd arthaai/frontend

# 2. Install dependencies
npm install

# 3. Start the dev server
npm run dev
```

Open **http://localhost:3000** in your browser.

The Vite dev server proxies `/api` and `/ws` to `http://localhost:8000` automatically — no CORS issues.

---

## Backend Requirement

The React frontend depends on the FastAPI backend. Start it first:

```bash
# From the arthaai/ root directory
python server.py
# → API available at http://localhost:8000
# → Swagger docs at http://localhost:8000/docs
```

Or using Docker Compose (starts both together):

```bash
docker compose up -d
```

---

## npm Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server with HMR on port 3000 |
| `npm run build` | Production build → `dist/` folder |
| `npm run preview` | Preview the production build locally |

---

## Pages & Features

The app is a single-page application with tab-based navigation:

### Portfolio Tab
- Summary metric cards — portfolio value, today's P&L, open positions, trade count
- Open positions table with live LTP, avg price, per-position P&L and P&L %
- Color-coded rows (green profit / red loss)

### Watchlist Tab
- Full 20-stock NSE watchlist fetched from `/api/watchlist`
- Displays LTP, signal (BUY/SELL/HOLD), confidence bar, entry/SL/target
- Signal badges color-coded: green = BUY, red = SELL, amber = HOLD

### AI Chat Tab
- Full chat interface connecting to `/api/chat` (Claude AI)
- Conversation history maintained in React state
- Quick-prompt buttons for common queries
- Typing indicator while waiting for Claude response
- Export chat as `.txt` via download button

### Risk Tab
- Four metric cards: total exposure, exposure %, total risk at stake, daily loss buffer %

---

## API Endpoints Used

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/portfolio` | GET | Open positions, today P&L, trade count |
| `/api/watchlist` | GET | All watchlist symbols with signals |
| `/api/chat` | POST | Claude AI chat — body: `{message, conversation_history}` |
| `/api/risk` | GET | Portfolio risk metrics |
| `/ws` | WebSocket | Live tick updates every 5 seconds |

Full API docs available at `http://localhost:8000/docs` when the backend is running.

---

## Configuration

### API Base URL

Defined at the top of `src/App.jsx`:

```js
const API = "http://localhost:8000";
```

For production, change this to your server URL or use an environment variable:

```js
const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
```

Then set it in a `.env` file:

```bash
# frontend/.env
VITE_API_URL=https://api.yourdomain.com
```

### Dev Proxy

`vite.config.js` proxies API calls in development so you don't hit CORS:

```js
server: {
  port: 3000,
  proxy: {
    "/api": "http://localhost:8000",
    "/ws":  { target: "ws://localhost:8000", ws: true },
  },
},
```

---

## Production Build

```bash
npm run build
```

This creates a `dist/` folder with optimised static assets. Serve it with any static file server:

```bash
# Using npx serve
npx serve dist

# Using Nginx (see deploy/nginx.conf)
# Copy dist/ to /var/www/arthaai/ and configure Nginx
```

### Nginx Static Serving

Add this block to your Nginx config to serve the React build alongside the API:

```nginx
# Serve React frontend
location / {
    root   /var/www/arthaai;
    index  index.html;
    try_files $uri $uri/ /index.html;   # SPA routing
}

# Proxy API to FastAPI
location /api/ {
    proxy_pass http://localhost:8000/api/;
}
```

---

## Docker

The root `docker-compose.yml` includes a service for the React build. To add the frontend container, extend it with:

```yaml
frontend:
  image: node:20-alpine
  working_dir: /app
  volumes:
    - ./frontend:/app
  command: sh -c "npm install && npm run build"
  # Build output is then served by Nginx
```

Or build a self-contained image:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
```

---

## Auto-Refresh

The dashboard auto-refreshes all data every **30 seconds** using `setInterval` in `useEffect`:

```js
useEffect(() => {
  refresh();
  const id = setInterval(refresh, 30_000);
  return () => clearInterval(id);
}, []);
```

The WebSocket connection at `/ws` additionally pushes live tick updates every 5 seconds (P&L, trade count, market status).

---

## Customisation

### Change the colour scheme

Edit CSS variables in `src/index.css`:

```css
:root {
  --green: #1D9E75;   /* Primary accent — change to your brand colour */
  --red:   #E24B4A;
  --blue:  #378ADD;
}
```

### Add a new page

1. Add a new tab button in the `tabs` array inside `App.jsx`
2. Add a new `{tab === "mytab" && <MyComponent />}` block in the JSX
3. Create your component as a function in `App.jsx` (or a new file imported into it)

### Connect to a different broker API

Change the API base URL and update the endpoint paths in the `refresh()` function and `sendMessage()` in `App.jsx`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Blank page after `npm run dev` | Check browser console — likely a JS import error |
| `ECONNREFUSED` on API calls | Start the FastAPI backend: `python server.py` |
| CORS errors | Ensure Vite proxy is configured in `vite.config.js` and you're accessing via `localhost:3000` not `localhost:8000` |
| Chat returns error | Add `ANTHROPIC_API_KEY` to the backend `.env` file |
| Stale data | Click the 🔄 Refresh button or wait for the 30s auto-refresh |
| `node_modules` missing | Run `npm install` inside the `frontend/` directory |
| Port 3000 already in use | Change `port: 3000` in `vite.config.js` to another port |

---

## Extending to Multiple Files (Recommended for Large Teams)

As the app grows, split `App.jsx` into separate component files:

```
src/
├── main.jsx
├── App.jsx              ← top-level routing only
├── api/
│   └── client.js        ← axios instance + all API calls
├── components/
│   ├── MetricCard.jsx
│   ├── SignalBadge.jsx
│   └── ChatPanel.jsx
├── pages/
│   ├── Portfolio.jsx
│   ├── Watchlist.jsx
│   ├── Chat.jsx
│   └── Risk.jsx
└── hooks/
    ├── usePortfolio.js  ← data fetching hook
    └── useWebSocket.js  ← WS connection hook
```

---

## Related

- **Streamlit dashboard** — `../dashboard/` — richer analytics, no Node required
- **FastAPI backend** — `../server.py` — REST + WebSocket API
- **Trading agents** — `../agents/` — Claude-powered signal generation
- **Main README** — `../README.md` — full project overview
