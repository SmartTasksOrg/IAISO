package io.iaiso.conformance;

import java.util.ArrayList;
import java.util.List;

/** Results aggregated by section. */
public final class SectionResults {
    public final List<VectorResult> pressure = new ArrayList<>();
    public final List<VectorResult> consent = new ArrayList<>();
    public final List<VectorResult> events = new ArrayList<>();
    public final List<VectorResult> policy = new ArrayList<>();

    public int countPassed() {
        int p = 0;
        for (List<VectorResult> bucket : new List[]{pressure, consent, events, policy}) {
            for (VectorResult r : bucket) if (r.passed) p++;
        }
        return p;
    }

    public int countTotal() {
        return pressure.size() + consent.size() + events.size() + policy.size();
    }
}
