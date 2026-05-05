"""Root package for the AI tourism assistant microservice.

Responsibilities:
    Publish package metadata (`__version__`, etc.) and serve as the `app` namespace
    entry point for the FastAPI app and domain modules.

Dependencies:
    None at module level; real startup happens in `app.main`.
"""

__version__ = "1.0.0"
__author__ = "Tourism Assistant Team"
__description__ = "AI-powered tourism recommendation and traveler matching service"
