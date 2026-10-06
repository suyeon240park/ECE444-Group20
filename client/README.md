# Client

Expo app (React Native + TypeScript). One codebase for the web, iOS and Android. Node 22 or newer.

## Run locally

```
cd client
npm install
npm run web          # opens http://localhost:8081 in the browser
```

For a phone, install the Expo Go app, run `npm start`, and scan the QR code. The phone must be on the same network as your computer, and the backend URL below must be reachable from the phone (use your computer's LAN IP instead of `localhost`).

The home screen calls the backend health check and shows the result. Start the backend first (see `backend/README.md`), or the card shows "Unreachable".

## Backend URL

- Development: `extra.apiBaseUrl` in `app.json` (`http://localhost:5000`).
- Deployed builds: set `EXPO_PUBLIC_API_BASE_URL` at build time; it overrides `app.json`. This is how the staging deployment (#22) points the client at the staging backend.

## Check and build

```
npm run typecheck    # tsc --noEmit
npm run build:web    # static web build into dist/
```

CI runs both on every pull request.

## Layout

```
client/
├── App.tsx          root component
├── index.ts         Expo entry point (registers App)
├── src/
│   └── api.ts       backend base URL and typed fetch helpers; add one module per API area
├── assets/          icons and splash images
├── app.json         Expo configuration (name, icons, web bundler, extra.apiBaseUrl)
└── tsconfig.json    strict TypeScript, extends expo/tsconfig.base
```

Screens and components go under `src/` as they are added (for example `src/screens/`, `src/components/`).
