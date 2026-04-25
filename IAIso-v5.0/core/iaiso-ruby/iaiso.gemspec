# frozen_string_literal: true

require_relative "lib/iaiso/version"

Gem::Specification.new do |spec|
  spec.name = "iaiso"
  spec.version = IAIso::VERSION
  spec.authors = ["IAIso Contributors"]
  spec.email = ["iaiso@example.com"]

  spec.summary = "Bounded-agent-execution framework for LLM agent loops."
  spec.description = <<~DESC
    IAIso adds pressure-based rate limiting, scope-based authorization,
    and structured audit logging to LLM agent loops. This is the Ruby
    reference SDK, conformant to IAIso spec 1.0. Wire-format compatible
    with the Python, Node, Go, Rust, Java, C#, PHP, and Swift reference
    SDKs.
  DESC
  spec.homepage = "https://github.com/SmartTasksOrg/IAISO"
  spec.license = "Apache-2.0"
  spec.required_ruby_version = ">= 3.0.0"

  spec.metadata["homepage_uri"] = spec.homepage
  spec.metadata["source_code_uri"] = spec.homepage
  spec.metadata["changelog_uri"] = "#{spec.homepage}/blob/main/CHANGELOG.md"

  spec.files = Dir.glob([
    "lib/**/*.rb",
    "exe/iaiso",
    "spec/**/*",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
  ])
  spec.bindir = "exe"
  spec.executables = ["iaiso"]
  spec.require_paths = ["lib"]

  # Zero runtime dependencies — everything we need is in Ruby stdlib:
  # json, openssl, base64, securerandom, set, monitor.

  spec.add_development_dependency "rake", "~> 13.0"
  # Minitest is in stdlib; no need to add as a dependency.
end
