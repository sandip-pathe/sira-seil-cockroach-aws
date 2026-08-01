"""External provider boundaries for SIRA + SEIL.

Provider-specific payloads and credentials terminate in this package.  Callers use
the typed protocols and credential-free result models exported by each adapter.
"""

from integrations.common import AdapterDescriptor, AdapterMode
from integrations.errors import ProviderError, ProviderErrorCode

__all__ = [
    "AdapterDescriptor",
    "AdapterMode",
    "ProviderError",
    "ProviderErrorCode",
]
