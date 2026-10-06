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

> The stack below is the Software Lead's proposal and is not final until the team confirms it. This section will be updated when the project skeleton is merged.

| Layer | Proposed choice | Why |
|---|---|---|
| Client (web and mobile) | React Native with Expo and TypeScript, built for web, iOS and Android from one codebase | One codebase covers the browser and phones; the camera and barcode scanner come built in |
| Backend API | Python with Flask | The course labs use Flask, and Python has the strongest OCR libraries |
| Database | PostgreSQL | Product cache, ingredient knowledge base |
| Product data | Open Food Facts API | Free, open, queried by barcode |
| Nutrition Facts extraction | To be chosen by benchmark (open question in the requirements document) | Must meet requirement Q1 |
| Tests and CI | pytest, Jest, GitHub Actions | Runs unit tests and the Q1 accuracy benchmark on pull requests |

## Getting started

There is no application code yet. Setup and run instructions will be added with the project skeleton in the first sprint.

To get the repository:

```
git clone https://github.com/suyeon240park/ECE444-Group20.git
cd ECE444-Group20
```

## Repository layout

```
.
├── README.md                    this file
├── CONTRIBUTING.md              how we branch, review and merge
├── CODE_OF_CONDUCT.md           how we treat each other
├── Team_Workflow_Document.md    roles, meetings, conflict resolution
├── team_members.md              names, roles, emails
└── docs/
    └── requirements.md          project goal, stakeholders, scope, selected requirements
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
