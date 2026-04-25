"""Middleware wrappers for popular LLM SDKs and frameworks.

Each submodule is optional and has its own extras flag:

    pip install iaiso[anthropic]   # for iaiso.middleware.anthropic
    pip install iaiso[openai]      # for iaiso.middleware.openai
    pip install iaiso[langchain]   # for iaiso.middleware.langchain

Importing a submodule without its extras installed raises ImportError at
import time with a clear message.
"""
