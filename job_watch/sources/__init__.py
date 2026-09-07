from .indeed import IndeedSource
from .leforem import LeForemSource
from .linkedin import LinkedInSource

SOURCE_CLASSES = {
    "leforem": LeForemSource,
    "indeed": IndeedSource,
    "linkedin": LinkedInSource,
}

__all__ = ["SOURCE_CLASSES", "IndeedSource", "LeForemSource", "LinkedInSource"]
