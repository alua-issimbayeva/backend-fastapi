from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # required: without a database address the application refuses to start
    database_url: str
    # required, no default: without a key (or with a short one) the app must not
    # start. 32 characters = 256 bits, the minimum for HS256 (RFC 7518, §3.2)
    secret_key: str = Field(min_length=32)
    # the access token lifetime in minutes
    access_token_minutes: int = 15
    # optional: print every SQL statement (only on your own machine)
    sql_echo: bool = False
    # GraphQL introspection (the schema map for GraphiQL); off on a closed production server
    graphql_introspection: bool = True


settings = Settings()
