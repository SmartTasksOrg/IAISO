package org.iaiso.core;

public class IAIsoEngine {
    private double pressure = 0.0;
    private boolean backProp = true;

    public synchronized String update(int tokens, int tools) {
        double delta = (tokens * 0.00015) + (tools * 0.08);
        this.pressure = Math.max(0, this.pressure + delta - 0.02);
        return (this.pressure >= 0.95) ? "RELEASE_TRIGGERED" : "OK";
    }
}
