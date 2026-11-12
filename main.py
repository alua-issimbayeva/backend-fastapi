from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from db import get_db
from models import Course
from schemas import CourseOut, Stats

app = FastAPI(title="Course Catalog API")

app.add_middleware(
    CORSMiddleware,
    # an origin: scheme + host + port, no path and no trailing slash
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SessionDep = Annotated[Session, Depends(get_db)]


def pagination(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return {"offset": (page - 1) * page_size, "limit": page_size}


@app.get("/")
def read_root():
    return {"message": "Course Catalog API is running"}


@app.get("/courses", response_model=list[CourseOut])
def list_courses(
    db: SessionDep,
    is_elective: bool | None = None,
    sort: Literal["popular", "title"] = "popular",
    q: str | None = None,
    p: dict = Depends(pagination),
):
    stmt = select(Course)
    # "is not None" so that ?is_elective=false still filters
    if is_elective is not None:
        stmt = stmt.where(Course.is_elective == is_elective)
    if q:
        stmt = stmt.where(Course.title.icontains(q))
    if sort == "title":
        stmt = stmt.order_by(Course.title)
    else:
        # id as the second key: equal like counts keep a stable order across pages
        stmt = stmt.order_by(Course.likes.desc(), Course.id)
    stmt = stmt.limit(p["limit"]).offset(p["offset"])
    return db.scalars(stmt).all()


@app.get("/stats", response_model=Stats)
def get_stats(db: SessionDep):
    stmt = select(
        func.count(Course.id).label("total"),
        func.coalesce(func.sum(Course.credits), 0).label("total_credits"),
        func.count().filter(Course.is_elective).label("electives"),
    )
    return db.execute(stmt).one()


@app.get("/courses/{course_id}", response_model=CourseOut)
def get_course(course_id: str, db: SessionDep):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@app.post("/courses/{course_id}/like", response_model=CourseOut)
def like_course(course_id: str, db: SessionDep):
    # the database does the adding: UPDATE ... SET likes = likes + 1 RETURNING ...
    stmt = (
        update(Course)
        .where(Course.id == course_id)
        .values(likes=Course.likes + 1)
        .returning(Course)
    )
    course = db.scalars(stmt).one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    db.commit()
    return course
