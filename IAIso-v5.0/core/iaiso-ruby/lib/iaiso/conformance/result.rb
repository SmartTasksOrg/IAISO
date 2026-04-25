# frozen_string_literal: true

module IAIso
  module Conformance
    VectorResult = Data.define(:section, :name, :passed, :message) do
      def self.pass(section, name); new(section: section, name: name, passed: true, message: ""); end
      def self.fail(section, name, message); new(section: section, name: name, passed: false, message: message); end
    end

    class SectionResults
      attr_accessor :pressure, :consent, :events, :policy

      def initialize
        @pressure = []
        @consent  = []
        @events   = []
        @policy   = []
      end

      def all = pressure + consent + events + policy
      def total = all.size
      def passed = all.count(&:passed)
      def failed = all.reject(&:passed)
    end
  end
end
