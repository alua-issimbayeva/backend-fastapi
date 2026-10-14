# Course Catalog API

A FastAPI backend that serves the course catalog (moved here from `lib/courses.ts`) with filtering, sorting, and pagination. Since Lab 5 it is the data source for the Next.js frontend [course-catalog](https://github.com/alua-issimbayeva/course-catalog) and accepts likes and enrollments.

## How to run

Requires Python 3.10+.

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
fastapi dev main.py
```

The server starts at http://localhost:8000, and the interactive docs are at http://localhost:8000/docs. Start it before the frontend.

### Routes

| Route | Description |
|---|---|
| `GET /` | Checks that the server is alive |
| `GET /courses` | Course list. Query params: `is_elective` (true/false), `sort` (`popular` by default, or `title`), `q` (case-insensitive search in the title), `page` (default 1, at least 1), `page_size` (default 20, from 1 to 100) |
| `GET /courses/{course_id}` | A single course, or 404 `{"detail": "Course not found"}` |
| `POST /courses/{course_id}/like` | Adds a like and returns the updated course, or 404 (Lab 5) |
| `POST /enrollments` | Enrolls a student: body `{"courseId", "studentName"}`, returns 201 with an `id` (Lab 5) |
| `GET /enrollments` | All enrollments received so far (Lab 5) |
| `GET /stats` | Catalog statistics: `total`, `totalCredits`, `electives` (Lab 4 bonus 4) |

Likes and enrollments are kept in memory, so they reset every time the server restarts.

## What changed (Lab 5)

### CORS: the allowed origin

`CORSMiddleware` allows exactly one origin, `http://localhost:3000`, where the Next.js dev server runs. The filter, the like button, and the enrollment form send their requests from the browser, and the page's origin (`localhost:3000`) differs from the API's (`localhost:8000`). Without an `access-control-allow-origin` header in the response, the browser hides the response from JavaScript. The value is an origin, meaning scheme, host and port, with no path and no trailing slash.

```bash
curl -i -H "Origin: http://localhost:3000" http://localhost:8000/   # access-control-allow-origin: http://localhost:3000, vary: Origin
curl -i -H "Origin: http://evil.example" http://localhost:8000/     # still 200, but no access-control-allow-origin
```

The preflight for the enrollment form answers 200 with `access-control-allow-methods`, `access-control-allow-headers: content-type`, and `access-control-max-age: 600`. CORS doesn't protect data. The server still executes requests from other origins; CORS only decides whether the browser lets the page read the response.

### camelCase in JSON

All models inherit from `CamelModel` (`alias_generator=to_camel`, `validate_by_name=True`, `validate_by_alias=True`). Python code keeps snake_case (`is_elective`), while JSON uses camelCase (`isElective`), matching the TypeScript `Course` type in the frontend.

- `validate_by_name=True` is required because `data.py` creates courses by field name. Without it, `is_elective=True` is silently ignored and every course becomes non-elective.
- Query parameters are not aliased, so the filter is still `?is_elective=true`. `?isElective=true` is an unknown parameter and is ignored, which returns all 6 courses.

### New routes: example responses

| Request | Response |
|---|---|
| `POST /courses/web-security/like` | 200 `{"id": "web-security", "title": "Web Security Essentials", "description": "JWT/OAuth2, XSS, CSRF, and SQL injection defense.", "credits": 4, "isElective": false, "likes": 22}` |
| the same again | 200, `"likes": 23` |
| `POST /courses/nope/like` | 404 `{"detail": "Course not found"}` |
| `POST /enrollments` `{"courseId": "web-security", "studentName": "Aigerim"}` | 201 `{"courseId": "web-security", "studentName": "Aigerim", "id": 1}` |
| the same with `"studentName": "A"` | 422, `"loc": ["body", "studentName"]`, `"msg": "String should have at least 2 characters"` |
| the same with `"courseId": "nope"` | 404 `{"detail": "Course not found"}` |
| `POST /enrollments` without `Content-Type: application/json` | 422, "Input should be a valid dictionary or object to extract fields from" |
| `GET /enrollments` | `[{"courseId": "web-security", "studentName": "Aigerim", "id": 1}]` |

## What was verified (Lab 4)

Since Lab 5, the JSON keys in these responses are camelCase (`isElective`, `totalCredits`); the routes and their results are otherwise unchanged.

All checked against the running server (`fastapi dev main.py`) and through `/docs`:

| Request | Result |
|---|---|
| `GET /` | `{"message": "Course Catalog API is running"}` |
| `GET /courses` | 6 courses: ai-integration, modern-frontend, web-security, backend-fastapi, databases-postgresql, api-design |
| `GET /courses?is_elective=true` | 2 courses: ai-integration, api-design |
| `GET /courses?is_elective=false` | 4 courses: modern-frontend, web-security, backend-fastapi, databases-postgresql |
| `GET /courses?sort=title` | ai-integration, api-design, backend-fastapi, modern-frontend, databases-postgresql, web-security |
| `GET /courses?page=1&page_size=2` | ai-integration, modern-frontend |
| `GET /courses?page=2&page_size=2` | web-security, backend-fastapi |
| `GET /courses?page=3&page_size=2` | databases-postgresql, api-design |
| `GET /courses?page=4&page_size=2` | `[]` |
| `GET /courses/web-security` | 200, the Web Security Essentials course |
| `GET /courses/nope` | 404, `{"detail": "Course not found"}` |
| `/docs` | Shows the three core routes `GET /`, `GET /courses`, `GET /courses/{course_id}` (plus `GET /stats` from bonus 4), and the `Course` schema |

### Bonus tasks

| Bonus | Request | Result |
|---|---|---|
| 1. `sort` as `Literal["popular", "title"]` | `GET /courses?sort=banana` | 422, "Input should be 'popular' or 'title'"; `/docs` shows a dropdown |
| 2. Pagination limits with `Query` | `GET /courses?page=0` | 422, "Input should be greater than or equal to 1" |
| | `GET /courses?page_size=1000` | 422, "Input should be less than or equal to 100" |
| | `GET /courses?page_size=100` | 200, all 6 courses |
| 3. Search by title (`q`) | `GET /courses?q=react` | modern-frontend |
| | `GET /courses?q=api` | backend-fastapi, api-design |
| 4. `GET /stats` with a `Stats` model | `GET /stats` | `{"total": 6, "total_credits": 28, "electives": 2}` |

Also checked:

- `python -c "import data; print(len(data.COURSES))"` prints `6`.
- `Course(id="x", title="t", description="d", credits="five")` raises a ValidationError ("Input should be a valid integer"), while `credits="5"` is converted to `5`.
