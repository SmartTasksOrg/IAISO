using System;

namespace IAIso.Core {
    public class Engine {
        private double _p = 0.0;
        public bool BackProp { get; set; } = true;

        public string Update(int tokens, int tools) {
            double delta = (tokens * 0.00015) + (tools * 0.08);
            _p = Math.Max(0, _p + delta - 0.02);
            if (_p >= 0.95) { _p = 0.0; return "RELEASED"; }
            return _p >= 0.85 ? "ESCALATED" : "OK";
        }
    }
}
