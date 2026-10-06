# What's in My Food?

ECE444 Software Engineering, University of Toronto, Fall 2026 · Group 20, Team Nexus

*What's in My Food?* helps shoppers understand packaged food without a nutrition background. A user photographs a product; the app identifies it from the barcode, retrieves its ingredient and nutrition data, and explains each nutrient and notable ingredient in plain language, with a link to the public-health or scientific source behind every statement. It shows what is in the product and what credible authorities say. It does not issue a single health score.

## Table of contents

- [Status](#status)
- [What the app does](#what-the-app-does)
- [Project management](#project-management)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Repository layout](#repository-layout)
- [Documentation](#documentation)
- [Team](#team)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)

## Status

| Milestone | State |
|---|---|
| M1: Team formation and project idea | Done |
| M2: Requirements engineering | Done. See [docs/requirements.md](docs/requirements.md) |
| M3: First sprint | In progress |

## What the app does

The scope for this semester is defined in [docs/requirements.md](docs/requirements.md). In short:

| ID | Requirement | Type | Story |
|---|---|---|---|
| F1 | Identify a packaged food by barcode and retrieve its food information, with Nutrition Facts OCR as a fallback | Functional | [#10](https://github.com/suyeon240park/ECE444-Group20/issues/10) |
| F2 | Display calories and nutrients for the entire package | Functional | [#2](https://github.com/suyeon240park/ECE444-Group20/issues/2) |
| F3 | Explain each nutrient in plain language with a credible source | Functional | [#3](https://github.com/suyeon240park/ECE444-Group20/issues/3) |
| F4 | Provide a quick, sourced ingredient summary for busy shoppers | Functional | [#9](https://github.com/suyeon240park/ECE444-Group20/issues/9) |
| Q1 | Nutrition values extracted from a label photo must match the printed label | Quality: accuracy | [#4](https://github.com/suyeon240park/ECE444-Group20/issues/4) |
| Q2 | Identify uploaded food products within an acceptable response time | Quality: performance | [#5](https://github.com/suyeon240park/ECE444-Group20/issues/5) |
| Q3 | Present food analysis that non-experts can understand and navigate without help | Quality: usability | [#11](https://github.com/suyeon240park/ECE444-Group20/issues/11) |

Deferred this semester: personalised allergen flagging ([#7](https://github.com/suyeon240park/ECE444-Group20/issues/7), [#8](https://github.com/suyeon240park/ECE444-Group20/issues/8)).

## Project management

The repository and the project board are private. The links below work for team members, the instructor and the TAs.

| Purpose | Tool | Link |
|---|---|---|
| Backlog, sprint planning and task board | GitHub Projects | https://github.com/users/suyeon240park/projects/2 |
| User stories, requirements review and implementation tasks | GitHub Issues | https://github.com/suyeon240park/ECE444-Group20/issues |
| Code review and merging | GitHub Pull Requests | https://github.com/suyeon240park/ECE444-Group20/pulls |
| Version control | Git and GitHub | https://github.com/suyeon240park/ECE444-Group20 |
| Continuous integration (planned) | GitHub Actions | https://github.com/suyeon240park/ECE444-Group20/actions |
| Day-to-day communication | Discord (private team server) | not public |
| Scheduling meetings | When2Meet | https://www.when2meet.com/ |
| Meeting minutes | AI notetaker in team meetings, corrected by hand when needed | not public |

How we use them:

- **Backlog.** Selected user stories are sorted by priority on the project board. Each story is a GitHub issue labelled `candidate-story` plus `functional` or `quality`.
- **Tasks.** Each first-sprint story is broken into implementation issues that link back to the story and to its section of the requirements document. Tasks move through Todo, In Progress and Done on the board.
- **Sprints.** We plan each sprint at a meeting, record estimated hours per task before starting, and compare them with actual hours at the end. Sprint reports are stored in [docs/](docs/).
- **Process.** Roles, meeting times and conflict resolution are in the [Team Workflow Document](Team_Workflow_Document.md). That document originally named Jira for task tracking; the team uses GitHub Projects instead.

## Tech stack

Set up in sprint 1 (issue #19).

| Layer | Choice | Why |
|---|---|---|
| Client (web and mobile) | React Native with Expo SDK 57 and TypeScript, built for web, iOS and Android from one codebase | One codebase covers the browser and phones; the camera and barcode scanner come built in |
| Backend API | Python 3.10+ with Flask | The course labs use Flask, and Python has the strongest image and data tooling |
| Database | PostgreSQL 16 (local instance via Docker Compose) | Product cache, ingredient knowledge base. Not used by any code yet |
| Product data | Open Food Facts API | Free, open, queried by barcode |
| Nutrition Facts extraction | Vision-model API prototype (#16); decision at the end of sprint 1 | Must meet requirement Q1 |
| Tests and CI | pytest and ruff for the backend, TypeScript and an Expo web build for the client, GitHub Actions | Runs on every pull request and on `main` |

## Getting started

You need Git, Python 3.10 or newer, and Node 22 or newer. Docker is optional and only needed for the local database.

```
git clone https://github.com/suyeon240park/ECE444-Group20.git
cd ECE444-Group20
```

**Backend** (terminal 1):

```
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate  on macOS / Linux
pip install -r requirements-dev.txt
copy .env.example .env          # Windows;  cp .env.example .env  on macOS / Linux
flask --app wsgi run --debug
```

Check http://127.0.0.1:5000/api/health returns `{"status": "ok", ...}`.

**Client** (terminal 2):

```
cd client
npm install
npm run web
```

The browser opens the app at http://localhost:8081. The home screen calls the backend health check and shows the result. For a phone, install Expo Go, run `npm start`, and scan the QR code.

**Database** (optional for now): `docker compose up db` starts PostgreSQL on port 5432 with the credentials in `backend/.env.example`.

**Before opening a pull request:**

```
cd backend && pytest && ruff check . && ruff format --check .
cd client && npm run typecheck && npm run build:web
```

CI runs exactly these commands. Details for each part are in [backend/README.md](backend/README.md) and [client/README.md](client/README.md).

## Repository layout

```
.
├── backend/                     Flask API: app/ (factory + route blueprints), tests/, wsgi.py
├── client/                      Expo app: App.tsx, src/ (api.ts and future screens), assets/
├── tests/
│   └── fixtures/
│       └── nutrition_labels/    benchmark photos and ground truth for requirement Q1 (#17)
├── docs/
│   └── requirements.md          project goal, stakeholders, scope, selected requirements
├── .github/workflows/ci.yml     backend lint + tests, client typecheck + web build
├── docker-compose.yml           local PostgreSQL
├── README.md                    this file
├── CONTRIBUTING.md              how we branch, review and merge
├── CODE_OF_CONDUCT.md           how we treat each other
├── Team_Workflow_Document.md    roles, meetings, conflict resolution
└── team_members.md              names, roles, emails
```

## Documentation

- [Requirements](docs/requirements.md)
- [Team Workflow Document](Team_Workflow_Document.md)
- [Team members](team_members.md)
- [Contributing guide](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

## Team

| Name | Role | Email |
|---|---|---|
| Suyeon Park | Backend Developer | suyeon.park@mail.utoronto.ca |
| Frank Liu | Software Lead | frankqt.liu@mail.utoronto.ca |
| Eyad Ahmed | Project Manager / Frontend Developer | eyad.ahmed@mail.utoronto.ca |
| Alex An | Full-Stack Developer | alex.an@mail.utoronto.ca |

## Contributing

Work happens on branches and reaches `main` only through a reviewed pull request. Read [CONTRIBUTING.md](CONTRIBUTING.md) before you start, and follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Acknowledgements

- README structure adapted from the [Best-README-Template](https://github.com/othneildrew/Best-README-Template).
- Product data from [Open Food Facts](https://world.openfoodfacts.org/).
- Nutrition guidance from [Health Canada](https://www.canada.ca/en/health-canada/services/food-nutrition/nutrition-labelling.html).
