# Client

Expo app (React Native + TypeScript). One codebase for the web, iOS and Android. Node 22 or newer.

## Run locally

```
cd client
npm install
npm run web          # opens http://localhost:8081 in the browser
```

The home screen lets you take or upload a photo of a product barcode and shows the barcode the backend finds (`POST /api/barcode`, #13). A line at the bottom shows the result of the backend health check. Start the backend first (see `backend/README.md`), or uploads fail with "We couldn't reach the server" and the status line shows "Unreachable".

On the web, "Take photo" opens the camera on a phone browser and a file picker on a desktop. Photos must be JPEG, PNG or WebP and under 10 MB; iPhone HEIC photos are rejected with a message.

## Run on a phone (Expo Go)

Expo Go runs the real app on your phone, with real camera and barcode scanning. It loads the JavaScript from your own computer, so each teammate runs their own copy.

One-time setup:

1. Install **Expo Go** from the App Store or Google Play.
2. Create a free account at https://expo.dev/signup, then run `npx expo login` in `client/` and log in to Expo Go with the same account. Expo requires this.

Each time:

1. Phone and computer on the same Wi-Fi.
2. Find your computer's LAN IP (`ipconfig` on Windows, `ifconfig` or `ip a` on macOS/Linux), e.g. `192.168.1.23`.
3. Create `client/.env` from `client/.env.example` and set `EXPO_PUBLIC_API_BASE_URL=http://192.168.1.23:5000` with your IP. `.env` is ignored by git, so this never affects anyone else.
4. Start the backend so it accepts connections from the network: `flask --app wsgi run --debug --host 0.0.0.0`. Allow it through the firewall if asked.
5. In `client/`, run `npm start` and scan the QR code with the phone camera (iOS) or from inside Expo Go (Android).

If the status line on the phone says "Unreachable", open `http://<your IP>:5000/api/health` in the phone's browser. If that fails too, the problem is the network or the firewall, not the app.

Expo Go cannot produce an installable APK or App Store build. Those come from EAS Build in the release sprint.

## Backend URL

Resolution order, implemented in `src/api.ts`:

1. `EXPO_PUBLIC_API_BASE_URL` from `client/.env` or the build environment. Used for phone testing and by the staging deployment (#22).
2. `extra.apiBaseUrl` in `app.json` (`http://localhost:5000`), the browser-development default.

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
│   ├── api.ts           backend base URL and typed fetch helpers; add one module per API area
│   ├── barcode.ts       detectBarcode(): uploads a photo to POST /api/barcode
│   ├── barcodeRules.ts  barcode error codes, plain-language messages, pre-upload checks
│   └── screens/
│       └── BarcodeScreen.tsx   take or upload a photo, show the barcode or the failure
├── assets/          icons and splash images
├── app.json         Expo configuration (name, icons, web bundler, extra.apiBaseUrl)
└── tsconfig.json    strict TypeScript, extends expo/tsconfig.base
```

Screens and components go under `src/` as they are added (for example `src/screens/`, `src/components/`).
