from pydantic import BaseModel, ConfigDict
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


class Stats(CamelModel):
    total: int
    total_credits: int
    electives: int
