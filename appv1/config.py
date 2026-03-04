from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_URL: str

    HOST: str
    PORT: int

    BASE_URL: str

    # пожелания
    WISH_PREFIXES: str = "user_wish:"

    # лимиты в выдаче
    POSTS_LIMIT: int = 200
    WISHES_LIMIT: int = 200

    # реальные event_name из ботов:
    RPP_FILE_EVENT: str = (
        'Получить файл: "Пакет инструментов для работы с РПП от Ирины Ушаковой"'
    )
    FARMA_FILE_EVENT: str = 'Получить файл: "Гайд по серотониновому синдрому"'

    model_config = SettingsConfigDict(
        env_file="analytics.env",
        env_file_encoding="utf-8",
    )


settings = Settings()
