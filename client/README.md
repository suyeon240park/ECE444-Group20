# Client

Expo app (React Native + TypeScript). One codebase for the web, iOS and Android. Node 22 or newer.

## Run locally

```
cd client
npm install
npm run web          # opens http://localhost:8081 in the browser
```

The home screen lets you upload a photo of a product barcode, or scan it live with the webcam, and shows the barcode the backend finds (`POST /api/barcode`, #13). A line at the bottom shows the result of the backend health check. Start the backend first (see `backend/README.md`), or uploads fail with "We couldn't reach the server" and the status line shows "Unreachable".

The second button is "Scan live" where the browser allows the webcam, and "Take photo" otherwise (Expo Go on a phone, or a plain `http://<LAN IP>` page). Photos must be JPEG, PNG or WebP and under 10 MB. On iOS the picker asks for the JPEG version of library photos; a HEIC photo that still arrives is rejected with a message.

**Scan live** opens the webcam and keeps sending frames to `POST /api/barcode` until one has a barcode (it gives up after a minute, and **Stop** ends it). Browsers only offer the webcam on `localhost` or https, so there the button is replaced by "Take photo".

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

Only changing the app, not the backend? Use the staging backend (#22) instead of running your own: set `EXPO_PUBLIC_API_BASE_URL=https://whats-in-my-food-api.onrender.com` in `client/.env`, skip step 4, and restart with `npx expo start -c` so the new value is picked up. The phone still loads the app from your computer, so step 1 still applies. This works in Expo Go only: in a browser on `localhost`, the staging backend refuses the request because it only accepts the staging app's origin.

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

## Results page

After a barcode is read, the app calls `GET /api/analysis/{barcode}` and opens the results page
(`src/screens/ResultsScreen.tsx`): product and data source, nutrition per serving and for the
whole package, nutrient explanations, and the ingredient summary. A section the server could
not provide shows its "not available" message and the rest still show.

The ingredient summary shows how many ingredients were checked, up to three flagged ones with
their reason (the rest behind "Show N more"), the other ingredients that were checked, and
the ones not in the reviewed database yet. Tapping a checked ingredient opens its detail screen
(`src/screens/IngredientDetailScreen.tsx`): what it is, why it is used, an explanation, source
links and the last-reviewed date, plus the reason, category and each authority's position for a
flagged one. Going back returns to the same place on the results page.

## Loading, partial-data and error states

Every screen shows these the same way through `src/components/StatusCard.tsx`:

- **Loading:** a spinner and a line saying what is happening. A product lookup that takes more
  than 8 seconds says it is taking longer than usual (the request stops after 20 seconds).
- **Error:** a plain message and what to do next. A failed scan offers "Try again" (it repeats
  how the scan was started). A failed lookup offers "Try again" and "Scan another product".
- **Partial data:** an amber notice on the results page lists what is missing and what is still
  shown. A section the server could not provide at all gets a "Try again" button. When the
  database lists values per 100 g and no serving size, the Nutrition section shows those values
  (`PerBasisNutritionTable`) instead of a table of "Not available".

Not built yet: offering a Nutrition Facts photo as the next step after a not-found or an
incomplete product. It needs the photo upload and confirmation screens from #39.

To work on the page without a backend, start the web build (`npm run web`) and open
`http://localhost:8081/?preview=<name>`, where `<name>` is `complete`, `incomplete`,
`nutrition_only`, `flagged`, `multiple_flags`, `no_flags` or `sections_unavailable` (the last one shows the "part of the analysis didn't load" state). The data is
in `src/mocks/`: four are real pipeline responses, the other three use the documented
ingredient examples (`multiple_flags` has four flags, so "Show 1 more" appears). The preview
works in development only.

## Layout

```
client/
├── App.tsx          root component
├── index.ts         Expo entry point (registers App)
├── src/
│   ├── api.ts           backend base URL and typed fetch helpers; add one module per API area
│   ├── barcode.ts       detectBarcode(): uploads a photo to POST /api/barcode
│   ├── barcodeRules.ts  barcode error codes, plain-language messages, pre-upload checks
│   ├── analysisApi.ts   fetchAnalysis(): GET /api/analysis/{barcode}
│   ├── productResult.ts types of the product contract and the analysis response
│   ├── ingredientView.ts labels and helpers for showing the ingredient result
│   ├── format.ts        formatDate() and joinWords() for text shown to people
│   ├── components/      shared pieces: Section, StatusCard (loading, error, notice), nutrition tables, explanations, ingredients, source links
│   ├── mocks/           mock analysis responses for the results page
│   └── screens/
│       ├── BarcodeScreen.tsx   take or upload a photo, show the barcode or the failure
│       ├── ResultsScreen.tsx   the whole analysis for one product
│       └── IngredientDetailScreen.tsx   one ingredient in detail
├── assets/          icons and splash images
├── app.json         Expo configuration (name, icons, web bundler, extra.apiBaseUrl)
└── tsconfig.json    strict TypeScript, extends expo/tsconfig.base
```

Screens and components go under `src/` as they are added (for example `src/screens/`, `src/components/`).
