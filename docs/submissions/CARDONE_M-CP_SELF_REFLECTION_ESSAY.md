# aiFeelNews Capstone Project — Self-Reflection Essay

Matias Cardone · matias.cardone@code.berlin · Spring Semester 2026

Module: Capstone Project · Project: aiFeelNews · Specialty: Web Backend

CODE University of Applied Sciences, Berlin · Supervisor: Frank Trollmann · 10 June 2026

---

When I registered this capstone, I wanted to prove to myself that I could build an
application end-to-end, alone. I had built individual pieces from zero before — a
frontend here, a backend there — and through work I operate daily around most of
the remaining areas without owning them. Putting everything together, from the
Terraform underneath to the article feed on top, was the part I had never done and
the part I wanted. If I am direct about the motivation: I wanted to get better at
everything at once, and a solo full-stack system is the one project shape that
demands exactly that.

One constraint shaped the system as much as any technology choice: I built it
alongside a job, in bursts, with gaps. I designed for that consciously: partly to
keep costs near zero, partly because I knew nobody would be watching the system
daily, least of all me. Cloud Run scales to zero, so an idle two weeks costs
nothing. Migrations run themselves in CI. Alerts escalate by email instead of
assuming an operator is looking at a dashboard. The demo rebuilds itself from a
seeded dataset with no credentials. The system had to tolerate an absent operator,
because it had one.

The decision I learn the most from is the one I got wrong. On May 3 I shipped
security hardening I was proud of: OIDC verification on the scheduler endpoints,
so that only Google-signed tokens from my own service account could trigger
ingestion. It worked — so well that it locked out my own scheduler. The job's
token did not carry the bare service URL as its audience, and from that cron tick
on, every scheduled ingestion died as a clean 401. No downtime, no errors, no
alarm: the uptime check watched a perfectly healthy web service, the error-rate
alert watched for 500s that never came, and a 401 is not an error to anyone but
the caller. The pipeline was dead for nine days while the system stayed green. I
noticed it the way a user would have — I came back from a gap, opened the feed,
and nothing was new.

What bothers me in hindsight is not the bug — which, as I have since learned, is
a common trap in Scheduler-to-Cloud-Run setups. It is the nine days. My monitoring had existed since February and was watching
for the wrong kinds of death: it could see the service fall over, but not the
system quietly doing nothing. The fix I shipped on May 12 states the lesson
better than I can: the audience is now wired in Terraform next to everything
else, and two alerts went out in the same commit. A leading one — any 401 on a
scheduler endpoint fires on the first bad cron tick, because the scheduler
retries and even a single broken run produces several. And a lagging one — if no
"ingestion completed" log line appears for nine hours, alert, regardless of why:
auth, code, a Mediastack outage, a bad deploy. That second alert taught me a
distinction I now treat as fundamental: detecting errors and detecting absence
are different problems. It had to be a metric-absence condition, because
log-based delta metrics produce gaps rather than zeros when nothing happens — a
"less than one run" threshold would never have fired on a fully dead pipeline.
Silence is a failure mode, and it has to be designed for explicitly.

It was not the pipeline's only lesson, either. Ingestion stalled more than once
over the months, for different reasons — among them a backlog that starved the
newest articles, because crawl jobs drained in effectively oldest-first order
under a capped per-run budget while I was still learning the NLP API's caveats. I
had considered the pipeline finished early on; it kept teaching me otherwise. If
I rebuilt this project, the pipeline would get its metrics and alerts on day one
instead of earning them the hard way.

The decision that changed how I think arrived late, and entirely on paper. Two
days before writing this, while working through the cost and scalability
documentation, I multiplied numbers I had known separately for months: Cloud SQL
caps connections at 50, SQLAlchemy defaults to roughly 15 per instance, and Cloud
Run fans out to ten instances. A hundred and fifty demanded, fifty available.
Nothing had ever broken — traffic had never spun up that many instances at once —
but the failure was sitting there, waiting for the first busy day. The fix
inverts instinct: under load you do not grow the pool, you shrink it — four per
instance, forty at full fan-out, safely under the cap. What stays with me is not
the arithmetic but the unit of thought. I had been sizing a resource per process when
the constraint belonged to the deployment as a whole — every instance drawing
from the same fifty connections. And I would rather find that kind
of bug in a document than in production; that is what writing the document is
for.

The request handlers are synchronous mostly because that is how the codebase
grew, and the justification came afterwards:
when I examined whether an async rewrite would buy anything, the analysis showed
the connection pool saturates long before the thread pool, so a rewrite would
move complexity around without moving the bottleneck. The analysis is correct
and I stand by it — and if I started again tomorrow, I would probably write
async handlers from the first file anyway, because it is the ecosystem's default
and costs nothing when there is nothing to migrate. I used to think a decision
had to have been right from the beginning to be defensible. I now think what
matters is whether you understand the constraint it lives under, and say so.

Some decisions came from outside, which is its own lesson. After the
Cybersecurity assessment, my professor suggested looking into access control, worth
having even where the scale does not strictly demand it. Instead of
bolting a roles table onto the database, I put the role claim inside the
Firebase-signed ID token: cryptographically verified on every request, no second
source of truth, no migration. The trade is that roles are granted out-of-band
rather than through an admin interface, which is proportionate for a system with
exactly one admin. The same sense of proportion ended the SvelteKit migration my exposé
had planned: by the time it was due, the personas and use cases were covered by
the stack I already had, and migrating for features that do not exist yet would
have been fashion, not engineering. I recorded the changed decision instead of
quietly dropping the promise.

Rebuilt from zero, then: async handlers from the start; pipeline metrics and
alerts from the first deploy; the Postgres arrangement in CI done properly from
scratch instead of grown; and, had the project's center of gravity been the
frontend, an earlier and harder look at the framework once the first MVP had
validated the concept. What would not change: Postgres in the middle, the
managed-GCP trade with its accepted lock-in, the demo that rebuilds itself from
a seed, and the habit, learned here, of writing the reasoning down while the
decision is still being made.

The learning behind the project did not start with the registration. I attended
the CODE learning units for all three module areas — Cloud Computing, Relational
Databases, Cybersecurity — twice each, before the capstone formally began. During
the build itself, my resources were the primary documentation (Google Cloud's and
SQLAlchemy's, above all), colleagues at work who had seen these problems before,
and office hours — Prof. Adam Roe's in particular, around the cloud architecture.
The LUs gave me the overview before I needed it; the docs and the people
answered the specific questions once I was inside the problem.

LLMs — ChatGPT and Claude — helped me understand concepts and go through
documentation in a more direct, dynamic and friendly way. A conversational
approach to documentation, on Docker and Terraform best practices for example,
made it easier to learn by asking questions rather than just reading. I used
them as an accelerator, not a replacement for understanding. They also carried
real project work: drafting some pull-request descriptions, first drafts of
tests, and code-review passes (GitHub Copilot is wired into CI as an automatic
first reviewer on every pull request), always with me deciding what was merged. Where
they were less useful: answers arrive equally confident whether they are right
or wrong, so everything still had to be verified against the documentation and
the tests — and when an agent edits files directly, it can change more than it
was asked to, so the review of its diffs became as important as the review of my
own code.

If I reduce what this project taught me about backend engineering to one
sentence, it is this: the parts of my system that failed were each individually
correct — the failures lived in the seams between them, and the cure was never a
smarter component but a more observable whole. And one more: a backend's real
job is to keep working when nobody is looking, and to say something when it
can't.

Against the level descriptions, I assess this work at Level 2. The case in one
line: I applied my knowledge to a complex, deployed, end-to-end system, examined
the backend specialty in depth, discussed its decisions from more than one
perspective (cost, security, operability), and evaluated the methods I did not
choose: async handlers, keyset pagination, a roles table, a framework migration.
I also know where the work stops. The large view components are untested by
choice, pagination will not survive deep offsets, and the pipeline earned its
alerts the hard way. Naming those gaps is part of the level I am claiming.
