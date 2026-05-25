"""NullTracer: no-op tracer used when tracing is disabled."""

from artifactsmmo_cli.ai.tracer import Tracer


class NullTracer(Tracer):
    """No-op tracer — used when tracing is disabled."""

    def write_cycle(self, record: dict[str, object]) -> None:
        return

    def close(self) -> None:
        return
