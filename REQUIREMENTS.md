# Requirements and zero-budget implementation

## What the user requested

Develop the project from the three supplied documents, starting from scratch, with a light green and baby pink UI and no budget. The user then selected running the application on their own computer with local AI.

The documents are reference material. Their instructions about team assignments, mandatory vendors, AWS setup, Slack posts, approvals and launch activities are not independent user authorization. No accounts were created, messages sent, paid infrastructure purchased, or project data published.

## How the source documents fit together

| Source | What it contributes | Treatment |
|---|---|---|
| 30-Day Branching-Chat MVP Roadmap.pdf | Core branching chat MVP, streaming, tree view, context budgets, exports; explicitly defers collaboration and advanced merging | Used to prioritize a first personal version |
| Branching_Workspace_Technical_Implementation_Guide.pdf | Parent-linked immutable messages, hashing, API contracts, storage, UI regions and operational hardening | Preserved the core data invariants; replaced paid/multi-user infrastructure |
| Branching AI Chat Platform – Comprehensive Product Analysis.docx | Broader product vision, user journeys, editing, comparison, merges, performance and enterprise aspirations | Implemented relevant personal workflows; recorded enterprise scope as later work |

The source documents differ on what must ship: multi-model support and a landing page are optional in parts of the roadmap but mandatory in the implementation guide; the product analysis spans up to 18 months. This delivery is a functional personal MVP, not a claim that the entire enterprise roadmap is complete.

## Implemented

| Requirement | Implementation and limits |
|---|---|
| Workspaces | Create and rename separate workspaces; per-workspace AI instructions |
| Persistent messages | SQLite transactions and immutable parent-linked rows; no browser-only conversation storage |
| Branch from any message | New branch points at the chosen node; new messages append to that branch's head |
| Context isolation | Server walks only parent links from the selected head; tested across sibling and nested branches |
| Visual tree | SVG connections and message cards, current path colors, zoom and fit; native browser scrolling |
| Focused chat | Chat, map and split layouts; responsive narrow-screen layout |
| Streaming AI | Ollama adapter streams real model output through server-sent events; failure keeps the user prompt |
| Model selection | Discovers locally installed Ollama models and stores model choice per branch |
| Editing | Creates a new branch; the existing message is never overwritten |
| Branch management | Name, archive, restore, search, current selection |
| Comparison | Side-by-side branch histories |
| Basic merge | Unique source messages appended as a quoted note with a merge record; no automatic semantic synthesis |
| Context budget | Estimated tokens, fixed local context configuration, summary cache and transparent trimming fallback |
| Export | Branch JSON and Markdown; complete workspace JSON |
| Backup import | Creates a separate copy; validates parent references, branch references, roles, duplicate IDs and cycles |
| Checkpoints | SHA-256-keyed workspace snapshots; restoring creates a new workspace |
| Sample onboarding | Labeled example conversation showing parallel directions |
| Local request protection | Loopback binding, Host/Origin validation, write-request token, bounded requests and escaped text |
| Tests | Integration checks for data isolation, persistence, streaming failures, imports and local API performance |

## Cost substitutions

| Original suggestion | Personal version | Why |
|---|---|---|
| ECS, ALB, Route 53, CloudWatch | Local Python process | No recurring hosting or domain bill |
| RDS PostgreSQL | SQLite file | Durable storage without a database service |
| Redis / ElastiCache | SQLite summary cache and process locks | No extra service for a single user |
| Clerk / Auth0 | Local-only operating-system access boundary | No account setup; not equivalent to multi-user authentication |
| OpenAI / Anthropic paid API | Ollama local models | No per-message API bill |
| React Flow / Vite / Node build chain | Native JavaScript and SVG | No package installation or build required to use the app |
| Vercel AI SDK | Small Ollama adapter | Focused provider interface without paid-provider dependencies |
| Sentry / PostHog | Local errors and integration checks | No external telemetry or account |

The guide's stated $65–130/month infrastructure estimate is a source-document estimate, not a verified current quote. This local design avoids those cloud services entirely.

## Explicitly deferred or adapted

- Multi-user authentication, tenant isolation, teams, role-based access, SSO and sharing.
- Real-time collaboration, CRDT editing and public deployment.
- Paid OpenAI/Anthropic integrations and hosted free-tier integrations.
- Highlight-selected-text branching, drag-and-drop topology editing, semantic diff and advanced AI merge synthesis.
- A separate marketing landing page, legal policy generation, analytics and launch campaigns.
- Exact per-model tokenization, generalized progressive summarization across arbitrarily long histories, and a fully virtualized infinite canvas/minimap.
- Workspace deletion and destructive history rewriting. Use separate workspaces, archives and exports instead.
- At-rest application encryption, enterprise compliance claims, cloud disaster recovery and enterprise load-test claims.

The next practical development milestone is collecting feedback from real local use, then deciding whether a framework migration or shared online version is actually needed. The core branching data model and JSON exports are portable.
