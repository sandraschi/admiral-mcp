"""Configuration from environment variables."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    host: str = os.getenv("ADMIRAL_HOST", "127.0.0.1")
    port: int = int(os.getenv("ADMIRAL_PORT", "11089"))
    relay_token: str = os.getenv("ADMIRAL_RELAY_TOKEN", "admin")
    approval_timeout: int = int(os.getenv("ADMIRAL_APPROVAL_TIMEOUT", "300"))
    version: str = "0.1.0"
    data_dir: str = os.getenv("ADMIRAL_DATA_DIR", "data/admiral_mcp")

    # APNs (all optional - tools work without APNs, just no pushes)
    apns_key_path: str | None = os.getenv("ADMIRAL_APNS_KEY_PATH")
    apns_key_id: str | None = os.getenv("ADMIRAL_APNS_KEY_ID")
    apns_team_id: str | None = os.getenv("ADMIRAL_APNS_TEAM_ID")
    apns_topic: str | None = os.getenv("ADMIRAL_APNS_TOPIC")
    apns_use_sandbox: bool = os.getenv("ADMIRAL_APNS_SANDBOX", "1") == "1"
    apns_device_token: str | None = os.getenv("ADMIRAL_APNS_DEVICE_TOKEN")

    @property
    def apns_configured(self) -> bool:
        return all(
            [
                self.apns_key_path,
                self.apns_key_id,
                self.apns_team_id,
                self.apns_topic,
                self.apns_device_token,
            ]
        )


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
