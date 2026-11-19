# ADR 0001: Local SQLite job queue

- Status: accepted for the initial release
- Date: 2026-11-19
- Decision: AD-003

## Context

The application needs a web service and a separate worker so file conversion does not block the UI. It targets a single self-hosted machine, has no accounts, and must keep uploads and results local. A broker, database server, and object-storage service would add setup and maintenance for a HomeLab deployment.

## Decision

Use a SQLite database on a shared local Docker volume for durable job state and atomic worker claims. Store each job's input and output in a per-job directory on that same volume. The web container creates jobs; one worker container polls and claims queued jobs; the web container reports status and streams completed results. A configured retention period removes the job row and its files.

Serve the interface from FastAPI with Jinja templates and locally hosted CSS/JavaScript. The interface needs one responsive tool-selection and job flow; a separate SPA toolchain is not required for that scope.

## Consequences

- The first deployment has only web and worker application services; no external service is required.
- The job database and file volume must be backed up or retained together if operators want to preserve pending jobs across container recreation.
- This queue is for a single host and modest HomeLab concurrency. A future distributed deployment may replace it with a broker and shared object storage.
- Job identifiers must be cryptographically unpredictable because API access is unauthenticated.
- The web service serves the UI and API from the same origin. No CDN, analytics, or external runtime service is used.

## Alternatives considered

- Redis/Celery or another external broker: rejected because it adds a service and more configuration to a single-host deployment.
- Synchronous conversion in the web process: rejected because long-running conversions would block request handling and make progress reporting unreliable.
- External object storage: rejected because uploads must remain local and the target is a self-hosted single machine.
- A separate React/Vite SPA: rejected for the initial scope because a server-rendered interface with progressive JavaScript avoids a second build/runtime stack while supporting upload progress and job polling.
