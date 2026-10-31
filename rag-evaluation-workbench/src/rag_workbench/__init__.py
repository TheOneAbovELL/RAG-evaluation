"""RAG Evaluation Workbench: evaluate a retrieval-augmented QA pipeline over a dataset.

The package is import-safe: importing it never contacts a network service, reads an API
key, or builds an index. Expensive objects are created only when a run asks for them.
"""

import os

# DeepEval sends anonymous telemetry unless told otherwise. Disable it before any
# submodule can import deepeval. Users may still opt in explicitly by setting it to "0".
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")
# DeepEval also loads any .env / .env.local in the working directory by itself when it is imported, which would bypass
# RAGWB_NO_DOTENV and read files this project did not ask it to. The project loads its own .env (config.load_settings),
# so DeepEval is told not to. Set DEEPEVAL_DISABLE_DOTENV=0 to restore its own behaviour.
os.environ.setdefault("DEEPEVAL_DISABLE_DOTENV", "1")

__version__ = "1.4.1"

__all__ = ["__version__"]
