# frozen_string_literal: true

module IAIso
  module Middleware
    # LiteLLM proxy-pattern helper.
    #
    # LiteLLM's primary integration is its proxy server, which exposes
    # an OpenAI-compatible HTTP endpoint that routes to any of 100+
    # underlying providers. On the client side, point an
    # OpenAI-compatible client at the proxy URL and account for the
    # call via IAIso::Middleware::OpenAI::BoundedClient — token
    # accounting works identically to vanilla OpenAI.
    #
    # This module exists primarily to make the integration discoverable
    # alongside the other LLM middleware. ProxyConfig documents the
    # typical fields you'd configure on your underlying client.
    module LiteLLM
      ProxyConfig = Data.define(:base_url, :api_key, :default_headers) do
        def self.build(base_url:, api_key: "", default_headers: {})
          new(base_url: base_url, api_key: api_key, default_headers: default_headers)
        end
      end
    end
  end
end
