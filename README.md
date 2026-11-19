# course-catalog-api

Backend of the course catalog: FastAPI, SQLAlchemy 2.1, PostgreSQL, Alembic and
GraphQL on Strawberry as a second entrance (Labs 4–8, "Advanced Web Technologies").
REST and GraphQL share one database and one services layer (`services.py`).
The Next.js frontend lives in
[-awt-lab02-issimbaeva-alua](https://github.com/alua-issimbayeva/-awt-lab02-issimbaeva-alua);
it has the "My courses" page twice: `/my-courses` (GraphQL) and `/my-courses-rest` (REST).

## How to run

You need Python 3.11 or newer and PostgreSQL 16 or newer.

Once, as the `postgres` superuser, create the role and the database:

```sql
CREATE ROLE catalog_app LOGIN PASSWORD 'change-me';
CREATE DATABASE course_catalog OWNER catalog_app;
```

Then, from the project folder:

```bash
# 1. virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows (PowerShell): .venv\Scripts\Activate.ps1

# 2. dependencies (FastAPI, SQLAlchemy, psycopg, Alembic, Strawberry)
pip install -r requirements.txt

# 3. settings: the database address and GRAPHQL_INTROSPECTION
cp .env.example .env               # Windows (PowerShell): Copy-Item .env.example .env

# 4. schema: both migrations, 0001 and 0002
alembic upgrade head

# 5. initial data: 6 courses, 3 students, 6 enrollments (clears the tables first)
psql -h localhost -U catalog_app -d course_catalog -v ON_ERROR_STOP=1 -f seed.sql

# 6. check that models and database agree, then start the server
alembic check
fastapi dev main.py
```

REST docs: http://localhost:8000/docs. GraphiQL: http://localhost:8000/graphql (open it
in a browser; a GET from a browser returns the editor, a POST with JSON runs a query).
The password `change-me` is for training; real projects don't commit passwords.

Check scripts (the server must be running, on the data from `seed.sql`):

| Script | Expected |
|--------|----------|
| `python try_errors.py` | `5 of 5 as expected`, four rule errors as `application/problem+json` |
| `python try_graphql.py` | `8 of 8 as expected` |
| `python try_n_plus_1.py` | `SQL queries: 3` for both nested queries |
| `python measure.py` | REST 5 requests in 2 rounds, GraphQL 1 request in 1 round |
| `python try_protection.py` | five short errors and `introspection … data, no errors` |
| `python flood_likes.py` | `error: 12 aliases found. Allowed: 10`, `SQL queries: 0` |

`python print_schema.py` prints the GraphQL schema as SDL. `more_students.sql` adds 17
students for the N+1 experiment; run it only once (reset with `seed.sql`).

### Routes

| Route | Description |
|---|---|
| `GET /` | Checks that the server is alive |
| `GET /courses` | Course list. Query params: `is_elective`, `level`, `sort` (`popular` or `title`), `q`, `page` (≥ 1), `page_size` (1–100) |
| `GET /courses/{course_id}` | A single course, or 404 `course-not-found` |
| `POST /courses/{course_id}/like` | Adds a like (`UPDATE … RETURNING`) and returns the course, or 404 |
| `POST /students` | Creates a student: `{"name", "email"}` → 201, or 409 `email-taken` |
| `GET /students/{id}` | A single student, or 404 `student-not-found` (Lab 8) |
| `GET /students/{id}/enrollments` | The student's enrollments with `courseTitle` and `studentName` (Lab 8) |
| `POST /enrollments` | `{"courseId", "studentId"}` → 201, or 409 `already-enrolled`, 404 `course-not-found` / `student-not-found` |
| `GET /enrollments` | All enrollments with `courseTitle` and `studentName` (one JOIN) |
| `GET /stats/courses` | Number of enrollments per course, including courses with 0 |
| `GET /stats` | Catalog totals: `total`, `totalCredits`, `electives` |
| `POST /graphql` | GraphQL: queries `courses`, `course`, `students`, `student`, `enrollments`; mutations `enroll`, `likeCourse` |

## What changed in the API

- **REST errors are Problem Details (RFC 9457).** A rule error now has the content type
  `application/problem+json` and a body with `type`, `title`, `status`, `detail`,
  `instance`, for example `{"type": "https://example.com/problems/already-enrolled",
  "title": "Already enrolled", "status": 409, …}`. The client tells errors apart by
  `type`, not by parsing the text. The rules live in `services.py`: it raises
  `ServiceError` with a code (`EMAIL_TAKEN`, `ALREADY_ENROLLED`, `COURSE_NOT_FOUND`,
  `STUDENT_NOT_FOUND`), and `problem.py` turns the code into a status and a type.
  Starlette's own errors (unknown address, wrong method) are Problem Details too, with
  `type: about:blank`; the `allow` header of a 405 is kept. Pydantic validation errors
  (422) are still in the old FastAPI format.
- **`/graphql` is a second entrance.** It has one address and one schema with the types
  `Course`, `Student`, `Enrollment`, so a client can ask for a student, their
  enrollments and each enrollment's course in one POST, with only the fields it needs.
  Each request gets its own database session and its own DataLoaders through the
  context. In a browser the same address opens GraphiQL, an editor with autocompletion
  and schema docs; an ordinary client just POSTs JSON `{"query", "variables"}`. A
  GraphQL error usually arrives with status 200, so clients must check `errors`.
- **Mutations `enroll(input: {courseId, studentId})` and `likeCourse(id)`** return a
  payload with the result and `userErrors`. An expected rule error (duplicate
  enrollment, unknown course or student) is part of `data`: `userErrors[0].code` holds the
  same code that REST turns into a status. `errors` is only for real failures: a broken
  query, a bug, a database error. Mutations sent with GET are refused with 400.
- **The `X-SQL-Queries` header** on every response counts the SQL statements run for that
  HTTP request (`counter.py`, a SQLAlchemy `before_cursor_execute` listener plus a
  middleware). It made the N+1 problem visible, and it is how `measure.py` counts
  database work.
- **GraphQL protection:** query depth is at most 5, a query can have at most 10 aliases,
  `limit` must be 1–100, and an `id` that is not a number gets `Invalid ID: '…'`. Any
  other exception reaches the client only as `Unexpected error.`; the full text stays
  in the server log. Introspection is on by default and is switched off with
  `GRAPHQL_INTROSPECTION=false` in `.env` (read at startup).
- **New REST routes** `GET /students/{id}` and `GET /students/{id}/enrollments` for the
  REST version of "My courses". The enrollment query is shared with `GET /enrollments`
  through `enrollment_details()`.

## Example queries

The “My courses” query (in the GraphiQL Variables panel: `{"id": "2"}`):

```graphql
query MyCourses($id: ID!) {
  student(id: $id) {
    name
    enrollments {
      id
      course { title credits level }
    }
  }
}
```

```json
{
  "data": {
    "student": {
      "name": "Daniyar Bekov",
      "enrollments": [
        { "id": "3", "course": { "title": "Modern Frontend: React & Next.js", "credits": 5, "level": "intermediate" } },
        { "id": "4", "course": { "title": "Backend Foundations: FastAPI", "credits": 5, "level": "intermediate" } },
        { "id": "5", "course": { "title": "AI/LLM Integration", "credits": 5, "level": "beginner" } }
      ]
    }
  }
}
```

The `enroll` mutation (Variables: `{"input": {"courseId": "web-security", "studentId": "3"}}`):

```graphql
mutation Enroll($input: EnrollInput!) {
  enroll(input: $input) {
    enrollment { id enrolledAt course { title } }
    userErrors { code message }
  }
}
```

The first time the enrollment is created (the `id` depends on the database's sequence):

```json
{
  "data": {
    "enroll": {
      "enrollment": {
        "id": "16",
        "enrolledAt": "2026-11-19T10:51:49.651383+05:00",
        "course": { "title": "Web Security Essentials" }
      },
      "userErrors": []
    }
  }
}
```

The same mutation again: still status 200, no `errors`, and the rule error is in `userErrors`:

```json
{
  "data": {
    "enroll": {
      "enrollment": null,
      "userErrors": [
        { "code": "ALREADY_ENROLLED", "message": "Student is already enrolled in this course" }
      ]
    }
  }
}
```

The same rule over REST: `POST /enrollments` → `409`, `application/problem+json`,
`"type": "https://example.com/problems/already-enrolled"`.

## REST vs GraphQL comparison

The “My courses” screen of student 2; numbers from `measure.py`, starting data.

| Criterion | REST | GraphQL | Source |
|-----------|------|---------|--------|
| Requests and rounds per screen | 5 requests in 2 rounds: student + enrollments, then one `GET /courses/{id}` per course (the codes are known only after round 1) | 1 request, 1 round | `measure.py`, step 8 |
| Bytes in the responses | 1145 (full courses with description, likes, `isElective`; enrollments with names and time) | 339 (only `name`, `title`, `credits`, `level`): about 3.4× less | `measure.py`, step 8 |
| SQL queries per screen | 5: student, enrollments (JOIN), 3 × course | 3: student, enrollments (one `IN`), courses (one `IN`) | `measure.py`, `X-SQL-Queries` |
| SQL growth with more students | each route has a fixed query (`GET /enrollments` is 1 JOIN for any number of rows), but the screen costs 2 + one per course the student has | without DataLoaders it grew with the data: 7 → 27 and 7 → 24 queries for 3 → 20 students; with DataLoaders 3 and 3 for both | `try_n_plus_1.py`, experiments 4–5 |
| Error in the query text | unknown address → 404, bad parameter → 422, visible from the status | status 200, `data: null`, `errors` with `Did you mean …`; the client must check `errors` (without the check the page failed with `Cannot destructure property 'student' … null`) | experiments 1 and 8 |
| Expected rule error (repeated enrollment) | 409, `application/problem+json`, `type …/already-enrolled` | 200, `userErrors[0].code = ALREADY_ENROLLED` in `data`; same code from the same service | steps 1 and 4 |
| HTTP cache | GET by URL is cacheable by the browser, a CDN or a proxy (`Cache-Control`, `ETag`) for each resource separately | everything goes as POST to one `/graphql` address, so HTTP caches don't help; you need persisted queries over GET or a client-side cache | lecture section 14 |
| Protection from “expensive” queries | the route fixes the cost: `page_size` is checked by `Query(ge=1, le=100)` (`?page_size=-1` → 422), a rate limiter counts requests | the client decides the cost: without protection a depth-6 cycle and 12 likes in one POST (likes 11 → 23, 24 SQL queries) ran, and DB errors leaked SQL text; protection needs depth and alias limits, argument checks, error masking | experiments 6 and 7 |

**Conclusion.** For a screen that combines several resources, like “My courses”,
GraphQL clearly wins: 1 request instead of 5, one network round instead of two, 339
bytes instead of 1145, and 3 SQL queries that don't grow with the number of courses.
That only holds with DataLoaders: without them the same single POST cost 27 SQL
queries on 20 students. I would leave on REST the simple, public and cacheable
resources (`GET /courses`, `GET /courses/{id}`, `GET /stats`) and the simple writes,
where HTTP caching, status codes and route-level limits come for free. I would use
GraphQL for personal, nested screens like “My courses”, and only together with the
protections from step 7.

## Experiment log

Each experiment was undone right after it, and the checks were run again. The output is
from my machine. My PostgreSQL server reports errors in Russian (`lc_messages`), so the
database's own message text in experiment 6 is in Russian; the error class and the
`[SQL: …]` part are verbatim.

| # | Experiment | What I saw | Cause | How I fixed it |
|---|------------|------------|-------|----------------|
| 1 | a typo in a field name, an argument name in `snake_case` | `{ course(id: "api-design") { titel } }` → status **200**, `"data": null`, `"errors": [{"message": "Cannot query field 'titel' on type 'Course'. Did you mean 'title', 'level', or 'likes'?", "locations": [{"line": 1, "column": 30}]}]`. `courses(is_elective: true)` → 200, `Unknown argument 'is_elective' on field 'Query.courses'. Did you mean 'isElective'?`. For comparison, REST `GET /courses/no-such` → 404 with Problem Details | GraphQL validates the query against the schema before running it and reports problems in `errors`, not in the HTTP status. Strawberry converts Python `snake_case` names to `camelCase` in the schema | Fixed the queries (`title`, `isElective`). Lesson: status 200 means nothing in GraphQL, the client checks `errors` |
| 2 | `\| None` removed from the `course` query, a nonexistent course | Schema became `course(id: ID!): Course!`. `course(id: "nope")` → 200, `"data": null`, `Cannot return null for non-nullable field Query.course.`, `path: ["course"]`, and a `TypeError` traceback in the server window. `{ a: course(id: "api-design") … b: course(id: "nope") … }` → `"data": null`, the error with `path: ["b"]`: the good field `a` was lost too | A `!` field that returns null breaks the schema's promise. By the null propagation rule the null goes up to the nearest nullable parent, here the whole `data` | Restored `CourseType \| None`: the same query gives `{"a": {"title": "API Design: REST vs GraphQL"}, "b": null}`. `try_graphql.py`: 5 of 8 (as expected for step 3) |
| 3 | a mutation with the GET method | `GET /graphql?query={course(id:"api-design"){title likes}}` → 200, `likes: 12`. `GET /graphql?query=mutation{likeCourse(id:"api-design"){course{likes}}}` → **400**, `text/plain`, `mutations are not allowed when using GET`. A repeated read still showed `likes: 12` | GET must be safe: it can be repeated, prefetched and cached, so a link must not change data. Strawberry refuses mutations over GET at the protocol level, which is why this is plain text, not JSON with `errors` | Nothing to fix: this is the correct behavior. Restored the data with `seed.sql` |
| 4 | `more_students.sql`: 3 and 20 students, the SQL counter | 3 students: `students → enrollments → course` rows 3, **7** SQL queries; `enrollments → course, student` rows 6, **7**. After `more_students.sql` (20 students): rows 20, **27**, and rows 20, **24**. The SQL log showed the same `SELECT … FROM enrollments WHERE … = enrollments.student_id` for students 1, 2, 3 one after another | Lazy loading in resolvers: 1 query for the list + 1 per student + 1 per distinct course not yet in the identity map (1 + 3 + 3 and 1 + 20 + 6; the second query 1 + 3 + 3 and 1 + 6 + 17). The query text, status and response time look the same, so only the counter shows it | Fixed in step 6 with DataLoaders: 3 and 3 on 20 students |
| 5 | a DataLoader batch function that doesn't sort rows by key | `{ students { name enrollments { course { title } } } }` → `"data": null`, `Received wrong number of results in dataloader, expected: 3, received: 6`, `path: ["students", 0, "enrollments"]`, server: `WrongNumberOfResultsReturned`. `{ enrollments { id course { title } } }` → **no error**, but enrollments 2, 4, 5, 6 showed the wrong course (2: Backend Foundations instead of AI/LLM, 4: AI/LLM instead of Backend Foundations, 5 and 6: Backend Foundations instead of AI/LLM) | The loader matches results to keys by position. In the first case the lengths differed (3 keys, 6 rows) and Strawberry refused, which is loud. In the second there were 3 keys (`modern-frontend`, `ai-integration`, `backend-fastapi`) and 3 rows, but `ORDER BY id DESC` returned `modern-frontend`, `backend-fastapi`, `ai-integration`, so the data was quietly wrong. That is worse, because nobody notices | `git restore graphql_api.py`: the original function groups rows by `getattr(row, column.key)` and builds the result in key order. `try_graphql.py` 8 of 8 |
| 6 | six dangerous queries without protection and with it | see the table below | the client controls depth, aliases and arguments; unhandled exceptions are sent to the client with their full text | added `QueryDepthLimiter(5)`, `MaxAliasesLimiter(10)`, `MaskErrors`, `check_limit`, `parse_id` |
| 7 | introspection off, a typo in a field name | With `GRAPHQL_INTROSPECTION=false`: `{ __schema { queryType { name } } }` → two errors, `GraphQL introspection has been disabled, but the requested query contained the field '__schema'.` (and `'queryType'`). Ordinary queries kept working (`try_graphql.py` 8 of 8). `{ cours { title } }` → `Cannot query field 'cours' on type 'Query'. Did you mean 'course' or 'courses'?` | `DisableIntrospection` blocks only the `__schema`/`__type` fields. Validation still uses the schema and suggests similar names, so field names can be guessed one by one | Put `GRAPHQL_INTROSPECTION` back (deleted the line from `.env`) for GraphiQL. Lesson: hiding the schema is not authorization; access is controlled by permissions |
| 8 | client failures: a typo, no `errors` check, the API stopped | (1) `titel` in `app/my-courses/page.tsx` → page 500, `⨯ Error [GraphQLRequestError]: Cannot query field 'titel' on type 'Course'. Did you mean 'title', 'level', or 'likes'?` at `gql (lib\graphql.ts:31:34)`. (2) The `errors` check commented out → `⨯ TypeError: Cannot destructure property 'student' of '(intermediate value)' as it is null.` at `page.tsx:23:11`. (3) API stopped → `⨯ TypeError: fetch failed` at `gql (lib\graphql.ts:22:15)` | (1) `gql` saw `errors` and threw them with the real cause. (2) The response was 200 with `data: null`, `res.ok` passed, and the page crashed on the consequence, while the cause was thrown away. (3) No response at all: a network failure, not GraphQL | `git restore .` in `course-catalog`, restarted the API; both pages show the three courses again. `gql` checks `errors` because status 200 is not success in GraphQL |

Experiment 6 in detail (`try_protection.py` and `flood_likes.py`):

| Query | Without protection | With protection |
|-------|--------------------|-----------------|
| a depth-6 cycle | executed, data arrived | `'Cycle' exceeds maximum operation depth of 5` |
| 12 aliases | executed; `flood_likes.py`: likes `[12 … 23]`, `SQL queries: 24` | `12 aliases found. Allowed: 10`; flood: same error, `SQL queries: 0`, likes stayed 23 |
| `limit: -1` | `(psycopg.errors.InvalidRowCountInLimitClause) LIMIT не может быть отрицательным` + `[SQL: SELECT courses.id, courses.title, … FROM courses ORDER BY courses.likes DESC, courses.id LIMIT %(param_1)s::INTEGER]` + `[parameters: {'param_1': -1}]` | `limit must be between 1 and 100` |
| `id: "abc"` | `invalid literal for int() with base 10: 'abc'` | `Invalid ID: 'abc'` (`data.student` is `null`, the rest of `data` survives) |
| id of 20 digits | `(psycopg.errors.NumericValueOutOfRange) bigint вне диапазона` + SQL with parameters | `Unexpected error.` (the server log keeps `sqlalchemy.exc.DataError: … bigint вне диапазона`) |
| introspection | the schema arrived | the schema arrived (it is switched off by the setting, experiment 7) |

- **What the client learned without protection:** from `limit: -1` and the 20-digit id it
  got the driver (`psycopg`), the table and all column names, the SQL text with the
  parameter type, the parameter values and the SQLAlchemy version link (`/e/21/`).
  From `"abc"` it learned the server is Python and converts the id with `int()`. From
  the cycle and the aliases it learned there are no limits at all, so it can multiply
  database work (12 writes in one request) without any request limiter noticing.
- **Why `check_limit` and `parse_id` and not only `MaskErrors`:** `Invalid ID: 'abc'` tells
  the client what to fix, while `Unexpected error.` says nothing and looks like our bug.
  We check the cases we expect and answer them clearly; masking is the safety net for
  everything we didn't expect.
- **If `max_depth` were 2:** the “My courses” query (`student → enrollments → course`, depth
  3) would be rejected, so both the `/my-courses` page and the `student(id: 2) → courses`
  case in `try_graphql.py` would break.

Other differences from the lab text:

- REST `GET /courses?page_size=-1` gives **422** (Pydantic, `Input should be greater than
  or equal to 1`), not 500: the pagination dependency from Lab 4 already checks
  `page_size` with `Query(ge=1, le=100)`.
- `measure.py` gave 1145 REST bytes instead of 1160 (the lab says a few bytes may differ).
- Strawberry is 0.341.2 here, not 0.338.0.

## Decisions

- **The rules and their errors live in `services.py`; each layer only translates the
  code.** If both REST and GraphQL checked the rules themselves, the constraint table
  and the try/except would be copied, and the copies would drift. Now one
  `ServiceError("ALREADY_ENROLLED")` became 409 `already-enrolled` in REST and
  `userErrors[0].code = ALREADY_ENROLLED` in GraphQL (steps 1 and 4), and a new rule only
  needs a new entry in `problem.py`.
- **Loaders are created in `Context` for every request, and the batch function matches rows
  by value.** A loader caches results by key, so one shared loader would hand one user's
  data to another and keep showing old data after a change. It would also outlive the
  request's database session. Matching by position is what broke in experiment 5: the
  lengths matched, and four of six enrollments quietly showed someone else's course.
  The `groups` dictionary looks each key up by its value, so the order of rows from the
  database doesn't matter.
- **The protection has two layers.** `check_limit` and `parse_id` handle the bad inputs we
  expect and give the client a clear message (`Invalid ID: 'abc'`). `MaskErrors` catches
  everything we didn't expect, like the 20-digit id that passed `parse_id` but broke
  `bigint`, and hides the internals that leaked in experiment 6. The developer still
  sees the full traceback in the server log.

## Migrations

| Command | What it does |
|---------|--------------|
| `alembic upgrade head` | applies all the missing migrations |
| `alembic downgrade -1` | rolls back the last migration |
| `alembic current` | shows the version of the database |
| `alembic history` | shows the chain of migrations |
| `alembic revision --autogenerate -m "text"` | writes a draft from models vs. database |
| `alembic check` | reports whether the models and the database have diverged |

The chain is `<base> -> 0001 (create catalog tables) -> 0002 (add course level)`. Lab 8
added no migrations. Run Alembic only from the project root.

## Notes

- **Windows console.** `try_graphql.py` and `try_n_plus_1.py` print `→`. In a console with
  the cp1251 code page Python fails with `UnicodeEncodeError: 'charmap' codec can't encode
  character '→'`. Run `$env:PYTHONUTF8 = "1"` in PowerShell first.
- **Slow scripts on Windows.** The scripts use `localhost`, which Windows first resolves to
  IPv6 `::1`, while `fastapi dev` listens on `127.0.0.1` only. Each request waits about
  2 s before falling back. The results are unaffected.
- **An extra CHECK from Lab 6:** `students_email_format CHECK (position('@' IN email) > 1)`
  is in the `Student` model with `conv()`, so the `ck` template doesn't rename it.
- The Lab 7 experiment log, decisions and migration self-check are in the git history
  of this file (commit `434d0de`); the Lab 4 and Lab 5 write-ups are in commit `5631ba7`.
