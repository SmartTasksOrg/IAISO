# frozen_string_literal: true

module IAIso
  module Middleware
    autoload :MiddlewareError,         "iaiso/middleware/errors"
    autoload :EscalationRaisedError,   "iaiso/middleware/errors"
    autoload :LockedError,             "iaiso/middleware/errors"
    autoload :ProviderError,           "iaiso/middleware/errors"

    autoload :Anthropic, "iaiso/middleware/anthropic"
    autoload :OpenAI,    "iaiso/middleware/openai"
    autoload :Gemini,    "iaiso/middleware/gemini"
    autoload :Bedrock,   "iaiso/middleware/bedrock"
    autoload :Mistral,   "iaiso/middleware/mistral"
    autoload :Cohere,    "iaiso/middleware/cohere"
    autoload :LiteLLM,   "iaiso/middleware/litellm"
  end
end
