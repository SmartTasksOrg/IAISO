# frozen_string_literal: true

module IAIso
  module Audit
    # Sink contract. Ruby uses duck typing so this is documentation;
    # any object responding to `emit(event)` is a valid sink.
    module Sink
      def emit(event)
        raise NotImplementedError, "subclasses must implement #emit"
      end
    end
  end
end
