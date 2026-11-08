// DESIGN REFERENCE — NOT SHIPPING CODE. This `vision/` sketch is not the
// installable IAIso SDK (core/iaiso-python). `BackProp`/`magnify` document an
// early design concept the real engine does not implement (flags are no-ops).
export class IAIsoEngine {
    constructor(systemId = "web-client") {
        this.systemId = systemId;
        this.p = 0.0;
        this.backProp = true; // DESIGN SKETCH flag; no-op in the real SDK
    }

    updatePressure(tokens = 0, tools = 0) {
        const delta = (tokens * 0.00015) + (tools * 0.08);
        this.p = Math.max(0, this.p + delta - 0.02);

        if (this.p >= 0.95) {
            this.p = 0.0;
            return "RELEASE_TRIGGERED";
        }
        return this.p >= 0.85 ? "ESCALATED" : "OK";
    }

    magnify(output) {
        // DESIGN SKETCH: marker only, no refinement. Not in the shipping SDK.
        return this.backProp ? `[IAIso-MAGNIFIED] ${output}` : output;
    }
}
