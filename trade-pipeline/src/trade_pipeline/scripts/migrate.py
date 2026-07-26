"""One-shot schema/partition setup, for the `migrate` compose service.

The consumer already calls `init_schema` on its own startup (see
`consumer/dedup_consumer.py`), so this isn't strictly required for a bare
`uv run` local setup — but in `docker compose up`, the API and consumer
containers start concurrently, and the API has no schema-init call of its
own (it only ever reads). A dedicated one-shot `migrate` service that both
depend on (`condition: service_completed_successfully`) guarantees the
schema and partitions exist before either touches Postgres, rather than
relying on `create_all`/`ensure_partitions`'s idempotency to paper over the
race.
"""

import logging

from trade_pipeline.common.config import load_config
from trade_pipeline.consumer.postgres_sink import init_schema, make_engine

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    engine = make_engine(config.postgres.dsn.replace("+asyncpg", "+psycopg"))
    init_schema(engine)
    logger.info("schema + partitions ready")
