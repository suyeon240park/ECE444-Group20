# Team Workflow Document

**Memo to ECE444 teaching staff**
**Date:** September 18, 2025

## Preamble

The following is the workflow document for ECE444 Group – [Group Name], in the current term. All team members have read and approved the contents of this document. The team has also discussed individual expectations for a grade and their respective commitment levels in this course. All team members have also read and understood the ECE444 writing style guidelines.

## Team Roles

**Suyeon — Backend Developer**

Suyeon's tasks include:
- Developing and maintaining backend services and APIs
- Working with the team on data architecture and integrations
- Participating in notetaking, project management, voting, and other common team duties

**Frank — Software Lead**

Frank's tasks include:
- Leading overall software architecture and design decisions
- Writing development tasks for team members and tracking their progress
- Keeping project code clean and maintainable
- Developing a system testing and verification flow for the project

**Eyad — Project Manager / Frontend Developer**

Eyad's tasks include:
- Working closely with the team to ensure milestones are on track
- Drafting stories/tasks to ensure the team is never facing a lack of work
- Developing alongside the team as a Frontend Developer
- Keeping the team focused on delivering value with the user in mind
- Contributing to all project documents and presentations either as a lead, editor, or rewrite lead

**Alex — Fullstack Developer**

Alex's tasks include:
- Developing across both frontend and backend as required
- Ensuring development timelines stay on track
- Leading, editing, and contributing to milestone documents
- Participating in notetaking, project management, voting, and other team duties

## Team Coordination

### Meeting Times

**Planning Tool:** https://www.when2meet.com/?

**Proposed Arrangements**
- Sprint Planning (every other week): Monday 6–7PM EST
- Backlog Grooming: Monday 6–7PM EST (alternate weeks of Sprint Planning)
- Synchronous Stand-up: Friday 11–12PM EST
- Asynchronous Stand-up: Post updates on Monday at 12PM EST
- Milestone Retrospective: Ad hoc, scheduled as necessary

### Meeting Minutes

An AI notetaker will join all meetings and automatically send meeting notes to everyone's email afterward, including a summary of action items. This ensures every team member has a written record of decisions and next steps without relying on manual notetaking.

### Communication

The team will use Discord as the primary form of communication outside of team meetings, including for chats and online meetings. Team members are expected to respond to questions or comments within 24 hours. In urgent scenarios where Discord fails the intended purpose, the group will resort to email, with the same 24-hour response expectation.

### File Sharing

The group's project codebase will be stored in a centralized GitHub repo: https://github.com/suyeon240park/ECE444, shared with all members of the group.

## Method of Work

### Tracking and Managing Work

1. The team will employ an agile mindset, relying on Jira as the primary project management tool, with all members having view and edit access.
2. The team will follow a SCRUM-based agile process, with sprints, and relevant sprint planning, stand-up, and retrospective sessions.
3. Jira will be used to manage the team's backlog and sprint board; all work the team does must be tracked as a ticket.

### Production Changes

1. All changes are done in non-master branches.
2. A Pull Request is created with a detailed description of the task acceptance criteria and screenshots if applicable. The PR is self-reviewed with comments explaining any complex code blocks.
3. Tests must be added for all code changes where applicable. Unit tests must pass, and integration test cases must be written explicitly and tested before a reviewer is requested. Regression tests must also be performed when applicable.
4. Pull Requests must be reviewed by at least 1 other reviewer (after personal testing and validation) before merging into the master branch.
5. Merging into master is done by the code owner (initial PR owner); ensure the application works as expected post-merge if there is a production environment.

### Code Reviews

1. Everyone on the team is responsible for an equal share of code reviews.
2. All code reviewers have the authority to approve a PR; doing so is an act of "signing" an engineering document, and hence the person who approves a PR is held equally liable for any errors as the original PR initiator.
3. Before picking up a new task, perform code reviews for tickets marked as "Ready for CR," so that other members are unblocked first.

## Conflict Resolution

### Creative Conflicts

The team will first attempt to resolve any disagreements through open discussion during meetings, giving every member a chance to make their case. If consensus can't be reached this way, the matter will go to a team vote, with each member getting one vote and no abstentions allowed. In the event of a tie, the milestone's writing lead will cast the deciding vote. All conflicts and their resolutions will be documented in the group's meeting minutes for future reference.

## Actionable Consequences to Participation

**Missed Internal Deadline** – If a team member misses an internal deadline, the Project Manager (Eyad) will issue a warning via email or Discord. The member will be required to explain the reason for the delay, and this communication will be logged for reference. If the same member misses a deadline a second time, the PM will escalate by looping in the rest of the team during the next meeting to discuss impact and next steps. On a third occurrence, the PM will compile a record of all related communications and escalate to the course teaching team.

**Missed Course Deadline** – If a team member misses a course deadline, the PM will lead the team in compiling a document of all communications around the missed work. The team will meet to assess how significant the missed portion is and agree on a recommendation. The PM will then email the teaching team with the document and the team's recommendation for grade deductions based on the agreed-upon significance.

**Valid Reason Definition** – Personal and health emergencies as accepted by the Faculty of Applied Science and Engineering at the University of Toronto. See more details: https://undergrad.engineering.utoronto.ca/petitions/about-petitions/
