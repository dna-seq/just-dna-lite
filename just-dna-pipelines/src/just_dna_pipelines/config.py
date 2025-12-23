import os


def get_default_workers() -> int:
    """
    Return default workers from JUST_DNA_PIPELINES_WORKERS env var or CPU count.

    Downloaders that manage their own workers should not use this.
    """
    return int(os.getenv("JUST_DNA_PIPELINES_WORKERS", os.cpu_count() or 1))


def get_parquet_workers() -> int:
    """
    Return parquet workers from JUST_DNA_PIPELINES_PARQUET_WORKERS env var or default of 4.

    This is used for memory-intensive parquet operations (conversion, splitting, etc.) to avoid memory overload.
    Default is 4 to balance performance and memory usage.
    """
    return int(os.getenv("JUST_DNA_PIPELINES_PARQUET_WORKERS", 4))


def get_download_workers() -> int:
    """
    Return download workers from JUST_DNA_PIPELINES_DOWNLOAD_WORKERS env var or CPU count.

    Used for parallel I/O-bound download operations.
    """
    return int(os.getenv("JUST_DNA_PIPELINES_DOWNLOAD_WORKERS", os.cpu_count() or 1))


def get_profile_enabled() -> bool:
    """Return whether profiling is enabled (JUST_DNA_PIPELINES_PROFILE), defaulting to True."""
    value = os.getenv("JUST_DNA_PIPELINES_PROFILE", "1").strip().lower()
    return value not in {"0", "false", "no", "off", "n"}


