from __future__ import annotations

import warnings

from config.settings import settings


def configure_warning_filters() -> None:
    if settings.SUPPRESS_32BIT_CRYPTO_WARNING:
        warnings.filterwarnings(
            "ignore",
            message=r"You are using cryptography on a 32-bit Python on a 64-bit Windows Operating System\..*",
            category=UserWarning,
            module=r"cryptography\.hazmat\.backends\.openssl\.backend",
        )

    warnings.filterwarnings(
        "ignore",
        message=r"'_UnionGenericAlias' is deprecated and slated for removal in Python 3\.17",
        category=DeprecationWarning,
        module=r"google\.genai\.types",
    )
