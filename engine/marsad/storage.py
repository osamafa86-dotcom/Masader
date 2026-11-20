"""Raw file storage. Local directory now; the interface matches an S3 bucket for later."""

from pathlib import Path


class LocalStorage:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)

    def put(self, key: str, data: bytes) -> str:
        path = self.base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return (self.base / key).read_bytes()
