# course-catalog-api

Backend of the course catalog: FastAPI, SQLAlchemy, PostgreSQL, Alembic migrations,
GraphQL on Strawberry, and JWT login with roles (Labs 4–9, “Advanced Web Technologies”).
REST and GraphQL share one database and one services layer (`services.py`).
The Next.js frontend lives in
[-awt-lab02-issimbaeva-alua](https://github.com/alua-issimbayeva/-awt-lab02-issimbaeva-alua);
since Lab 9 it has `/login` and `/account` (httpOnly cookie, Server Action, `proxy.ts`,
`verifySession()`).

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

# 2. dependencies (FastAPI, SQLAlchemy, psycopg, Alembic, Strawberry, PyJWT, pwdlib)
pip install -r requirements.txt

# 3. settings: copy the template, then put a random key into SECRET_KEY
cp .env.example .env               # Windows (PowerShell): Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste the output after SECRET_KEY=

# 4. schema: all three migrations (0001, 0002, 0003 = users)
alembic upgrade head

# 5. initial data: 6 courses, 3 students, 6 enrollments (clears the tables, users too)
psql -h localhost -U catalog_app -d course_catalog -v ON_ERROR_STOP=1 -f seed.sql

# 6. demo accounts (always after seed.sql: it empties users)
python seed_users.py

# 7. check that models and database agree, then start the server
alembic check
fastapi dev main.py
```

Without `SECRET_KEY`, or with a key shorter than 32 characters, the application refuses
to start (`ValidationError … secret_key`). The key never goes into git: `.env` is in
`.gitignore`, and `.env.example` holds only an empty `SECRET_KEY=`.

REST docs: http://localhost:8000/docs (the **Authorize** button logs in: e-mail in
`username`, password in `password`). GraphiQL: http://localhost:8000/graphql (the token
goes into the Headers panel: `{"Authorization": "Bearer <token>"}`).

Demo users (course passwords; a real project never publishes them):

| E-mail | Role | Password |
|--------|------|----------|
| admin@example.com | admin | admin-demo-password |
| aigerim@example.com | student (student 1) | aigerim-demo-pass |
| daniyar@example.com | student (student 2) | daniyar-demo-pass |
| asel@example.com | student (student 3) | asel-demo-password |

`seed.sql` also clears `users`: after it, always run `python seed_users.py`. If a script
fails with `KeyError: 'access_token'`, that is what was forgotten.

Check scripts (the server must be running, on the data from `seed.sql` + `seed_users.py`):

| Script | Expected |
|--------|----------|
| `python check_users.py` | `4 of 4 as expected` (no server needed) |
| `python try_auth.py` | `6 of 6 as expected` |
| `python try_tokens.py` | `9 of 9 as expected` |
| `python try_timing.py` | two medians within a few ms of each other (~90–100 ms) |
| `python try_access.py` | `14 of 14 as expected` |
| `python try_errors.py` | `5 of 5 as expected` (logs in as the administrator) |
| `python try_graphql_access.py` | `9 of 9 as expected` |
| `python try_graphql.py` | `8 of 8 as expected` |
| `python try_n_plus_1.py` | `SQL queries: 4` for both queries (3 from the loaders + 1 user lookup) |
| `python measure.py` | REST 5 requests in 2 rounds, GraphQL 1 request in 1 round |
| `python scan_routes.py` | 12 routes, 9 of them open without a token |
| `python scan_graphql.py` | 11 fields, 3 closed (`Query.me`, `Query.students`, `Student.email`) |

All of these were run after rebuilding the schema from zero (step 7, see “Differences
from the lab text”) and gave exactly the results above.

### Routes

| Route | Access | Description |
|---|---|---|
| `GET /` | everyone | Checks that the server is alive |
| `POST /auth/login` | everyone | Form `username` (e-mail) + `password` → `{"access_token", "token_type": "bearer"}`, or 401 `Incorrect email or password` |
| `GET /me` | logged in | The current user: `id`, `email`, `role`, `studentId` (never the hash) |
| `GET /courses`, `GET /courses/{id}` | everyone | Course list (filters, sort, pagination) and a single course |
| `POST /courses/{id}/like` | everyone (open spot) | Adds a like |
| `POST /students` | everyone (open spot) | Creates a student profile |
| `GET /students/{id}`, `GET /students/{id}/enrollments` | everyone (open spots) | A student and their enrollments |
| `POST /enrollments` | logged in, owner or admin | Enrolls `studentId` in `courseId`; a student only themselves |
| `GET /enrollments` | admin | All enrollments with course title and student name |
| `GET /stats`, `GET /stats/courses` | everyone | Catalog totals and enrollments per course |
| `POST /graphql` | see the scanners below | Queries `courses`, `course`, `me`, `students`, `student`, `enrollments`; mutations `enroll`, `likeCourse` |

How to read denials: **401** means “I don't know who you are” (no token, expired,
forged, user deleted) and comes with `WWW-Authenticate: Bearer`; **403** means “I know
you, but you may not” and has no such header. Both are `application/problem+json`. In
GraphQL a denial is status 200 with `errors` (a closed nullable field arrives as `null`
with its `path`); only a bad token is rejected before GraphQL, with an ordinary 401.

## Access matrix

The codes come from `python try_access.py` (14 of 14 as expected). The “—” cell: the
administrator has no student profile, so there is nobody to enroll “for yourself”.

| Request | Anonymous | Student | Administrator |
|---------|-----------|---------|---------------|
| `GET /courses` | 200 | 200 | 200 |
| `GET /me` | 401 | 200 | 200 |
| `GET /enrollments` | 401 | 403 | 200 |
| `POST /enrollments`, for yourself | 401 | 201 | — |
| `POST /enrollments`, for another | 401 | 403 | 201 |

Before step 3 the same script gave 9 of 14: an anonymous caller read all enrollments
(200) and enrolled students (201), and a student enrolled another student (201 instead
of 403). That last cell is BOLA, item 1 of the OWASP API Security Top 10.

GraphQL, from `python try_graphql_access.py` (9 of 9):

| Question | Anonymous | Student (Aigerim) | Administrator |
|----------|-----------|-------------------|---------------|
| `me` | `Authentication required` | own e-mail and role | own e-mail and role |
| `students` | `Admin role required` | `Admin role required` | list of 3 |
| `student(2) { name email }` | name, `email: null` + error | name, `email: null` + error | name and e-mail |
| `enrollments(limit: 4) { student { email } }` | 4 hidden | 2 shown (her own), 2 hidden | 4 shown |
| any query with a bad token | HTTP 401 | HTTP 401 | HTTP 401 |

## Open spots

Found by `scan_routes.py` and `scan_graphql.py`; not closed in this lab. My API has one
route more than the lab's example (`GET /stats` from Lab 4), so there are 17 rows: 9
REST and 8 GraphQL.

| Route or field | Verdict | How to close it |
|----------------|---------|-----------------|
| `GET /` | by design: a health check with no data | no need to close it |
| `GET /courses` | by design: the catalog is open to everyone | no need to close it |
| `GET /stats` | by design: totals of the public catalog (count, credits, electives) | no need to close it |
| `GET /courses/{id}` | by design: one course of the public catalog | no need to close it |
| `POST /courses/{id}/like` | a hole: an anonymous caller inflates the counter in a loop (`flood_likes.py` did +12 in one GraphQL request in Lab 8) | `CurrentUser`, one like per user: a `likes` table with `UNIQUE (user_id, course_id)` |
| `POST /students` | a hole: anyone creates profiles and can take someone's e-mail first, so the real person later gets `409 email-taken` | `AdminUser`; in the final project a profile is created together with the account at registration |
| `GET /students/{id}` | a hole: returns name **and e-mail**; ids go 1, 2, 3, so a loop collects every e-mail, the same leak that GraphQL `Student.email` now blocks | `CurrentUser` + `can_access_student` → 403 (or 404 if even existence is private) |
| `GET /students/{id}/enrollments` | a hole: anyone sees which courses any student takes, while the matrix closes the same data in `GET /enrollments` to everyone but the admin | `CurrentUser` + `can_access_student`; better a `GET /me/enrollments` that takes no id at all |
| `GET /stats/courses` | by design: only counts per course, no names | no need to close it (with very small courses a count can hint at a person; then admin only) |
| GraphQL `courses` | by design: the public catalog | no need to close it |
| GraphQL `course` | by design: one course | no need to close it |
| GraphQL `student` | a hole: `email` is closed, but an anonymous caller still enumerates ids and reads names and the path to enrollments | `IsAuthenticated` on the query and `IsSelfOrAdmin` on `name` too, or only `me { student }` for students |
| GraphQL `enrollments` | a hole: all enrollments of all students, with `student { name }`; REST `GET /enrollments` gives the same data only to the admin, so the two entrances disagree | `IsAdmin`, the same rule as `GET /enrollments` |
| GraphQL `Course.enrollments` | a hole: through the public `courses` anyone walks to every enrollment and student name | permission on the field: `IsAdmin`, or a resolver that returns only the caller's own enrollments |
| GraphQL `Student.enrollments` | a hole: someone else's course list, the GraphQL twin of `GET /students/{id}/enrollments` | `IsSelfOrAdmin` on the field, like `email` |
| GraphQL `enroll` | a hole: without a token it enrolls any student in any course, exactly what step 3 closed in REST; the check sits in the REST route, not in `services.enroll` which both entrances call | `IsAuthenticated`, and move the owner check into the service: `services.enroll(db, user, course_id)` takes the student from `user.student_id` (SEC-01) |
| GraphQL `likeCourse` | a hole: the same counter inflation as the REST like, many per request via aliases | `IsAuthenticated` + one like per user, the same service function as REST |

The pattern behind most holes: the permission lives in one entrance (a REST route or a
GraphQL resolver) instead of in a layer both share. The scanners make that visible
because they read the route list from `/openapi.json` and probe every field, so a new
route lands in the table by itself.

## Threat table

| Where | What can break | How it is covered | How I checked |
|-------|----------------|-------------------|---------------|
| The login form | Telling apart “no such e-mail” and “wrong password” by the text or by the time, so an attacker collects registered e-mails; guessing passwords | One text for every failure (`Incorrect email or password`, `auth.py: login`); `authenticate` verifies `DUMMY_HASH` when the e-mail is unknown, so both cases cost one Argon2id verification. Guessing is **not** limited (see below) | `try_auth.py` 6/6 (same text and `WWW-Authenticate: Bearer`); `try_timing.py`: 97.4 / 96.5 ms with the protection, **5.5 / 106.0 ms** (~19×) without it (experiment 2) |
| Passwords and the key | A database leak reveals passwords; a weak or committed key lets anyone sign tokens | `users.password_hash` holds only `$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>`, ~97 ms per hash; `SECRET_KEY` is required with `min_length=32`, read from `.env`, which is in `.gitignore`; `.env.example` has `SECRET_KEY=` empty | `check_users.py` 4/4; experiment 1: no key → `Field required`, `short` → `String should have at least 32 characters`; two hashes of one password differ but both verify |
| Token and role | A forged, edited, unsigned, expired or foreign token is accepted; a demoted admin keeps rights until the token expires | `read_access_token`: `algorithms=["HS256"]`, `issuer="course-catalog-api"`, `require=["exp","sub","iss"]`, `int(sub)` inside `try`; the user and the role are read from `users` on every request (`db.get(User, id)`) | `try_tokens.py` 9/9, and 3/9 with `verify_signature: False`, where an unsigned token entered as `admin@example.com` (experiment 3); one admin token: 200 → 403 after `UPDATE … role='student'` → 200 after restoring (experiment 4) |
| Permissions on objects | A student acts on someone else's object (BOLA); a forgotten route stays open; a GraphQL field leaks through another path | `require_admin` / `AdminUser` on `GET /enrollments`, `can_access_student` in `POST /enrollments`; GraphQL `IsAuthenticated`, `IsAdmin`, `IsSelfOrAdmin` on the field `Student.email` (nullable) | `try_access.py` 14/14, 13/14 without the owner check, and Daniyar was enrolled by Aigerim (experiment 5); `try_graphql_access.py` 9/9, 7/9 when only `students` was closed (experiment 6); scanners: 9 REST routes and 8 GraphQL fields still open (table above) |
| Cookie and Next.js | The token stolen by injected JavaScript or sent by another site; a page that trusts the mere presence of a cookie | The token lives only in the `session` cookie with `httpOnly`, `secure`, `sameSite: "lax"`, `path: "/"`, `maxAge: 900` (`lib/session.ts`), set by a Server Action; `proxy.ts` is only an optimistic check, `verifySession()` in `lib/dal.ts` asks the API `/me` | experiment 7: no cookie → 307 and no API call; forged cookie → 307, the API logged `GET /me 401`; with `verifySession()` removed the forged cookie opened the page (200) |
| Logout and lifetime | A token copied before “Log out” keeps working | The cookie and the token both live 15 minutes; logout deletes the cookie. Server-side revocation is **not** implemented (see below) | experiment 8: after logout `/account` gives 307, but the same token on `GET /me` still gives 200 with Aigerim's data |

Deliberately not closed:

- **Limiting login attempts.** Right now guessing is limited only by the ~100 ms Argon2id
  check per attempt (about 36 000 guesses an hour per connection, more in parallel). A
  counter in process memory is lost on restart and is not shared: with 4 uvicorn
  workers an attacker gets 4 counters. A table in PostgreSQL (`login_attempts`: key,
  count, window start) is shared and survives restarts, at the price of a write per
  failed login; a separate store like Redis with `INCR` + `EXPIRE` is the usual answer
  when there are several servers. A limit on the e-mail alone is bad: anyone who knows
  someone's address can lock that person out on purpose by failing five times, and one
  IP can still try one password on thousands of e-mails. I would combine a soft limit per
  IP with growing delays per (e-mail, IP) pair instead of a hard lock of the account.
- **The token after “Log out”.** I would pick `token_version`: an integer column in
  `users`, copied into the token as `ver` at login and compared in `get_optional_user`.
  It costs nothing extra on each request, because that function already loads the user
  row, and one `UPDATE` revokes all of a user's tokens (logout everywhere, password
  change, ban). The price: one device can't be logged out separately, and the frontend
  “Log out” has to call `POST /auth/logout-all` before deleting the cookie. A `jti`
  blacklist allows single-token revocation but needs a lookup in another table or store
  on every request; refresh tokens add the most code (rotation, storage, a second
  cookie). So: “Log out” guarantees that this browser forgets the token; it does not
  guarantee that a copy taken earlier stops working before its 15 minutes run out.

## Experiment log

Each experiment was undone right after it (`git restore` or the reverse `UPDATE`), and
the checks were run again.

| No. | Experiment | What I saw | Cause | How I fixed it |
|-----|------------|------------|-------|----------------|
| 1 | no key, a short key; two hashes of one password | No key: `ValidationError: 1 validation error for Settings` / `secret_key Field required [type=missing …]`. `SECRET_KEY=short`: `String should have at least 32 characters [type=string_too_short, input_value='short' …]`. Hash: 95–104 ms (5 runs), parts `argon2id`, `v=19`, `m=65536,t=3,p=4`, salt `BgSvpeqZGBWLmvj5VNiFIg`, hash; `h1 == h2` → `False`, both `verify` → `True`, `verify("wrong")` → `False`. For comparison one SHA-256 took ~1.1 µs | `secret_key` has no default and `min_length=32`. With a default like `"secret"` in the code every copy of the project would share the key, and anyone who read the repository could sign an admin token; failing at startup is better than running insecurely. The hash string carries the algorithm, parameters and a fresh salt, so no salt column is needed. SHA-256 is fast on purpose: ~85 000 times faster than Argon2id here, and on a GPU billions per second, so a leaked table would be guessed quickly | Restored the real key; nothing to fix in the hashing |
| 2 | login time with and without `DUMMY_HASH` | With the protection: unknown 97.4 ms, known 96.5 ms. Without it (early `return None`): unknown **5.5 ms**, known **106.0 ms**, about **19×** apart | Without a user nothing is hashed, so the answer for an unknown e-mail skips the ~100 ms Argon2id work; the same error text doesn't help when the time differs | `git restore auth.py`; medians close again (91.3 / 91.9 ms) |
| 3 | nine forged tokens; signature check turned off | Normally 9 of 9, every forgery `401 Invalid or expired token`. Decoding without a key showed `{'alg': 'HS256', 'typ': 'JWT'}` and `{'sub': '2', 'iss': 'course-catalog-api', 'iat': …, 'exp': …}` with `exp − iat = 900`, signature 43 characters. With `verify_signature: False`: **3 of 9**; `expired`, `signed with another key`, `another issuer`, `no exp` → 200 as Aigerim; `payload edited, old signature` and `alg none, no signature` → 200 as **admin@example.com**; only `valid`, `sub is not a number`, `sub of a missing user` stayed as expected | A JWT is signed, not encrypted: anyone reads the payload, so it must not hold secrets. Turning off the signature also turned off the `exp`, `iss` and `require` checks; the remaining two are stopped by `int()` and the database lookup. The most important protection is the signature with a server-chosen algorithm (`algorithms=[…]`): without it every other claim can be written by the attacker | `git restore security.py`; 9 of 9 again |
| 4 | the role changes in the database, the token is the same | Admin token on `GET /enrollments`: 200 → `UPDATE users SET role='student'` → **403** → role restored → 200. Aigerim's token: 403 → `role='admin'` → **200** → back → 403 | The token says only who (`sub`); `require_admin` reads `user.role` from the row loaded on every request. The price is one `SELECT` on `users` per request (visible in `try_n_plus_1.py`: 4 queries instead of 3). For a service whose admins change once a year a role in the token with a short lifetime is fine; for a bank I would read from the database, because a revoked right must stop at once | Restored the roles (`python seed_users.py` would do the same) |
| 5 | the owner check in `POST /enrollments` removed | `try_access.py`: **13 of 14**, the cell `POST /enrollments, for another` / student = `201 (want 403)`. By hand Aigerim enrolled Daniyar: `201`, `{"id":20,"courseId":"web-security","studentId":2,…}`; `enrollments` showed `20 \| Daniyar Bekov \| web-security`, and nothing recorded who did it | BOLA: authentication worked (the token was genuine), authorization on the object was missing. In experiment 3 the token itself was false; here a real user abused a real token, so no signature check can notice. Detecting it needs an audit trail: the request log plus the token's `sub`, or a `created_by` column | Deleted the row, `git restore main.py`; 14 of 14, 6 enrollments |
| 6 | the path closed, not the field; the closed field not nullable | (a) `email: str` without permission: **7 of 9**, `student(2).email, student` → `Daniyar Bekov, email daniyar@example.com`, `enrollments → student.email` → `4 shown, 0 hidden`, while `students` still said `Admin role required`. (b) `email: str` with the permission: 7 of 9 with `?`; `student(2) { name email }` → `{"data":{"student":null}, … "path":["student","email"]}`; through enrollments → `{"data":null, … "path":["enrollments",2,"student","email"]}` | (a) The same `Student` type is reached through `student(id)` and `enrollments → student`; locking the `students` door doesn't lock the others. (b) A denied non-null field must become null, so the null rises to the nearest nullable parent: `student` in one case, and through the non-null `student` of an enrollment and the non-null list up to `data` in the other | `git restore graphql_api.py`; 9 of 9. **The protection sits on the field of the type, not on the root query.** |
| 7 | a forged cookie; protection only in `proxy.ts` | `curl localhost:3000/account` → `307`, `location: /login`, nothing in the API log. With `Cookie: session=forged.token.value` → also `307`, but the API logged `"GET /me HTTP/1.1" 401 Unauthorized`. With `page.tsx` not calling `verifySession()`: no cookie → 307, forged cookie → **200** and “Secret account data”. A real token in the cookie rendered `aigerim@example.com · role: student` | `proxy.ts` only checks that a cookie named `session` exists; it cut off the request without a cookie. `verifySession()` showed the forgery to the API, which verified the signature and answered 401. The second check matters more: it is the only one that knows whether the token is real, and it stands next to the data, so any page that needs user data (the “My courses” pages, future enroll forms) must call it itself | `git restore app/account/page.tsx`; forged cookie → 307 again |
| 8 | the token after “Log out” | After logout `/account` → 307 (no cookie), but `curl /me -H "Authorization: Bearer <the same token>"` → `200 {"id":2,"email":"aigerim@example.com","role":"student","studentId":1}` | The server keeps no list of tokens; logout only deletes the browser's cookie. The token stays valid until `exp`, i.e. up to 15 minutes after login | Not fixed (by design of this lab); the right fix is `token_version` or a `jti` blacklist, plus a short lifetime (see the threat table) |

## Decisions

- **The user's role is read from the database on every request and is not in the token.**
  I pay one `SELECT` by primary key per request with a token (`try_n_plus_1.py` went
  from 3 to 4 queries). In return a role change or a deleted user takes effect on the
  next request: experiment 4 showed 200 → 403 on the same token without logging in
  again, while a role inside the token would have stayed valid for up to 15 minutes.
- **The closed GraphQL field allows null, and the permission hangs on the field of a type,
  not on the root query.** A type can be reached by many paths (`student(id)`,
  `enrollments → student`, later more), and only a check on the field fires on all of
  them; experiment 6a leaked Daniyar's e-mail through two open paths while `students`
  was locked. Nullable keeps the damage local: without `| None` one foreign e-mail
  nulled the whole `student`, or even the whole `data` of an enrollments query (6b).
- **`proxy.ts` checks only that a cookie exists, while `verifySession()` stands next to
  the data.** The proxy runs before every page and can't verify the token without a
  call to the API; it just saves a render for obvious anonymous visitors. Any made-up
  cookie passes it (experiment 7b opened the page with `session=forged.token.value`), so
  the real check must be where the data is read, and a page that forgets it fails
  closed instead of open.

## Migrations

| Command | What it does |
|---------|--------------|
| `alembic upgrade head` | applies all the missing migrations |
| `alembic downgrade -1` | rolls back the last migration |
| `alembic current` | shows the version of the database |
| `alembic history` | shows the chain of migrations |
| `alembic revision --autogenerate -m "text" --rev-id 000N` | writes a draft from models vs. database |
| `alembic check` | reports whether the models and the database have diverged |

The chain is `<base> -> 0001 (create catalog tables) -> 0002 (add course level) -> 0003
(create users)`. 0003 creates `users` with `users_pkey`, `users_email_key`,
`users_student_id_key`, `users_role_check` (`role IN ('student', 'admin')`) and
`users_student_id_fkey` (`ON DELETE SET NULL`); the names come from `naming_convention`
in `db.py`. Run Alembic only from the project root.

## Differences from the lab text

- **12 routes instead of 11.** `GET /stats` (Lab 4) is in my API, so `scan_routes.py`
  lists 9 open routes and “Open spots” has 17 rows.
- **The start from scratch** was checked with `alembic downgrade base` followed by the
  commands from “How to run” (`upgrade head` → `seed.sql` → `seed_users.py` →
  `alembic check`), not with `DROP DATABASE`: the role `catalog_app` has no right to
  create databases. All three migrations ran from an empty schema, and every check
  script gave the expected result.
- **Experiments with code changes were run on `uvicorn main:app` without `--reload`.**
  On my Windows machine the `fastapi dev` reloader printed `WatchFiles detected changes
  … Reloading...` but kept serving the old code (the old worker never exited), so the
  first “without protection” run of experiment 2 showed no difference. With a manual
  restart after each edit the results matched the lab.
- `measure.py` gives 1145 REST bytes instead of 1160; Python 3.13, PyJWT 2.15.1,
  pwdlib 0.4.2, Strawberry 0.341.2.

## Notes

- **Windows console.** Several scripts print `→`. In a console with the cp1251 code page
  Python fails with `UnicodeEncodeError: 'charmap' codec can't encode character '→'`. Run
  `$env:PYTHONUTF8 = "1"` in PowerShell first.
- **Slow scripts on Windows.** The scripts use `localhost`, which Windows first resolves to
  IPv6 `::1`, while the server listens on `127.0.0.1` only. Each new connection waits
  about 2 s before falling back, so `scan_routes.py` (36 requests) takes over a minute.
  The results are unaffected; `try_timing.py` reuses one connection, so its numbers are
  not affected either.
- **An extra CHECK from Lab 6:** `students_email_format CHECK (position('@' IN email) > 1)`
  is in the `Student` model with `conv()`, so the `ck` template doesn't rename it.
- The Lab 8 write-up (REST vs GraphQL comparison, its experiment log and decisions) is
  in the git history of this file (commit `a6c84a6`); Lab 7 in `434d0de`; Labs 4 and 5
  in `5631ba7`.
