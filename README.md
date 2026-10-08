# Course Catalog API

A FastAPI backend that serves the course catalog (moved here from `lib/courses.ts`) with filtering, sorting, and pagination.

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

The server starts at http://127.0.0.1:8000, and the interactive docs are at http://127.0.0.1:8000/docs.

### Routes

| Route | Description |
|---|---|
| `GET /` | Checks that the server is alive |
| `GET /courses` | Course list. Query params: `is_elective` (true/false), `sort` (`popular` by default, or `title`), `q` (case-insensitive search in the title), `page` (default 1, at least 1), `page_size` (default 20, from 1 to 100) |
| `GET /courses/{course_id}` | A single course, or 404 `{"detail": "Course not found"}` |
| `GET /stats` | Catalog statistics: `total`, `total_credits`, `electives` (bonus 4) |

## What was verified

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
