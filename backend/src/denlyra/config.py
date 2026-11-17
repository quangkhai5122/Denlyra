from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = False
    db_url: str = "sqlite+pysqlite:///./local_data/denlyra-demo.db"
    host: str = "127.0.0.1"
    port: int = 8766

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            demo_mode=os.getenv("DENLYRA_DEMO_MODE", "0") == "1",
            db_url=os.getenv("DENLYRA_DATABASE_URL", cls.db_url),
            host=os.getenv("DENLYRA_HOST", "127.0.0.1"),
            port=int(os.getenv("DENLYRA_PORT", "8766")),
        )

    def validate(self) -> None:
        if not self.demo_mode:
            raise RuntimeError("NOT A PRODUCTION EMR: DENLYRA_DEMO_MODE=1 required")
        if self.host not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError("DEMO API must bind only to loopback; no public deployment")
        if self.db_url.startswith("sqlite") and ":memory:" not in self.db_url:
            # Ensure that the demo creates directories, never a real default user DB.
            path = self.db_url.split("///", 1)[-1]
            if path and path != self.db_url:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
