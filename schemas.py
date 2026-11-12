from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,  # is_elective <-> isElective in JSON
        validate_by_name=True,
        validate_by_alias=True,  # request bodies arrive with camelCase keys
        from_attributes=True,  # read SQLAlchemy objects and result rows
    )


class CourseOut(CamelModel):
    id: str
    title: str
    description: str
    credits: int
    is_elective: bool
    likes: int
    level: str


class StudentIn(CamelModel):
    # repeats the CHECK in the database: Pydantic answers 422 before the database
    name: str = Field(min_length=2)
    email: EmailStr


class StudentOut(StudentIn):
    id: int


class EnrollmentIn(CamelModel):
    course_id: str
    student_id: int


class EnrollmentOut(CamelModel):
    id: int
    course_id: str
    student_id: int
    enrolled_at: datetime


class EnrollmentDetail(EnrollmentOut):
    course_title: str
    student_name: str


class CourseStats(CamelModel):
    course_id: str
    enrolled: int


class Stats(CamelModel):
    total: int
    total_credits: int
    electives: int
