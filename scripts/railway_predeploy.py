"""Run Railway's one-writer schema and restricted-role bootstrap."""

from alembic import command
from alembic.config import Config

from prepare_railway_database import main as prepare_database


def main() -> None:
    command.upgrade(Config("alembic.ini"), "head")
    prepare_database()


if __name__ == "__main__":
    main()
