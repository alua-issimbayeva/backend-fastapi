from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # required: without a database address the application refuses to start
    database_url: str
    # optional: print every SQL statement (only on your own machine)
    sql_echo: bool = False
    # GraphQL introspection (the schema map for GraphiQL); off on a closed production server
    graphql_introspection: bool = True


settings = Settings()
